import consul as consul_lib

from .config import settings


def _get_consul_client() -> consul_lib.Consul:
    return consul_lib.Consul(host=settings.CONSUL_HOST, port=settings.CONSUL_PORT)


def register_service() -> None:
    """Register this service instance in Consul with an HTTP health check."""
    client = _get_consul_client()
    client.agent.service.register(
        name=settings.SERVICE_NAME,
        service_id=f"{settings.SERVICE_NAME}-1",
        address=settings.SERVICE_HOST,
        port=settings.SERVICE_PORT,
        check=consul_lib.Check.http(
            url=f"http://{settings.SERVICE_HOST}:{settings.SERVICE_PORT}/healthz",
            interval="10s",
            timeout="5s",
            deregister="30s",
        ),
    )


def deregister_service() -> None:
    """Deregister this service instance from Consul."""
    client = _get_consul_client()
    client.agent.service.deregister(f"{settings.SERVICE_NAME}-1")
