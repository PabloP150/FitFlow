"""Structured JSON logging (Task 3 — Observabilidad).

Configura `structlog` + el modulo estandar `logging` para que TODO log de
este proceso salga como una linea JSON en stdout: tanto los que emitimos
nosotros via `structlog.get_logger()` como los que emiten librerias que usan
`logging` directamente (uvicorn, sqlalchemy, etc).

Se usa `structlog.stdlib.ProcessorFormatter` (no `JSONRenderer` aplicado
directo en `structlog.configure`) precisamente para poder unificar ambas
fuentes de logs bajo el mismo formatter/processor chain. Aplicar
`JSONRenderer` directo en `structlog.configure` solo formatea los logs de
structlog; los de uvicorn/sqlalchemy seguirian saliendo en texto plano.
"""

import logging
import sys

import structlog


def configure_logging(service_name: str) -> None:
    """Configura logging estructurado en JSON para todo el proceso.

    Debe llamarse una sola vez, al importar `main.py`, antes de crear la
    app de FastAPI.
    """

    def add_service_name(logger, method_name, event_dict):
        event_dict["service"] = service_name
        return event_dict

    # Processors compartidos por logs que se originan en structlog Y por
    # logs que se originan en el modulo `logging` estandar (foreign_pre_chain).
    shared_processors = [
        structlog.contextvars.merge_contextvars,
        add_service_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    structlog.configure(
        processors=shared_processors
        + [structlog.stdlib.ProcessorFormatter.wrap_for_formatter],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        processor=structlog.processors.JSONRenderer(),
        foreign_pre_chain=shared_processors,
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers = [handler]
    root_logger.setLevel(logging.INFO)

    # uvicorn instala sus propios handlers (texto plano) al arrancar; los
    # quitamos y dejamos que sus logs se propaguen al root logger, que ya
    # tiene el handler JSON configurado arriba.
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        uv_logger = logging.getLogger(name)
        uv_logger.handlers = []
        uv_logger.propagate = True
