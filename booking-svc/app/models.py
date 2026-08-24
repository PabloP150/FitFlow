from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from .database import Base


class FitnessClass(Base):
    __tablename__ = "classes"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    description = Column(String, nullable=True)
    start_time = Column(DateTime, nullable=False)
    capacity = Column(Integer, nullable=False)


class Booking(Base):
    __tablename__ = "bookings"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False)  # sin FK, solo valor de referencia
    class_id = Column(Integer, ForeignKey("classes.id"), nullable=False)
    status = Column(String, default="confirmed")  # "confirmed" | "cancelled"
    created_at = Column(DateTime, default=datetime.utcnow)

    fitness_class = relationship("FitnessClass")
