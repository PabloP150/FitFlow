from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    CONSUL_HOST: str = "localhost"
    CONSUL_PORT: int = 8500
    MCP_RUN_MODE: str = "local"  # "local" o "docker"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
