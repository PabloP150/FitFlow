from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Booking, FitnessClass
from ..schemas import ClassOut

router = APIRouter(tags=["classes"])


@router.get("/classes", response_model=list[ClassOut])
def list_classes(db: Session = Depends(get_db)):
    """Get all fitness classes with their currently taken spots."""
    classes = db.query(FitnessClass).all()

    result = []
    for cls in classes:
        spots_taken = (
            db.query(func.count(Booking.id))
            .filter(Booking.class_id == cls.id, Booking.status == "confirmed")
            .scalar()
            or 0
        )

        result.append(
            ClassOut(
                id=cls.id,
                name=cls.name,
                description=cls.description,
                start_time=cls.start_time,
                capacity=cls.capacity,
                spots_taken=spots_taken,
            )
        )

    return result
