"""Agent Card del Booking Agent (Task 5).

El Agent Card es el mecanismo de descubrimiento de A2A: un JSON publicado en
/.well-known/agent.json que declara quien es el agente y que sabe hacer.
Es el analogo, para agentes, de lo que Consul es para microservicios.

Nota sobre la forma del JSON: el SDK implementa A2A v1.0, donde la URL del
agente vive dentro de `supported_interfaces` (con su binding de protocolo)
en vez de ser un campo `url` plano como en borradores anteriores del spec.
"""

from a2a.types import AgentCapabilities, AgentCard, AgentInterface, AgentSkill

from .config import settings

SKILL_LIST_CLASSES = "list_classes"
SKILL_CREATE_BOOKING = "create_booking"
SKILL_CANCEL_BOOKING = "cancel_booking"

SKILLS = [
    AgentSkill(
        id=SKILL_LIST_CLASSES,
        name="Listar clases",
        description=(
            "Devuelve las clases de fitness disponibles con su id, horario y "
            "cupo restante. No requiere credenciales."
        ),
        tags=["booking", "fitflow"],
        examples=["Que clases hay disponibles?"],
    ),
    AgentSkill(
        id=SKILL_CREATE_BOOKING,
        name="Crear reserva",
        description=(
            "Reserva una clase de fitness para un usuario. Requiere el id de la "
            "clase y las credenciales del usuario."
        ),
        tags=["booking", "fitflow"],
        examples=["Reserva yoga para manana", "Quiero inscribirme a spinning"],
    ),
    AgentSkill(
        id=SKILL_CANCEL_BOOKING,
        name="Cancelar reserva",
        description=(
            "Cancela una reserva existente de un usuario a partir del id de la reserva."
        ),
        tags=["booking", "fitflow"],
        examples=["Cancela mi reserva 3"],
    ),
]


def build_agent_card() -> AgentCard:
    return AgentCard(
        name="FitFlow Booking Agent",
        description="Gestiona reservas de clases fitness en FitFlow",
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
