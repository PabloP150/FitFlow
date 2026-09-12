"""Configuracion del Notification Agent (Task 5).

A diferencia de los microservicios, este agente no tiene base de datos ni
se registra en Consul: su "registro" es el Agent Card que publica en
/.well-known/agent.json.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- Identidad del agente ---
    SERVICE_NAME: str = "notification-agent"
    SERVICE_HOST: str = "notification-agent"
    SERVICE_PORT: int = 9002

    # --- MCP ---
    # Endpoint streamable-http del servidor MCP de FitFlow. El agente lo usa
    # como cliente MCP para ejecutar las acciones reales contra notif-svc.
    MCP_SERVER_URL: str = "http://fitflow-mcp:8000/mcp"

    @property
    def AGENT_URL(self) -> str:
        return f"http://{self.SERVICE_HOST}:{self.SERVICE_PORT}"


settings = Settings()
