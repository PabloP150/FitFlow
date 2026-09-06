"""Correlation ID middleware (Task 3 — Observabilidad).

Propaga un `x-correlation-id` por request para poder rastrear una misma
operacion a traves de logs de distintos servicios (p.ej. booking-svc ->
notif-svc).
"""

import time
import uuid

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

logger = structlog.get_logger("http")


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """Asigna/propaga un `x-correlation-id` por cada request entrante.

    - Si el caller ya mando el header `x-correlation-id` (p.ej. porque la
      request ya cruzo otro servicio), se reusa ese mismo id — asi una
      operacion conserva un unico id de punta a punta. Si no vino, se genera
      un UUID4 nuevo.
    - Se enlaza a los contextvars de structlog (`bind_contextvars`) para que
      TODO log emitido mientras se procesa este request incluya
      automaticamente `correlation_id`, sin tener que pasarlo a mano por
      cada funcion.
    - Se guarda en `request.state.correlation_id` para que los routers lo
      puedan leer y reenviarlo en llamadas salientes a otros servicios
      (p.ej. booking-svc -> notif-svc).
    - Se devuelve en el header de la respuesta, para que el caller (o quien
      inspeccione la respuesta) tambien lo vea.
    - Se emite una linea de log JSON por request (metodo, path, status,
      duracion) como access-log estructurado minimo.
    """

    async def dispatch(self, request: Request, call_next):
        correlation_id = request.headers.get("x-correlation-id") or str(uuid.uuid4())
        request.state.correlation_id = correlation_id

        # Limpiamos contextvars de requests previos (importante: en el mismo
        # worker/proceso, distintos requests concurrentes corren en tasks
        # de asyncio separadas, pero limpiar explicito evita fugas si algo
        # reusa el contexto).
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(correlation_id=correlation_id)

        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = round((time.perf_counter() - start) * 1000, 2)

        response.headers["x-correlation-id"] = correlation_id

        logger.info(
            "http.request",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=duration_ms,
        )

        return response
