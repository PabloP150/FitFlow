from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Notification
from app.schemas import NotificationCreate, NotificationOut

router = APIRouter(tags=["notifications"])


@router.post("/notifications", response_model=NotificationOut, status_code=201)
def create_notification(payload: NotificationCreate, db: Session = Depends(get_db)):
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
def list_notifications_for_user(user_id: int, db: Session = Depends(get_db)):
    notifications = (
        db.query(Notification)
        .filter(Notification.user_id == user_id)
        .order_by(desc(Notification.created_at))
        .all()
    )
    return notifications
