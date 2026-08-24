from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import settings
from app.consul_client import deregister_service, register_service
from app.database import Base, engine
from app.routers import health, notifications


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: primero crear las tablas, luego registrar en Consul.
    # Este orden importa porque Consul hace un healthcheck HTTP a /readyz
    # (via /healthz) que asume que la app ya puede responder correctamente,
    # y /readyz a su vez intenta conectar a la base de datos.
    Base.metadata.create_all(engine)
    try:
        register_service(settings)
        print(f"[{settings.SERVICE_NAME}] Registered in Consul")
    except Exception as e:
        print(f"[{settings.SERVICE_NAME}] Failed to register in Consul: {e}")

    yield

    # Shutdown
    try:
        deregister_service(settings)
        print(f"[{settings.SERVICE_NAME}] Deregistered from Consul")
    except Exception as e:
        print(f"[{settings.SERVICE_NAME}] Failed to deregister: {e}")


app = FastAPI(title=settings.SERVICE_NAME, lifespan=lifespan)

app.include_router(notifications.router)
app.include_router(health.router)
