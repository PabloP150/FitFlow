"""Configuracion del Orchestrator Agent (Task 5)."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- Identidad ---
    SERVICE_NAME: str = "orchestrator-agent"
    SERVICE_HOST: str = "orchestrator-agent"
    SERVICE_PORT: int = 9000

    # --- Agentes a descubrir via Agent Card ---
    BOOKING_AGENT_URL: str = "http://booking-agent:9001"
    NOTIFICATION_AGENT_URL: str = "http://notification-agent:9002"

    # --- Gemini (NLU) ---
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-2.5-flash"

    # --- Consul ---
    # El orchestrator NO registra agentes al arrancar: solo cuando se pulsa el
    # boton del dashboard (ver consul_publish.py).
    CONSUL_HOST: str = "consul"
    CONSUL_PORT: int = 8500

    @property
    def AGENT_URLS(self) -> list[str]:
        return [self.BOOKING_AGENT_URL, self.NOTIFICATION_AGENT_URL]


settings = Settings()
