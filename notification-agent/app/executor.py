"""Executor del Notification Agent (Task 5).

Recibe tareas A2A delegadas por el Orchestrator y las traduce en llamadas a
tools del servidor MCP de FitFlow.

Contrato del mensaje entrante (lo envia `orchestrator-agent/app/a2a_dispatch.py`):
un unico data part con la forma

    {"skill": "send_notification", "args": {"user_id": 1, "message": "..."}}
"""

from typing import Any

import structlog
from a2a.helpers import (
    get_data_parts,
    new_data_part,
    new_task_from_user_message,
    new_text_message,
)
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.tasks import TaskUpdater

from .agent_card import SKILL_GET_HISTORY, SKILL_SEND_NOTIFICATION
from .config import settings
from .mcp_client import call_tool

logger = structlog.get_logger(f"{settings.SERVICE_NAME}.a2a")


def _as_int(value: Any, field: str) -> int:
    """Convierte a int un valor que llego por protobuf.

    Los data parts viajan como `google.protobuf.Value`, que representa todo
    numero como double: un `user_id: 1` sale del otro lado como `1.0`. Sin
    esta coercion, la tool MCP recibiria un float y notif-svc respondaria 422.
    """
    if value is None:
        raise ValueError(f"Falta el campo requerido '{field}'")
    try:
        return int(value)
    except (TypeError, ValueError) as e:
        raise ValueError(f"El campo '{field}' debe ser un entero, llego {value!r}") from e


class NotificationAgentExecutor(AgentExecutor):
    """Ejecuta las skills del Notification Agent contra el MCP Server."""

    async def execute(
        self, context: RequestContext, event_queue: EventQueue
    ) -> None:
        # El framework exige encolar el Task antes de emitir cualquier
        # TaskStatusUpdateEvent.
        if context.current_task:
            task = context.current_task
        else:
            task = new_task_from_user_message(context.message)
            await event_queue.enqueue_event(task)

        updater = TaskUpdater(
            event_queue=event_queue, task_id=task.id, context_id=task.context_id
        )
        await updater.start_work()

        parts = get_data_parts(context.message.parts) if context.message else []
        envelope = parts[0] if parts else {}
        skill = envelope.get("skill")
        args = envelope.get("args") or {}

        logger.info("a2a.task_received", skill=skill, task_id=task.id)

        try:
            result = await self._dispatch(skill, args)
        except Exception as e:
            logger.warning("a2a.task_failed", skill=skill, task_id=task.id, error=str(e))
            await updater.add_artifact(
                parts=[new_data_part({"ok": False, "skill": skill, "error": str(e)})],
                name="result",
            )
            await updater.failed(new_text_message(f"Fallo la skill '{skill}': {e}"))
            return

        logger.info("a2a.task_completed", skill=skill, task_id=task.id)
        await updater.add_artifact(
            parts=[new_data_part({"ok": True, "skill": skill, "result": result})],
            name="result",
        )
        await updater.complete(new_text_message(f"Skill '{skill}' ejecutada."))

    async def _dispatch(self, skill: str | None, args: dict) -> Any:
        if skill == SKILL_SEND_NOTIFICATION:
            payload = {
                "user_id": _as_int(args.get("user_id"), "user_id"),
                "type": args.get("type") or "generic",
                "message": args.get("message") or "",
            }
            # booking_id es opcional: solo se manda si vino en la delegacion.
            if args.get("booking_id") is not None:
                payload["booking_id"] = _as_int(args.get("booking_id"), "booking_id")
            return await call_tool("send_notification_tool", payload)

        if skill == SKILL_GET_HISTORY:
            return await call_tool(
                "get_notification_history_tool",
                {
                    "user_id": _as_int(args.get("user_id"), "user_id"),
                    "email": args.get("email"),
                    "password": args.get("password"),
                },
            )
        raise ValueError(
            f"Skill desconocida: {skill!r}. Soportadas: "
            f"{SKILL_SEND_NOTIFICATION}, {SKILL_GET_HISTORY}"
        )

    async def cancel(
        self, context: RequestContext, event_queue: EventQueue
    ) -> None:
        """Las skills son llamadas HTTP cortas: no hay punto intermedio que abortar."""
        updater = TaskUpdater(
            event_queue=event_queue,
            task_id=context.task_id,
            context_id=context.context_id,
        )
        await updater.cancel()
