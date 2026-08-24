import consul as consul_lib

from .config import settings

SERVICE_ID = f"{settings.SERVICE_NAME}-1"


def get_consul() -> consul_lib.Consul:
    return consul_lib.Consul(host=settings.CONSUL_HOST, port=settings.CONSUL_PORT)


def register_service():
    """Register this service instance in Consul with an HTTP health check."""
    c = get_consul()
    c.agent.service.register(
        name=settings.SERVICE_NAME,
        service_id=SERVICE_ID,
        address=settings.SERVICE_HOST,
        port=settings.SERVICE_PORT,
        check=consul_lib.Check.http(
            url=f"http://{settings.SERVICE_HOST}:{settings.SERVICE_PORT}/healthz",
            interval="10s",
            timeout="5s",
            deregister="30s",
        ),
    )


def deregister_service():
    """Deregister this service instance from Consul."""
    c = get_consul()
    c.agent.service.deregister(SERVICE_ID)
