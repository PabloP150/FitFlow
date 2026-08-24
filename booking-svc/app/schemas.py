from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class BookingCreate(BaseModel):
    class_id: int


class BookingOut(BaseModel):
    id: int
    user_id: int
    class_id: int
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ClassOut(BaseModel):
    id: int
    name: str
    description: Optional[str]
    start_time: datetime
    capacity: int
    spots_taken: int  # calculado en tiempo de ejecución

    model_config = ConfigDict(from_attributes=True)
