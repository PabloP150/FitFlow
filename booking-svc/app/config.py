from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- Database ---
    BOOKING_DB_USER: str
    BOOKING_DB_PASSWORD: str
    BOOKING_DB_NAME: str
    BOOKING_DB_PORT: int

    # --- Consul ---
    CONSUL_HOST: str
    CONSUL_PORT: int

    # --- JWT ---
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str

    # --- Service identity ---
    SERVICE_NAME: str = "booking-svc"
    SERVICE_HOST: str = "booking-svc"
    SERVICE_PORT: int = 8001

    @property
    def DATABASE_URL(self) -> str:
        return (
            f"postgresql+psycopg2://{self.BOOKING_DB_USER}:{self.BOOKING_DB_PASSWORD}"
            f"@booking-db:5432/{self.BOOKING_DB_NAME}"
        )


settings = Settings()
