import consul as consul_lib
from .config import settings


def get_consul():
    return consul_lib.Consul(host=settings.CONSUL_HOST, port=settings.CONSUL_PORT)


def get_service_url(service_name: str) -> str:
    """Resolve service URL from Consul, handling local vs docker mode"""
    try:
        c = get_consul()
        _, services = c.health.service(service_name, passing=True)
        if not services:
            raise Exception(f"Service {service_name} not found or not passing health check")

        entry = services[0]["Service"]

        # Si MCP corre localmente (no en docker), reescribir hostname a localhost
        host = "localhost" if settings.MCP_RUN_MODE == "local" else entry["Address"]

        return f"http://{host}:{entry['Port']}"
    except Exception as e:
        print(f"[discovery] Error resolving {service_name}: {e}")
        raise
