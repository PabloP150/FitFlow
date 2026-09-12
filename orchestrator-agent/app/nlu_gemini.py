"""NLU del Orchestrator con Gemini (Task 5).

Traduce una instruccion en lenguaje natural ("Reserva yoga para el viernes y
avisame por notificacion") en una secuencia ordenada de skills a delegar.

Como funciona:
  1. Las skills disponibles NO estan hard-codeadas: se arman a partir de los
     Agent Cards realmente descubiertos (ver `agent_registry.py`).
  2. Cada skill se traduce en una `FunctionDeclaration` de Gemini. Gemini
     decide cuales llamar y en que orden.
  3. La ejecucion automatica de funciones va DESACTIVADA: no queremos que
     Gemini ejecute nada localmente, solo que *decida*. La ejecucion real la
     hace `a2a_dispatch.delegate()` contra el agente remoto.

Nota de diseno: el Agent Card de A2A declara que skills existe pero no el
esquema de argumentos de cada una. Gemini si necesita un esquema para generar
argumentos estructurados, asi que lo aportamos aqui. El descubrimiento de
*que agentes hay y que skills ofrecen* sigue siendo 100% dinamico; solo la
forma de los argumentos es estatica.

Ademas, los argumentos sensibles o derivados (email, password, user_id) NO se
le piden a Gemini: los inyecta el orchestrator (ver `main.py`).
"""

from typing import Any

import structlog
from google import genai
from google.genai import types
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

from .config import settings

logger = structlog.get_logger(f"{settings.SERVICE_NAME}.nlu")


class GeminiTransientError(Exception):
    """Error temporal de la API de Gemini (503 sobrecarga, 429 rate limit)."""


# Codigos que vale la pena reintentar: la API de Gemini devuelve 503
# ("high demand") de forma intermitente, y eso no deberia tumbar la demo.
_TRANSIENT_MARKERS = ("503", "UNAVAILABLE", "429", "RESOURCE_EXHAUSTED", "500", "INTERNAL")


def _is_transient(e: Exception) -> bool:
    text = str(e)
    return any(m in text for m in _TRANSIENT_MARKERS)

# Esquema de argumentos "semanticos" por skill: solo lo que se puede inferir
# del lenguaje natural. Las credenciales y los ids derivados los inyecta el
# orchestrator despues.
SKILL_PARAM_SCHEMAS: dict[str, dict[str, Any]] = {
    "list_classes": {"type": "object", "properties": {}},
    "create_booking": {
        "type": "object",
        "properties": {
            "class_id": {
                "type": "integer",
                "description": "El id de la clase a reservar, tomado de la lista de clases disponibles.",
            }
        },
        "required": ["class_id"],
    },
    "cancel_booking": {
        "type": "object",
        "properties": {
            "booking_id": {
                "type": "integer",
                "description": "El id de la reserva a cancelar.",
            }
        },
        "required": ["booking_id"],
    },
    "send_notification": {
        "type": "object",
        "properties": {
            "message": {
                "type": "string",
                "description": "Texto de la notificacion para el usuario, en espanol.",
            },
            "type": {
                "type": "string",
                "description": "Tipo de notificacion, p.ej. 'booking_confirmation'.",
            },
        },
        "required": ["message"],
    },
    "get_history": {"type": "object", "properties": {}},
}

SYSTEM_INSTRUCTION = """\
Eres el orquestador de FitFlow, una plataforma de reservas de clases fitness.

Recibes una instruccion del usuario en lenguaje natural y decides que
herramientas (skills de agentes especializados) hay que ejecutar y en que
orden para cumplirla.

Reglas:
- Una instruccion puede requerir VARIAS skills. Emite TODAS las llamadas
  necesarias en una sola respuesta, en el orden logico de ejecucion.
- Cada accion que pide el usuario necesita su propia llamada. Las skills son
  independientes entre si: ninguna hace el trabajo de otra. En particular,
  `create_booking` NO envia ninguna notificacion — si el usuario pide que se
  le avise, notifique o confirme, DEBES ademas llamar a `send_notification`
  despues de la reserva.
- Para reservar, usa el class_id correcto segun la lista de clases
  disponibles que se te da en el contexto. Escoge la clase cuyo nombre mejor
  corresponda a lo que pide el usuario.
- NO inventes ids que no aparezcan en el contexto.
- No pidas email, password ni user_id: el sistema los inyecta automaticamente.
- Si la instruccion no requiere ninguna accion, no llames ninguna skill.

Ejemplo: "Reserva pilates y avisame" -> dos llamadas:
  create_booking(class_id=<id de Pilates>), luego
  send_notification(message="Tu reserva de Pilates fue confirmada",
                    type="booking_confirmation")
"""


def _build_tools(skills: dict[str, str]) -> list[types.Tool]:
    """Arma las FunctionDeclarations a partir de las skills descubiertas."""
    declarations = []
    for skill_id, description in skills.items():
        schema = SKILL_PARAM_SCHEMAS.get(skill_id)
        if schema is None:
            # Skill descubierta sin esquema conocido: se expone sin argumentos
            # en vez de omitirla, para que Gemini al menos pueda invocarla.
            logger.warning("nlu.skill_without_schema", skill=skill_id)
            schema = {"type": "object", "properties": {}}
        declarations.append(
            types.FunctionDeclaration(
                name=skill_id,
                description=description,
                parameters_json_schema=schema,
            )
        )
    return [types.Tool(function_declarations=declarations)]


async def plan(
    instruction: str, skills: dict[str, str], context: str = ""
) -> list[tuple[str, dict]]:
    """Devuelve la secuencia de (skill_id, args) que Gemini decidio ejecutar.

    `skills` es el mapa skill_id -> descripcion, tomado de los Agent Cards.
    `context` es texto adicional (p.ej. la lista de clases disponibles) para
    que Gemini pueda resolver nombres a ids.
    """
    # El valor de .env.example cuenta como "sin configurar": si no, el error
    # que ve el usuario es un 400 crudo de Google en vez de algo accionable.
    if not settings.GEMINI_API_KEY or settings.GEMINI_API_KEY.startswith("your-"):
        raise RuntimeError(
            "GEMINI_API_KEY no esta configurada. Poné una key real en .env "
            "(obtenela en https://aistudio.google.com/apikey) y reinicia "
            "orchestrator-agent para que pueda interpretar lenguaje natural."
        )

    client = genai.Client(api_key=settings.GEMINI_API_KEY)
    prompt = f"{context}\n\nInstruccion del usuario: {instruction}" if context else instruction

    @retry(
        reraise=True,
        stop=stop_after_attempt(4),
        wait=wait_exponential_jitter(initial=1, max=8),
        retry=retry_if_exception_type(GeminiTransientError),
    )
    async def _generate():
        try:
            return await client.aio.models.generate_content(
                model=settings.GEMINI_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_INSTRUCTION,
                    tools=_build_tools(skills),
                    # Queremos la DECISION de Gemini, no que ejecute nada localmente.
                    automatic_function_calling=types.AutomaticFunctionCallingConfig(
                        disable=True
                    ),
                    temperature=0,
                ),
            )
        except Exception as e:
            if _is_transient(e):
                logger.warning("nlu.transient_error", error=str(e)[:200])
                raise GeminiTransientError(str(e)) from e
            raise

    logger.info("nlu.request", instruction=instruction, skills=list(skills))
    response = await _generate()

    decisions: list[tuple[str, dict]] = []
    for call in response.function_calls or []:
        decisions.append((call.name, dict(call.args or {})))

    logger.info("nlu.plan", decisions=[d[0] for d in decisions])
    return decisions
