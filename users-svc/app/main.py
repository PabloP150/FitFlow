from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI

from .config import settings
from .consul_client import deregister_service, register_service
from .database import Base, engine
from .logging_config import configure_logging
from .middleware import CorrelationIdMiddleware
from .routers import health, users

configure_logging(settings.SERVICE_NAME)
logger = structlog.get_logger(settings.SERVICE_NAME)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    Base.metadata.create_all(bind=engine)
    try:
        register_service()
        logger.info("consul.registered")
    except Exception:
        # Consul may not be up (e.g. running `docker compose up users-db users-svc`
        # without consul). Registration is best-effort so the API stays usable.
        logger.warning("consul.register_failed", exc_info=True)
    yield
    # Shutdown
    try:
        deregister_service()
        logger.info("consul.deregistered")
    except Exception:
        logger.warning("consul.deregister_failed", exc_info=True)


app = FastAPI(title="users-svc", lifespan=lifespan)
app.add_middleware(CorrelationIdMiddleware)

app.include_router(health.router)
app.include_router(users.router)
