"""
MCP Server para FitFlow — transporte HTTP (para usar dentro de docker-compose)

Uso en docker:
    python -m app.server_http

Este es un transporte alterno al stdio, permitiendo que otros clientes MCP se conecten
remotamente. Desde Task 5 es el transporte que usan booking-agent y
notification-agent para ejecutar acciones reales vía MCP.
"""

import sys
from pathlib import Path

from mcp.server.fastmcp import FastMCP

# Ver la nota equivalente en server.py: soporta tanto ejecución directa
# (python app/server_http.py) como ejecución como módulo
# (python -m app.server_http, usado por defecto en el perfil docker "http").
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from app.tools import (
        cancel_booking,
        create_booking,
        get_available_classes,
        get_notification_history,
        send_notification,
    )
else:
    from .tools import (
        cancel_booking,
        create_booking,
        get_available_classes,
        get_notification_history,
        send_notification,
    )

mcp = FastMCP("fitflow", "FitFlow MCP Server (HTTP transport)")


@mcp.tool()
async def get_available_classes_tool() -> list:
    """Get list of available fitness classes with available spots"""
    return await get_available_classes()


@mcp.tool()
async def create_booking_tool(class_id: int, email: str, password: str) -> dict:
    """Create a fitness class booking. Login with email and password."""
    return await create_booking(class_id, email, password)


@mcp.tool()
async def cancel_booking_tool(booking_id: int, email: str, password: str) -> dict:
    """Cancel a fitness class booking. Login with email and password."""
    return await cancel_booking(booking_id, email, password)


@mcp.tool()
async def send_notification_tool(
    user_id: int, type: str, message: str, booking_id: int | None = None
) -> dict:
    """Send a notification to a user. Service-to-service call, no login needed."""
    return await send_notification(user_id, type, message, booking_id)


@mcp.tool()
async def get_notification_history_tool(
    user_id: int, email: str, password: str
) -> list:
    """Get a user's notification history. Login with that user's email and password."""
    return await get_notification_history(user_id, email, password)


if __name__ == "__main__":
    # Run on Streamable HTTP transport (para docker, puerto 8000)
    # Permite que otros clientes se conecten vía HTTP
    mcp.run(transport="streamable-http")
