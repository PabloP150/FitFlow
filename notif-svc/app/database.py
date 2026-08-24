from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.config import settings

engine = create_engine(settings.DATABASE_URL, echo=False)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)

Base = declarative_base()


def get_db():
    """FastAPI dependency: entrega una sesion de DB y la cierra al terminar."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
