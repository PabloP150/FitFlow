"""Booking Agent — servidor A2A (Task 5).

Expone las skills del agente por el protocolo A2A (JSON-RPC) y publica su
Agent Card para que el Orchestrator lo descubra.

El Agent Card se sirve en DOS rutas:
  - /.well-known/agent-card.json  -> default del SDK (A2A v1.0)
  - /.well-known/agent.json       -> la ruta que especifica el enunciado
Ambas devuelven exactamente el mismo JSON.
"""

import structlog
import uvicorn
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.routes import (
    add_a2a_routes_to_fastapi,
    create_agent_card_routes,
    create_jsonrpc_routes,
)
from a2a.server.tasks import InMemoryTaskStore
from fastapi import FastAPI

from .agent_card import build_agent_card
from .config import settings
from .executor import BookingAgentExecutor
from .logging_config import configure_logging
from .middleware import CorrelationIdMiddleware

configure_logging(settings.SERVICE_NAME)
logger = structlog.get_logger(settings.SERVICE_NAME)

AGENT_CARD = build_agent_card()

request_handler = DefaultRequestHandler(
    agent_executor=BookingAgentExecutor(),
    task_store=InMemoryTaskStore(),
    agent_card=AGENT_CARD,
)

app = FastAPI(title=settings.SERVICE_NAME)
app.add_middleware(CorrelationIdMiddleware)


@app.get("/healthz", tags=["health"])
def healthz():
    """Liveness — sin dependencias externas (lo usa el healthcheck de compose)."""
    return {"status": "ok"}


add_a2a_routes_to_fastapi(
    app,
    agent_card_routes=[
        *create_agent_card_routes(AGENT_CARD),
        *create_agent_card_routes(AGENT_CARD, card_url="/.well-known/agent.json"),
    ],
    jsonrpc_routes=create_jsonrpc_routes(request_handler, rpc_url="/"),
)

logger.info(
    "agent.ready",
    agent=AGENT_CARD.name,
    skills=[s.id for s in AGENT_CARD.skills],
    url=settings.AGENT_URL,
)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=settings.SERVICE_PORT)
