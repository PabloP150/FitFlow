from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String

from app.database import Base


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False)
    type = Column(String, nullable=False)  # "booking_confirmation", "booking_cancelled", "generic"
    message = Column(String, nullable=False)
    booking_id = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
