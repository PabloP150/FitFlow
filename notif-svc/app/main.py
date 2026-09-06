from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI

from app.config import settings
from app.consul_client import deregister_service, register_service
from app.database import Base, engine
from app.logging_config import configure_logging
from app.middleware import CorrelationIdMiddleware
from app.routers import health, notifications

configure_logging(settings.SERVICE_NAME)
logger = structlog.get_logger(settings.SERVICE_NAME)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: primero crear las tablas, luego registrar en Consul.
    # Este orden importa porque Consul hace un healthcheck HTTP a /readyz
    # (via /healthz) que asume que la app ya puede responder correctamente,
    # y /readyz a su vez intenta conectar a la base de datos.
    Base.metadata.create_all(engine)
    try:
        register_service(settings)
        logger.info("consul.registered")
    except Exception as e:
        logger.warning("consul.register_failed", error=str(e))

    yield

    # Shutdown
    try:
        deregister_service(settings)
        logger.info("consul.deregistered")
    except Exception as e:
        logger.warning("consul.deregister_failed", error=str(e))


app = FastAPI(title=settings.SERVICE_NAME, lifespan=lifespan)
app.add_middleware(CorrelationIdMiddleware)

app.include_router(notifications.router)
app.include_router(health.router)
