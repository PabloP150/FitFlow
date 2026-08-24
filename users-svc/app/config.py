from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- Database ---
    USERS_DB_USER: str
    USERS_DB_PASSWORD: str
    USERS_DB_NAME: str
    USERS_DB_PORT: int

    # --- Consul ---
    CONSUL_HOST: str
    CONSUL_PORT: int

    # --- JWT ---
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str
    JWT_EXPIRE_MINUTES: int

    # --- Service identity ---
    SERVICE_NAME: str = "users-svc"
    SERVICE_HOST: str = "users-svc"
    SERVICE_PORT: int = 8003

    @property
    def DATABASE_URL(self) -> str:
        return (
            f"postgresql+psycopg2://{self.USERS_DB_USER}:{self.USERS_DB_PASSWORD}"
            f"@users-db:5432/{self.USERS_DB_NAME}"
        )


settings = Settings()
