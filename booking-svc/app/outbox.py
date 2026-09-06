"""Outbox worker: entrega diferida de notificaciones (Task 3 — Resiliencia).

Cuando `notif_client.send_notification` no logra entregar una notificacion
en el momento (red caida, notif-svc con 5xx, o circuit breaker abierto), la
guarda como fila `pending` en la tabla `pending_notifications` en vez de
perderla. Este modulo corre un loop en background (lanzado desde el
`lifespan` de `main.py`) que cada `POLL_INTERVAL_SECONDS` revisa esa tabla y
reintenta la entrega.

Importante: el worker reintenta las notificaciones pendientes pasando por
el MISMO `call_notif_service` (retry + circuit breaker) que usa el flujo
sincrono de creacion de reservas. Eso significa que las llamadas del outbox
tambien actuan como "sonda": mientras el circuito este abierto, el propio
`circuitbreaker` corta la llamada de inmediato (`CircuitBreakerError`) sin
tocar la red; pasado el `recovery_timeout`, la siguiente llamada del outbox
(o la de un booking nuevo, lo que ocurra primero) es la que efectivamente
prueba si notif-svc ya se recupero y, si tiene exito, cierra el circuito de
nuevo.
"""

import asyncio
from datetime import datetime

import structlog
from circuitbreaker import CircuitBreakerError

from .database import SessionLocal
from .discovery import get_service_url
from .models import FAILED, PENDING, SENT, PendingNotification
from .resilience import NotifServiceClientError, NotifServiceError, call_notif_service

logger = structlog.get_logger("booking-svc.outbox")

POLL_INTERVAL_SECONDS = 10
MAX_ATTEMPTS = 10
BATCH_SIZE = 20


async def _process_one(db, item: PendingNotification) -> None:
    headers = {"x-correlation-id": item.correlation_id} if item.correlation_id else {}
    payload = {
        "user_id": item.user_id,
        "type": item.type,
        "message": item.message,
        "booking_id": item.booking_id,
    }

    url = get_service_url("notif-svc")
    await call_notif_service(f"{url}/notifications", payload, headers)

    item.status = SENT
    item.last_attempt_at = datetime.utcnow()
    db.commit()
    logger.info("outbox.sent", pending_id=item.id, user_id=item.user_id)


async def process_pending_notifications_once() -> int:
    """Procesa un lote de notificaciones pendientes. Devuelve cuantas se enviaron."""
    db = SessionLocal()
    sent_count = 0
    try:
        pending = (
            db.query(PendingNotification)
            .filter(PendingNotification.status == PENDING)
            .order_by(PendingNotification.id)
            .limit(BATCH_SIZE)
            .all()
        )
        if not pending:
            return 0

        for item in pending:
            try:
                await _process_one(db, item)
                sent_count += 1
            except CircuitBreakerError:
                # Circuito abierto: notif-svc sigue caido. No tiene sentido
                # seguir intentando el resto del lote en esta pasada — se
                # reintenta todo en el proximo poll.
                logger.warning("outbox.circuit_open", pending_id=item.id)
                break
            except NotifServiceClientError as e:
                # Payload invalido: reintentar no cambiaria el resultado.
                item.status = FAILED
                item.attempts += 1
                item.last_attempt_at = datetime.utcnow()
                db.commit()
                logger.error(
                    "outbox.client_error", pending_id=item.id, error=str(e)
                )
            except NotifServiceError as e:
                item.attempts += 1
                item.last_attempt_at = datetime.utcnow()
                if item.attempts >= MAX_ATTEMPTS:
                    item.status = FAILED
                    logger.error(
                        "outbox.giving_up",
                        pending_id=item.id,
                        attempts=item.attempts,
                        error=str(e),
                    )
                else:
                    logger.warning(
                        "outbox.retry_failed",
                        pending_id=item.id,
                        attempts=item.attempts,
                        error=str(e),
                    )
                db.commit()
            except Exception as e:  # discovery failure u otro error inesperado
                logger.warning("outbox.unexpected_error", pending_id=item.id, error=str(e))
                break

        return sent_count
    finally:
        db.close()


async def outbox_worker_loop(stop_event: asyncio.Event) -> None:
    """Loop en background: procesa el outbox cada POLL_INTERVAL_SECONDS.

    Se detiene limpiamente cuando `stop_event` se marca (shutdown de la app).
    """
    logger.info("outbox.worker_started", interval_seconds=POLL_INTERVAL_SECONDS)
    while not stop_event.is_set():
        try:
            sent = await process_pending_notifications_once()
            if sent:
                logger.info("outbox.batch_processed", sent=sent)
        except Exception:
            logger.exception("outbox.worker_error")

        try:
            await asyncio.wait_for(stop_event.wait(), timeout=POLL_INTERVAL_SECONDS)
        except asyncio.TimeoutError:
            pass  # timeout normal: toca el siguiente poll

    logger.info("outbox.worker_stopped")
