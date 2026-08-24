from contextlib import asynccontextmanager

from fastapi import FastAPI

from .config import settings
from .consul_client import deregister_service, register_service
from .database import Base, SessionLocal, engine
from .routers import bookings, classes, health
from .seed import seed_classes


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
        print(f"[{settings.SERVICE_NAME}] Registered in Consul")
    except Exception as e:
        print(f"[{settings.SERVICE_NAME}] Failed to register: {e}")

    yield

    # Shutdown
    try:
        deregister_service()
        print(f"[{settings.SERVICE_NAME}] Deregistered from Consul")
    except Exception as e:
        print(f"[{settings.SERVICE_NAME}] Failed to deregister: {e}")


app = FastAPI(title=settings.SERVICE_NAME, lifespan=lifespan)
app.include_router(health.router)
app.include_router(classes.router)
app.include_router(bookings.router)
