"""Descubrimiento de agentes via Agent Card (Task 5).

Este es el equivalente, para agentes, de lo que `discovery.py` hace con
Consul para microservicios: en vez de preguntarle a un registry central
"donde esta X", el orchestrator va a la URL conocida de cada agente y lee su
Agent Card en /.well-known/agent.json, que le dice quien es y que skills tiene.

El resultado se cachea en memoria; `discover_agents(force=True)` lo refresca.
"""

from dataclasses import dataclass, field

import httpx
import structlog
from a2a.client import A2ACardResolver
from a2a.types import AgentCard

from .config import settings

logger = structlog.get_logger(f"{settings.SERVICE_NAME}.discovery")

# El enunciado especifica esta ruta; los agentes la sirven junto con la ruta
# por defecto del SDK (/.well-known/agent-card.json).
AGENT_CARD_PATH = "/.well-known/agent.json"


@dataclass
class DiscoveredAgent:
    """Un agente encontrado, con su card y la URL por la que se le habla."""

    base_url: str
    card: AgentCard
    skills: dict[str, str] = field(default_factory=dict)  # skill_id -> description

    @property
    def name(self) -> str:
        return self.card.name

    def to_dict(self) -> dict:
        return {
            "name": self.card.name,
            "description": self.card.description,
            "version": self.card.version,
            "base_url": self.base_url,
            "card_url": f"{self.base_url}{AGENT_CARD_PATH}",
            "skills": [
                {"id": s.id, "name": s.name, "description": s.description}
                for s in self.card.skills
            ],
        }


_registry: dict[str, DiscoveredAgent] = {}  # skill_id -> agent
_agents: list[DiscoveredAgent] = []


async def discover_agents(force: bool = False) -> list[DiscoveredAgent]:
    """Lee el Agent Card de cada agente conocido y arma el indice de skills.

    Si un agente no responde, se omite y se sigue con los demas: el
    orchestrator puede operar parcialmente (y el error queda logueado).
    """
    global _agents
    if _agents and not force:
        return _agents

    found: list[DiscoveredAgent] = []
    async with httpx.AsyncClient(timeout=10) as hx:
        for base_url in settings.AGENT_URLS:
            try:
                resolver = A2ACardResolver(
                    httpx_client=hx,
                    base_url=base_url,
                    agent_card_path=AGENT_CARD_PATH,
                )
                card = await resolver.get_agent_card()
            except Exception as e:
                logger.warning(
                    "discovery.agent_card_failed", base_url=base_url, error=str(e)
                )
                continue

            agent = DiscoveredAgent(
                base_url=base_url,
                card=card,
                skills={s.id: s.description for s in card.skills},
            )
            found.append(agent)
            logger.info(
                "discovery.agent_found",
                agent=card.name,
                base_url=base_url,
                skills=list(agent.skills),
            )

    _agents = found
    _registry.clear()
    for agent in found:
        for skill_id in agent.skills:
            _registry[skill_id] = agent

    return _agents


def agent_for_skill(skill_id: str) -> DiscoveredAgent | None:
    """Resuelve que agente ofrece una skill dada."""
    return _registry.get(skill_id)


def known_agents() -> list[DiscoveredAgent]:
    return _agents
