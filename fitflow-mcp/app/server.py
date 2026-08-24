"""
MCP Server para FitFlow — transporte stdio para Claude Desktop

Uso local:
    python -m app.server
    (ejecutar desde la carpeta fitflow-mcp/, con las dependencias de
    requirements.txt instaladas y Consul accesible en CONSUL_HOST:CONSUL_PORT)

Configuración en claude_desktop_config.json:
{
  "mcpServers": {
    "fitflow": {
      "command": "python",
      "args": ["/path/to/Proyecto/fitflow-mcp/app/server.py"],
      "env": {
        "CONSUL_HOST": "localhost",
        "CONSUL_PORT": "8500",
        "MCP_RUN_MODE": "local"
      }
    }
  }
}
"""

import sys
from pathlib import Path

from mcp.server.fastmcp import FastMCP

# Claude Desktop invoca este archivo directamente por ruta absoluta
# (python /path/to/fitflow-mcp/app/server.py), no como módulo. En ese modo
# __package__ es None/"" y el import relativo `from .tools import ...`
# falla con "attempted relative import with no known parent package".
# Para soportar ambos modos de ejecución (directo y `python -m app.server`,
# usado por el Dockerfile), agregamos la raíz del proyecto (el padre de
# app/) a sys.path cuando se detecta ejecución directa, y usamos el import
# absoluto correspondiente.
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from app.tools import get_available_classes, create_booking, cancel_booking
else:
    from .tools import get_available_classes, create_booking, cancel_booking

# Create MCP server instance
mcp = FastMCP("fitflow", "FitFlow MCP Server para Claude Desktop")


# Register tools
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


# Main entry point
if __name__ == "__main__":
    # Run on stdio transport (for Claude Desktop)
    mcp.run(transport="stdio")
