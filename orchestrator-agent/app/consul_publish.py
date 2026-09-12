"""Publicacion de agentes descubiertos en Consul (Task 5).

Los agentes A2A NO se auto-registran en Consul al arrancar: se descubren
entre si por Agent Card, que es un mecanismo distinto y deliberadamente
separado del service registry de los microservicios.

Este modulo existe para hacer visible esa diferencia en la demo: el boton del
dashboard descubre los agentes por su Agent Card y *entonces* los publica en
Consul. Antes del click, Consul no sabe que existen; despues, aparecen en
verde junto a los microservicios.

Es un registro "de tercero" (third-party registration): el orchestrator
registra a otros, en vez de que cada agente se registre a si mismo.
"""

from urllib.parse import urlparse

import consul as consul_lib
import structlog

from .agent_registry import DiscoveredAgent
from .config import settings

logger = structlog.get_logger(f"{settings.SERVICE_NAME}.consul")


def get_consul() -> consul_lib.Consul:
    return consul_lib.Consul(host=settings.CONSUL_HOST, port=settings.CONSUL_PORT)


def _service_id(name: str) -> str:
    return f"{name}-1"


def publish_agent(agent: DiscoveredAgent) -> dict:
    """Registra un agente descubierto en Consul, con health check contra /healthz.

    El nombre del servicio se toma del hostname de su URL (p.ej.
    "booking-agent"), para que coincida con el resto de nombres logicos del
    docker-compose.
    """
    parsed = urlparse(agent.base_url)
    host = parsed.hostname or agent.base_url
    port = parsed.port or 80
    name = host  # en docker-compose el hostname ES el nombre logico del servicio

    c = get_consul()
    c.agent.service.register(
        name=name,
        service_id=_service_id(name),
        address=host,
        port=port,
        tags=["a2a-agent", "discovered-via-agent-card"],
        check=consul_lib.Check.http(
            url=f"{agent.base_url}/healthz",
            interval="10s",
            timeout="5s",
            deregister="60s",
        ),
    )
    logger.info("consul.agent_published", agent=agent.name, service=name, port=port)
    return {"service": name, "address": host, "port": port}


def publish_agents(agents: list[DiscoveredAgent]) -> list[dict]:
    """Publica todos los agentes descubiertos; no lanza si uno falla."""
    published = []
    for agent in agents:
        try:
            published.append(publish_agent(agent))
        except Exception as e:
            logger.warning(
                "consul.publish_failed", agent=agent.name, error=str(e)
            )
            published.append({"service": agent.name, "error": str(e)})
    return published


def unpublish_agents(agents: list[DiscoveredAgent]) -> list[str]:
    """Quita de Consul los agentes publicados (vuelve al estado "pre-boton").

    Sirve para poder repetir la demo: deja Consul como estaba antes del
    descubrimiento, con solo los microservicios registrados.
    """
    removed = []
    c = get_consul()
    for agent in agents:
        host = urlparse(agent.base_url).hostname or agent.base_url
        try:
            c.agent.service.deregister(_service_id(host))
            removed.append(host)
            logger.info("consul.agent_unpublished", service=host)
        except Exception as e:
            logger.warning("consul.unpublish_failed", service=host, error=str(e))
    return removed


def registered_agent_services() -> list[str]:
    """Nombres de servicios en Consul que fueron publicados como agentes A2A."""
    try:
        c = get_consul()
        _, services = c.catalog.services()
    except Exception as e:
        logger.warning("consul.catalog_failed", error=str(e))
        return []
    return [name for name, tags in (services or {}).items() if "a2a-agent" in (tags or [])]
