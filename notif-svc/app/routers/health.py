from fastapi import APIRouter, Response
from sqlalchemy import text

from app.database import SessionLocal

router = APIRouter(tags=["health"])


@router.get("/healthz")
def healthz():
    """Liveness check: siempre 200 si el proceso esta corriendo."""
    return {"status": "ok"}


@router.get("/readyz")
def readyz(response: Response):
    """Readiness check: 200 si la DB responde, 503 si no."""
    try:
        db = SessionLocal()
        try:
            db.execute(text("SELECT 1"))
        finally:
            db.close()
        return {"status": "ok"}
    except Exception as e:
        response.status_code = 503
        return {"status": "error", "detail": str(e)}
