from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Booking, FitnessClass
from ..notif_client import send_notification
from ..schemas import BookingCreate, BookingOut
from ..security import get_current_user_id

router = APIRouter(tags=["bookings"])


def _correlation_id(request: Request) -> str | None:
    """Lee el correlation id que `CorrelationIdMiddleware` guardo en request.state,
    para reenviarlo en la llamada saliente a notif-svc y mantener un mismo id
    de rastreo de punta a punta."""
    return getattr(request.state, "correlation_id", None)


@router.post("/bookings", response_model=BookingOut, status_code=201)
async def create_booking(
    booking: BookingCreate,
    request: Request,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    """Create a new booking (requires JWT)."""
    # Check class exists
    fitness_class = db.query(FitnessClass).filter(FitnessClass.id == booking.class_id).first()
    if not fitness_class:
        raise HTTPException(status_code=404, detail="Class not found")

    # Check capacity
    booked_count = (
        db.query(func.count(Booking.id))
        .filter(Booking.class_id == booking.class_id, Booking.status == "confirmed")
        .scalar()
        or 0
    )

    if booked_count >= fitness_class.capacity:
        raise HTTPException(status_code=409, detail="Class is full")

    # Create booking
    db_booking = Booking(user_id=user_id, class_id=booking.class_id)
    db.add(db_booking)
    db.commit()
    db.refresh(db_booking)

    # Send notification. Resiliente: reintentos + circuit breaker + outbox
    # (ver notif_client.py) — nunca lanza, asi que nunca puede tumbar una
    # reserva ya creada.
    await send_notification(
        db=db,
        user_id=user_id,
        notif_type="booking_confirmation",
        message=f"Tu reserva en {fitness_class.name} fue confirmada",
        booking_id=db_booking.id,
        correlation_id=_correlation_id(request),
    )

    return db_booking


@router.get("/bookings/{booking_id}", response_model=BookingOut)
def get_booking(
    booking_id: int,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    """Get booking details (requires JWT; solo el dueno de la reserva puede verla)."""
    booking = db.query(Booking).filter(Booking.id == booking_id).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    if booking.user_id != user_id:
        raise HTTPException(status_code=403, detail="Not authorized to view this booking")

    return booking


@router.post("/bookings/{booking_id}/cancel", response_model=BookingOut)
async def cancel_booking(
    booking_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    """Cancel a booking (soft-cancel, requires JWT; solo el dueno puede cancelarla)."""
    booking = db.query(Booking).filter(Booking.id == booking_id).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    if booking.user_id != user_id:
        raise HTTPException(status_code=403, detail="Not authorized to cancel this booking")

    booking.status = "cancelled"
    db.commit()
    db.refresh(booking)

    fitness_class = db.query(FitnessClass).filter(FitnessClass.id == booking.class_id).first()
    await send_notification(
        db=db,
        user_id=booking.user_id,
        notif_type="booking_cancelled",
        message=f"Tu reserva en {fitness_class.name if fitness_class else 'una clase'} fue cancelada",
        booking_id=booking_id,
        correlation_id=_correlation_id(request),
    )

    return booking
