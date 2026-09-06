"""Resiliencia para la llamada booking-svc -> notif-svc (Task 3).

Combina dos patrones complementarios alrededor de la llamada HTTP a
notif-svc:

- **Retries con backoff exponencial + jitter** (`tenacity`): reintenta
  fallos transitorios (timeouts, errores de red, 5xx) unas pocas veces
  dentro de UNA misma invocacion, esperando cada vez un poco mas (con
  aleatoriedad para evitar que varios requests reintenten todos al mismo
  tiempo).
- **Circuit breaker** (`circuitbreaker`): si las llamadas siguen fallando
  DESPUES de agotar los reintentos, el breaker se "abre" y las siguientes
  llamadas fallan de inmediato (sin ni siquiera intentar la red) durante
  `recovery_timeout` segundos. Esto evita que booking-svc se quede
  bloqueado reintentando contra un notif-svc caido, y le da tiempo a
  notif-svc para recuperarse sin que le sigan llegando requests.

Notas de implementacion (importantes, dejaron bugs en un intento previo):

1. `circuitbreaker==2.1.3` es async-aware: `@circuit` detecta automaticamente
   si la funcion decorada es una coroutine y la envuelve en consecuencia.
   Se usa siempre como DECORADOR (`@circuit(...)`); nunca se llama
   `breaker.call_async(...)` manualmente.
2. El orden de los decoradores importa: `@circuit` va POR FUERA de
   `@retry`. Asi, el circuit breaker solo cuenta como "un fallo" el
   resultado FINAL de una llamada (despues de que tenacity ya agoto sus
   reintentos), no cada intento individual. Si el circuito esta abierto,
   ni siquiera se ejecutan los reintentos: se levanta `CircuitBreakerError`
   de inmediato.
3. Se distinguen dos tipos de error:
   - `NotifServiceError` (red, timeout, 5xx): son errores "de notif-svc",
     se reintentan y cuentan contra el circuit breaker
     (`expected_exception=NotifServiceError`).
   - `NotifServiceClientError` (4xx): son errores "nuestros" (payload
     invalido, etc). Reintentar no ayuda porque el resultado seria el
     mismo, y no deben abrir el circuito (notif-svc esta sano, el problema
     es la request). No matchean `retry_if_exception_type` ni
     `expected_exception`, asi que se propagan de inmediato sin reintento
     ni conteo de fallo.
4. `tenacity.before_sleep_log` necesita un logger estandar de
   `logging.Logger` (no un `structlog` BoundLogger) — de ahi el
   `import logging` en vez de usar structlog aqui directamente.
"""

import logging

import httpx
from circuitbreaker import CircuitBreakerError, circuit
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

__all__ = [
    "NotifServiceError",
    "NotifServiceClientError",
    "CircuitBreakerError",
    "call_notif_service",
]

_logger = logging.getLogger("booking-svc.resilience")

# --- Parametros de resiliencia (ajustados para que una demo sea rapida de
# observar: pocos segundos, no minutos) ---
RETRY_ATTEMPTS = 3
RETRY_WAIT_INITIAL_SECONDS = 0.5
RETRY_WAIT_MAX_SECONDS = 4
CIRCUIT_FAILURE_THRESHOLD = 3
CIRCUIT_RECOVERY_TIMEOUT_SECONDS = 10
HTTP_TIMEOUT_SECONDS = 5


class NotifServiceError(Exception):
    """Error transitorio de notif-svc: red, timeout, o respuesta 5xx.

    Se reintenta (tenacity) y cuenta como fallo para el circuit breaker.
    """


class NotifServiceClientError(Exception):
    """Error 4xx de notif-svc: la request que enviamos esta mal formada.

    NO se reintenta (reintentar no cambiaria el resultado) y NO cuenta
    contra el circuit breaker (el problema es nuestro payload, no la salud
    de notif-svc).
    """


@circuit(
    failure_threshold=CIRCUIT_FAILURE_THRESHOLD,
    recovery_timeout=CIRCUIT_RECOVERY_TIMEOUT_SECONDS,
    expected_exception=NotifServiceError,
    name="notif-svc",
)
@retry(
    reraise=True,
    stop=stop_after_attempt(RETRY_ATTEMPTS),
    wait=wait_exponential_jitter(
        initial=RETRY_WAIT_INITIAL_SECONDS, max=RETRY_WAIT_MAX_SECONDS
    ),
    retry=retry_if_exception_type(NotifServiceError),
    before_sleep=before_sleep_log(_logger, logging.WARNING),
)
async def call_notif_service(url: str, payload: dict, headers: dict) -> dict:
    """POST a `{url}` (esperado: `.../notifications`) con retry + circuit breaker.

    Lanza `NotifServiceError` para fallos transitorios (red/timeout/5xx) —
    reintentados automaticamente por tenacity, y contados por el circuit
    breaker. Lanza `NotifServiceClientError` para 4xx — sin reintento, sin
    contar contra el breaker. Lanza `circuitbreaker.CircuitBreakerError` si
    el circuito esta abierto (notif-svc viene fallando de forma sostenida).
    """
    try:
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT_SECONDS) as client:
            response = await client.post(url, json=payload, headers=headers)
    except httpx.RequestError as e:
        # Cubre timeouts, errores de conexion/red, DNS, etc — cualquier cosa
        # que falle ANTES de recibir una respuesta HTTP.
        raise NotifServiceError(f"Network error calling notif-svc: {e}") from e

    if response.status_code >= 500:
        raise NotifServiceError(
            f"notif-svc returned {response.status_code}: {response.text}"
        )
    if response.status_code >= 400:
        raise NotifServiceClientError(
            f"notif-svc returned {response.status_code}: {response.text}"
        )

    return response.json()
