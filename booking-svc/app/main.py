import asyncio
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI

from .config import settings
from .consul_client import deregister_service, register_service
from .database import Base, SessionLocal, engine
from .logging_config import configure_logging
from .middleware import CorrelationIdMiddleware
from .outbox import outbox_worker_loop
from .routers import bookings, classes, health
from .seed import seed_classes

configure_logging(settings.SERVICE_NAME)
logger = structlog.get_logger(settings.SERVICE_NAME)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    Base.metadata.create_all(engine)

    db = SessionLocal()
    try:
        seed_classes(db)
    finally:
        db.close()

    try:
        register_service()
        logger.info("consul.registered")
    except Exception as e:
        logger.warning("consul.register_failed", error=str(e))

    # Worker en background del outbox de notificaciones (Task 3). Se
    # coordina el shutdown con un asyncio.Event en vez de cancelar la task a
    # la fuerza, para que un ciclo de trabajo en curso pueda terminar limpio.
    stop_event = asyncio.Event()
    outbox_task = asyncio.create_task(outbox_worker_loop(stop_event))

    yield

    # Shutdown
    stop_event.set()
    await outbox_task

    try:
        deregister_service()
        logger.info("consul.deregistered")
    except Exception as e:
        logger.warning("consul.deregister_failed", error=str(e))


app = FastAPI(title=settings.SERVICE_NAME, lifespan=lifespan)
app.add_middleware(CorrelationIdMiddleware)
app.include_router(health.router)
app.include_router(classes.router)
app.include_router(bookings.router)
