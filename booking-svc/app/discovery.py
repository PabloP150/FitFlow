import consul as consul_lib
import structlog

from .config import settings

logger = structlog.get_logger("booking-svc.discovery")


def get_consul() -> consul_lib.Consul:
    return consul_lib.Consul(host=settings.CONSUL_HOST, port=settings.CONSUL_PORT)


def get_service_url(service_name: str) -> str:
    """Resolve a service's base URL dynamically via Consul health-passing entries."""
    try:
        c = get_consul()
        _, services = c.health.service(service_name, passing=True)
        if not services:
            raise Exception(f"Service {service_name} not found or not passing health check")

        entry = services[0]["Service"]
        return f"http://{entry['Address']}:{entry['Port']}"
    except Exception as e:
        logger.warning("discovery.resolve_failed", service=service_name, error=str(e))
        raise
