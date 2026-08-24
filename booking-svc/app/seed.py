from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from .models import FitnessClass

SEED_CLASSES = [
    {"name": "Yoga Matutino", "description": "Yoga suave para principiantes", "capacity": 20},
    {"name": "Spinning", "description": "Cardio intenso en bicicleta", "capacity": 15},
    {"name": "CrossFit", "description": "Entrenamiento funcional", "capacity": 18},
    {"name": "Pilates", "description": "Fortalecimiento y flexibilidad", "capacity": 16},
]


def seed_classes(db: Session):
    """Seed fitness classes if the DB is empty."""
    if db.query(FitnessClass).count() > 0:
        return  # Already seeded

    tomorrow = datetime.utcnow() + timedelta(days=1)

    classes = [
        FitnessClass(
            name=c["name"],
            description=c["description"],
            start_time=tomorrow.replace(hour=9 + i, minute=0, second=0, microsecond=0),
            capacity=c["capacity"],
        )
        for i, c in enumerate(SEED_CLASSES)
    ]

    db.add_all(classes)
    db.commit()
    print(f"[seed] Inserted {len(classes)} fitness classes")
