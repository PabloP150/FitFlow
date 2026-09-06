"""Cliente HTTP booking-svc -> notif-svc, con resiliencia (Task 3).

`send_notification` intenta la entrega inmediata via `resilience.call_notif_service`
(retry con backoff + circuit breaker). Si eso falla — timeout/red, 5xx
persistente, o circuito abierto — la notificacion se encola de forma
duradera en la tabla `pending_notifications` (ver `models.py` / `outbox.py`)
en vez de perderse. Un worker en background (`outbox.py`) la reintenta mas
tarde.

Esto es "best-effort pero sin perdida": una reserva NUNCA falla por culpa
de notif-svc, y la notificacion tampoco se descarta silenciosamente cuando
notif-svc esta caido — se entrega en cuanto vuelve a estar sano.
"""

from typing import Optional

import structlog
from sqlalchemy.orm import Session

from .discovery import get_service_url
from .models import PendingNotification
from .resilience import NotifServiceClientError, call_notif_service

logger = structlog.get_logger("booking-svc.notif_client")


async def send_notification(
    db: Session,
    user_id: int,
    notif_type: str,
    message: str,
    booking_id: Optional[int] = None,
    correlation_id: Optional[str] = None,
) -> None:
    """Envia una notificacion a notif-svc; nunca lanza excepciones.

    En exito, retorna sin mas. En fallo (transitorio o circuito abierto),
    encola la notificacion en el outbox para reintento posterior. En un
    error de payload (4xx — "nuestra culpa"), lo loguea y descarta: no tiene
    sentido reintentar algo que va a volver a fallar igual.
    """
    payload = {
        "user_id": user_id,
        "type": notif_type,
        "message": message,
        "booking_id": booking_id,
    }
    headers = {"x-correlation-id": correlation_id} if correlation_id else {}

    try:
        url = get_service_url("notif-svc")
        await call_notif_service(f"{url}/notifications", payload, headers)
        logger.info("notification.sent", user_id=user_id, type=notif_type)
        return
    except NotifServiceClientError as e:
        logger.error(
            "notification.client_error", user_id=user_id, type=notif_type, error=str(e)
        )
        return
    except Exception as e:
        # Cubre: NotifServiceError (red/timeout/5xx tras agotar reintentos),
        # circuitbreaker.CircuitBreakerError (circuito abierto), y fallos de
        # discovery (notif-svc no registrado en Consul).
        logger.warning(
            "notification.failed_queuing_outbox",
            user_id=user_id,
            type=notif_type,
            error=str(e),
        )

    pending = PendingNotification(
        user_id=user_id,
        type=notif_type,
        message=message,
        booking_id=booking_id,
        correlation_id=correlation_id,
    )
    db.add(pending)
    db.commit()
    logger.info("notification.queued_to_outbox", user_id=user_id, type=notif_type)
