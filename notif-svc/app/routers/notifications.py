from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Notification
from app.schemas import NotificationCreate, NotificationOut
from app.security import get_current_user_id

router = APIRouter(tags=["notifications"])


@router.post("/notifications", response_model=NotificationOut, status_code=201)
def create_notification(payload: NotificationCreate, db: Session = Depends(get_db)):
    """Registrar una notificacion. Llamado internamente por booking-svc
    (servicio-a-servicio); no requiere JWT de usuario final."""
    notification = Notification(
        user_id=payload.user_id,
        type=payload.type,
        message=payload.message,
        booking_id=payload.booking_id,
    )
    db.add(notification)
    db.commit()
    db.refresh(notification)
    return notification


@router.get("/notifications/user/{user_id}", response_model=List[NotificationOut])
def list_notifications_for_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user_id: int = Depends(get_current_user_id),
):
    """Historial de notificaciones de un usuario (requiere JWT; ownership:
    solo el propio usuario puede ver sus notificaciones)."""
    if current_user_id != user_id:
        raise HTTPException(status_code=403, detail="Not authorized to view these notifications")

    notifications = (
        db.query(Notification)
        .filter(Notification.user_id == user_id)
        .order_by(desc(Notification.created_at))
        .all()
    )
    return notifications
