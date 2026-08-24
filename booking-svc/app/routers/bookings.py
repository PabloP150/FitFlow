from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Booking, FitnessClass
from ..notif_client import send_notification
from ..schemas import BookingCreate, BookingOut
from ..security import get_current_user_id

router = APIRouter(tags=["bookings"])


@router.post("/bookings", response_model=BookingOut, status_code=201)
async def create_booking(
    booking: BookingCreate,
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

    # Send notification (async, fire-and-forget — never fails the booking)
    try:
        await send_notification(
            user_id=user_id,
            notif_type="booking_confirmation",
            message=f"Tu reserva en {fitness_class.name} fue confirmada",
            booking_id=db_booking.id,
        )
    except Exception as e:
        print(f"[bookings] Notification failed but booking created: {e}")

    return db_booking


@router.get("/bookings/{booking_id}", response_model=BookingOut)
def get_booking(booking_id: int, db: Session = Depends(get_db)):
    """Get booking details (no auth required for this task)."""
    booking = db.query(Booking).filter(Booking.id == booking_id).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    return booking


@router.post("/bookings/{booking_id}/cancel", response_model=BookingOut)
async def cancel_booking(
    booking_id: int,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    """Cancel a booking (soft-cancel, requires JWT)."""
    booking = db.query(Booking).filter(Booking.id == booking_id).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    # Ownership validation (booking.user_id == user_id) se añade en Task 4.
    # Por ahora, cualquier usuario autenticado puede cancelar cualquier reserva.

    booking.status = "cancelled"
    db.commit()
    db.refresh(booking)

    # Send notification
    try:
        fitness_class = db.query(FitnessClass).filter(FitnessClass.id == booking.class_id).first()
        await send_notification(
            user_id=booking.user_id,
            notif_type="booking_cancelled",
            message=f"Tu reserva en {fitness_class.name if fitness_class else 'una clase'} fue cancelada",
            booking_id=booking_id,
        )
    except Exception as e:
        print(f"[bookings] Notification failed but booking cancelled: {e}")

    return booking
