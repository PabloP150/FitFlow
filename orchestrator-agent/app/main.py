"""Orchestrator Agent (Task 5).

Punto de entrada de la red de agentes. Recibe una instruccion en lenguaje
natural, decide con Gemini que skills hay que ejecutar, descubre que agente
ofrece cada una (via Agent Card) y les delega el trabajo por protocolo A2A.

A diferencia de booking-agent y notification-agent, este no es un servidor
A2A sino un *cliente* A2A: por eso es una app FastAPI normal.
"""

from pathlib import Path

import structlog
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from . import consul_publish
from .a2a_dispatch import delegate
from .agent_registry import agent_for_skill, discover_agents, known_agents
from .config import settings
from .logging_config import configure_logging
from .middleware import CorrelationIdMiddleware
from .nlu_gemini import plan

configure_logging(settings.SERVICE_NAME)
logger = structlog.get_logger(settings.SERVICE_NAME)

STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(title=settings.SERVICE_NAME)
app.add_middleware(CorrelationIdMiddleware)


class InstructRequest(BaseModel):
    instruction: str
    email: str
    password: str


@app.get("/healthz", tags=["health"])
def healthz():
    """Liveness — sin dependencias externas."""
    return {"status": "ok"}


@app.get("/readyz", tags=["health"])
async def readyz():
    """Readiness — confirma que al menos un agente es descubrible."""
    agents = await discover_agents()
    if not agents:
        return JSONResponse(
            status_code=503,
            content={"status": "not ready", "detail": "ningun agente descubierto"},
        )
    return {"status": "ready", "agents": [a.name for a in agents]}


@app.get("/", include_in_schema=False)
def dashboard():
    """Dashboard con el boton de descubrimiento (ver static/index.html)."""
    return FileResponse(STATIC_DIR / "index.html")


@app.post("/agents/discover", tags=["a2a"])
async def agents_discover():
    """Descubre los agentes via Agent Card y los publica en Consul.

    Esto es lo que dispara el boton del dashboard. Antes de llamarlo, los
    agentes NO existen para Consul; despues, aparecen en su UI en verde.
    """
    agents = await discover_agents(force=True)
    published = consul_publish.publish_agents(agents)
    return {
        "discovered": [a.to_dict() for a in agents],
        "published_to_consul": published,
        "consul_ui": "http://localhost:8500/ui/dc1/services",
    }


@app.post("/agents/reset", tags=["a2a"])
async def agents_reset():
    """Quita los agentes de Consul, dejandolo como antes del descubrimiento.

    Permite repetir la demo del boton cuantas veces haga falta (util al
    grabar el video).
    """
    agents = await discover_agents()
    removed = consul_publish.unpublish_agents(agents)
    return {"removed_from_consul": removed}


@app.get("/agents", tags=["a2a"])
async def agents_list():
    """Agentes actualmente conocidos (descubre si aun no se ha hecho)."""
    agents = await discover_agents()
    return {"agents": [a.to_dict() for a in agents]}


def _inject_args(
    skill_id: str, args: dict, body: InstructRequest, ctx: dict
) -> dict:
    """Completa los argumentos que Gemini no produce.

    Las credenciales vienen del request, no del lenguaje natural. Los ids
    derivados (user_id, booking_id) vienen del resultado de un paso anterior
    de la misma instruccion — asi "reserva y avisame" encadena correctamente.
    """
    args = dict(args)
    if skill_id in ("create_booking", "cancel_booking", "get_history"):
        args["email"] = body.email
        args["password"] = body.password
    if skill_id in ("send_notification", "get_history") and "user_id" not in args:
        if ctx.get("user_id") is not None:
            args["user_id"] = ctx["user_id"]
    if skill_id == "send_notification" and ctx.get("booking_id") is not None:
        args.setdefault("booking_id", ctx["booking_id"])
    if skill_id == "cancel_booking" and "booking_id" not in args:
        if ctx.get("booking_id") is not None:
            args["booking_id"] = ctx["booking_id"]
    return args


def _absorb_result(skill_id: str, result: dict, ctx: dict) -> None:
    """Extrae del resultado los ids que pasos posteriores puedan necesitar."""
    payload = result.get("result")
    if not isinstance(payload, dict):
        return
    if skill_id == "create_booking":
        if payload.get("user_id") is not None:
            ctx["user_id"] = payload["user_id"]
        if payload.get("id") is not None:
            ctx["booking_id"] = payload["id"]


async def _class_context() -> str:
    """Pide la lista de clases al Booking Agent para aterrizar el prompt.

    Sin esto Gemini no podria mapear "yoga" a un class_id real. Se obtiene por
    la misma via A2A que todo lo demas, no por HTTP directo a booking-svc.
    """
    agent = agent_for_skill("list_classes")
    if agent is None:
        return ""
    result = await delegate(agent, "list_classes", {})
    if not result.get("ok"):
        return ""
    return f"Clases disponibles en FitFlow (JSON):\n{result.get('result')}"


@app.post("/instruct", tags=["a2a"])
async def instruct(body: InstructRequest, request: Request):
    """Ejecuta una instruccion en lenguaje natural de punta a punta."""
    correlation_id = getattr(request.state, "correlation_id", None)

    agents = await discover_agents()
    if not agents:
        return JSONResponse(
            status_code=503,
            content={"error": "No se pudo descubrir ningun agente via Agent Card"},
        )

    # Catalogo de skills descubiertas (dinamico, desde los Agent Cards).
    skills: dict[str, str] = {}
    for agent in agents:
        skills.update(agent.skills)

    context = await _class_context()

    try:
        decisions = await plan(body.instruction, skills, context)
    except Exception as e:
        logger.warning("instruct.nlu_failed", error=str(e))
        return JSONResponse(status_code=502, content={"error": str(e)})

    if not decisions:
        return {
            "instruction": body.instruction,
            "steps": [],
            "summary": "Gemini no identifico ninguna accion que ejecutar.",
        }

    ctx: dict = {}
    steps = []
    for skill_id, raw_args in decisions:
        agent = agent_for_skill(skill_id)
        if agent is None:
            steps.append(
                {
                    "skill": skill_id,
                    "ok": False,
                    "error": f"Ningun agente descubierto ofrece la skill '{skill_id}'",
                }
            )
            continue

        args = _inject_args(skill_id, raw_args, body, ctx)
        result = await delegate(agent, skill_id, args, correlation_id=correlation_id)
        _absorb_result(skill_id, result, ctx)

        steps.append(
            {
                "skill": skill_id,
                "agent": agent.name,
                "ok": bool(result.get("ok")),
                "result": result.get("result"),
                "error": result.get("error"),
            }
        )

    ok_count = sum(1 for s in steps if s["ok"])
    return {
        "instruction": body.instruction,
        "correlation_id": correlation_id,
        "steps": steps,
        "summary": f"{ok_count}/{len(steps)} skills ejecutadas correctamente.",
    }


logger.info("orchestrator.ready", agents=settings.AGENT_URLS)
