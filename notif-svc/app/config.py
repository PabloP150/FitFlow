from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- Database ---
    NOTIF_DB_USER: str
    NOTIF_DB_PASSWORD: str
    NOTIF_DB_NAME: str
    NOTIF_DB_PORT: int

    # --- Consul ---
    CONSUL_HOST: str
    CONSUL_PORT: int

    # --- Service identity ---
    SERVICE_NAME: str = "notif-svc"
    SERVICE_HOST: str = "notif-svc"
    SERVICE_PORT: int = 8002

    @property
    def DATABASE_URL(self) -> str:
        # Nota: NOTIF_DB_PORT es el puerto publicado en el HOST (mapeo en
        # docker-compose, p.ej. "${NOTIF_DB_PORT}:5432") para acceso externo
        # (debug, psql desde el host). La comunicacion interna entre
        # contenedores en la red de Docker siempre usa el puerto real de
        # Postgres dentro del contenedor (5432), sin importar a que puerto
        # del host este mapeado. Por eso aqui se usa 5432 fijo, no
        # NOTIF_DB_PORT, para conectar a "notif-db" (nombre del servicio en
        # docker-compose = hostname resoluble via la red interna de Docker).
        return (
            f"postgresql+psycopg2://{self.NOTIF_DB_USER}:{self.NOTIF_DB_PASSWORD}"
            f"@notif-db:5432/{self.NOTIF_DB_NAME}"
        )


settings = Settings()
