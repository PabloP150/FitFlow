"""Cliente MCP del Booking Agent (Task 5).

El agente NO llama a booking-svc por HTTP directo: habla con el servidor MCP
de FitFlow (`fitflow-mcp`) por transporte streamable-http y ejecuta sus tools.
Asi el agente "usa MCP internamente", que es lo que pide el enunciado.

Se abre una sesion MCP nueva por llamada (mismo criterio que
`fitflow-mcp/app/tools.py`, que abre un `httpx.AsyncClient()` por llamada):
el volumen es bajo y evita mantener estado de sesion entre requests.
"""

import json
from typing import Any

import structlog
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

from .config import settings

logger = structlog.get_logger(f"{settings.SERVICE_NAME}.mcp")


class McpCallError(Exception):
    """Fallo al invocar una tool MCP (red, sesion, o error del servidor)."""


def _parse_result(result: Any) -> Any:
    """Extrae el payload util de un CallToolResult.

    Ojo con las listas: cuando una tool devuelve una lista, FastMCP NO manda
    un solo bloque con un array JSON, sino UN BLOQUE POR ELEMENTO. Por eso hay
    que juntar todos los bloques y no quedarse con el primero (si no,
    `list_classes` devolveria una sola clase en vez de las cuatro).
    """
    structured = getattr(result, "structuredContent", None)
    if structured:
        # FastMCP envuelve valores no-dict bajo la clave "result".
        if isinstance(structured, dict) and set(structured.keys()) == {"result"}:
            return structured["result"]
        return structured

    values = []
    for block in getattr(result, "content", None) or []:
        text = getattr(block, "text", None)
        if text is None:
            continue
        try:
            values.append(json.loads(text))
        except json.JSONDecodeError:
            values.append(text)

    if not values:
        return None
    return values[0] if len(values) == 1 else values


@retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential_jitter(initial=0.5, max=4),
    retry=retry_if_exception_type(McpCallError),
)
async def call_tool(name: str, args: dict) -> Any:
    """Invoca una tool del servidor MCP y devuelve su resultado ya parseado.

    Reintenta con backoff porque `fitflow-mcp` puede no estar listo todavia
    cuando el agente arranca (no tiene healthcheck de compose contra el que
    sincronizar: un GET simple no valida un handshake MCP).
    """
    logger.info("mcp.call", tool=name, args={k: v for k, v in args.items() if k != "password"})
    try:
        async with streamablehttp_client(settings.MCP_SERVER_URL) as (read, write, _):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(name, args)
    except Exception as e:
        logger.warning("mcp.call_failed", tool=name, error=str(e))
        raise McpCallError(f"MCP call '{name}' failed: {e}") from e

    if getattr(result, "isError", False):
        raise McpCallError(f"MCP tool '{name}' returned an error: {result}")

    parsed = _parse_result(result)
    logger.info("mcp.result", tool=name)
    return parsed
