from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..database import get_db

router = APIRouter(tags=["health"])


@router.get("/healthz")
def healthz():
    """Liveness check — does not touch the database."""
    return {"status": "ok"}


@router.get("/readyz")
def readyz(db: Session = Depends(get_db)):
    """Readiness check — confirms the database connection is alive."""
    try:
        db.execute(text("SELECT 1"))
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Database not ready: {e}")
    return {"status": "ready"}
