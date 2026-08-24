from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class NotificationCreate(BaseModel):
    user_id: int
    type: str
    message: str
    booking_id: Optional[int] = None


class NotificationOut(BaseModel):
    id: int
    user_id: int
    type: str
    message: str
    booking_id: Optional[int]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
