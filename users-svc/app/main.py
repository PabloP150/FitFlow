import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from .consul_client import deregister_service, register_service
from .database import Base, engine
from .routers import health, users

logger = logging.getLogger("users-svc")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    Base.metadata.create_all(bind=engine)
    try:
        register_service()
    except Exception:
        # Consul may not be up (e.g. running `docker compose up users-db users-svc`
        # without consul). Registration is best-effort so the API stays usable.
        logger.warning("Could not register service in Consul", exc_info=True)
    yield
    # Shutdown
    try:
        deregister_service()
    except Exception:
        logger.warning("Could not deregister service from Consul", exc_info=True)


app = FastAPI(title="users-svc", lifespan=lifespan)

app.include_router(health.router)
app.include_router(users.router)
