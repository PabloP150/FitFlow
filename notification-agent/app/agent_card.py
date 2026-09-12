"""Agent Card del Notification Agent (Task 5).

El Agent Card es el mecanismo de descubrimiento de A2A: un JSON publicado en
/.well-known/agent.json que declara quien es el agente y que sabe hacer.
Es el analogo, para agentes, de lo que Consul es para microservicios.

Nota sobre la forma del JSON: el SDK implementa A2A v1.0, donde la URL del
agente vive dentro de `supported_interfaces` (con su binding de protocolo)
en vez de ser un campo `url` plano como en borradores anteriores del spec.
"""

from a2a.types import AgentCapabilities, AgentCard, AgentInterface, AgentSkill

from .config import settings

SKILL_SEND_NOTIFICATION = "send_notification"
SKILL_GET_HISTORY = "get_history"

SKILLS = [
    AgentSkill(
        id=SKILL_SEND_NOTIFICATION,
        name="Enviar notificacion",
        description=(
            "Envia una notificacion a un usuario de FitFlow (por ejemplo, para "
            "avisarle que su reserva fue confirmada)."
        ),
        tags=["notifications", "fitflow"],
        examples=["Avisame cuando este lista mi reserva", "Notifica al usuario 1"],
    ),
    AgentSkill(
        id=SKILL_GET_HISTORY,
        name="Consultar historial",
        description=(
            "Devuelve el historial de notificaciones de un usuario. Requiere las "
            "credenciales del propio usuario."
        ),
        tags=["notifications", "fitflow"],
        examples=["Muestrame mis notificaciones"],
    ),
]


def build_agent_card() -> AgentCard:
    return AgentCard(
        name="FitFlow Notification Agent",
        description="Gestiona notificaciones a usuarios de FitFlow",
        version="1.0.0",
        capabilities=AgentCapabilities(streaming=True),
        supported_interfaces=[
            AgentInterface(
                url=settings.AGENT_URL,
                protocol_binding="JSONRPC",
                protocol_version="1.0",
            )
        ],
        default_input_modes=["application/json", "text/plain"],
        default_output_modes=["application/json", "text/plain"],
        skills=SKILLS,
    )
