"""Delegacion de tareas a otros agentes via protocolo A2A (Task 5).

El orchestrator no ejecuta ninguna skill: se la delega al agente que la
publica en su Agent Card. Cada delegacion es un mensaje A2A con un sobre JSON

    {"skill": "<skill_id>", "args": {...}}

y la respuesta es el artifact que el agente remoto adjunta a la Task.

Todo envio y toda respuesta se loguean bajo el logger "a2a" — esos son los
"logs de comunicacion A2A" que pide la demo del enunciado.
"""

from typing import Any

import httpx
import structlog
from a2a.client import ClientConfig, create_client
from a2a.helpers import get_data_parts, new_data_message
from a2a.types import Role, SendMessageRequest

from .agent_registry import DiscoveredAgent
from .config import settings

logger = structlog.get_logger("a2a")


def _extract_artifact(chunk: Any) -> dict | None:
    """Saca el primer data part de los artifacts de una Task, si los hay."""
    task = getattr(chunk, "task", None)
    if task is None and type(chunk).__name__ == "Task":
        task = chunk
    if task is None or not getattr(task, "artifacts", None):
        return None
    for artifact in task.artifacts:
        parts = get_data_parts(artifact.parts)
        if parts:
            return parts[0]
    return None


async def delegate(
    agent: DiscoveredAgent, skill_id: str, args: dict, correlation_id: str | None = None
) -> dict:
    """Delega una skill a un agente remoto y devuelve su resultado.

    No lanza: cualquier fallo vuelve como `{"ok": False, "error": ...}` para
    que el orchestrator pueda reportar un resumen parcial en vez de romperse.
    """
    envelope = {"skill": skill_id, "args": args}
    safe_args = {k: v for k, v in args.items() if k != "password"}
    logger.info(
        "a2a.delegate.send", agent=agent.name, skill=skill_id, args=safe_args
    )

    headers = {"x-correlation-id": correlation_id} if correlation_id else {}
    try:
        async with httpx.AsyncClient(timeout=60, headers=headers) as hx:
            client = await create_client(
                agent=agent.card,
                client_config=ClientConfig(streaming=False, httpx_client=hx),
            )
            request = SendMessageRequest(
                message=new_data_message(envelope, role=Role.ROLE_USER)
            )

            result: dict | None = None
            async for chunk in client.send_message(request):
                artifact = _extract_artifact(chunk)
                if artifact is not None:
                    result = artifact
            await client.close()
    except Exception as e:
        logger.warning(
            "a2a.delegate.failed", agent=agent.name, skill=skill_id, error=str(e)
        )
        return {"ok": False, "skill": skill_id, "error": str(e)}

    if result is None:
        logger.warning("a2a.delegate.no_artifact", agent=agent.name, skill=skill_id)
        return {
            "ok": False,
            "skill": skill_id,
            "error": "El agente no devolvio ningun artifact",
        }

    logger.info(
        "a2a.delegate.result",
        agent=agent.name,
        skill=skill_id,
        ok=result.get("ok"),
    )
    return result
