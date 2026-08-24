from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..database import get_db

router = APIRouter(tags=["health"])


@router.get("/healthz")
def healthz():
    """Simple liveness check."""
    return {"status": "ok"}


@router.get("/readyz")
def readyz(db: Session = Depends(get_db)):
    """Readiness check: verifies DB connectivity."""
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database not ready",
        )
    return {"status": "ok"}
