from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from .database import Base

# Estados posibles de PendingNotification.status
PENDING = "pending"
SENT = "sent"
FAILED = "failed"


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


class PendingNotification(Base):
    """Outbox de notificaciones (Task 3 — Resiliencia).

    Cuando la llamada a notif-svc falla incluso despues de los reintentos
    (o el circuit breaker esta abierto), la notificacion NO se pierde: se
    guarda aqui para que `app/outbox.py` (un worker en background) la
    reintente periodicamente hasta que notif-svc vuelva a estar disponible.
    Esto es lo que garantiza que una reserva nunca falle por culpa de
    notif-svc, sin sacrificar la entrega eventual de la notificacion.
    """

    __tablename__ = "pending_notifications"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False)
    type = Column(String, nullable=False)
    message = Column(String, nullable=False)
    booking_id = Column(Integer, nullable=True)
    correlation_id = Column(String, nullable=True)
    attempts = Column(Integer, default=0, nullable=False)
    status = Column(String, default=PENDING, nullable=False)  # pending | sent | failed
    created_at = Column(DateTime, default=datetime.utcnow)
    last_attempt_at = Column(DateTime, nullable=True)
