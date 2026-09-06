"""Validacion de JWT para notif-svc (Task 4 — Seguridad).

Espejo del `security.py` de booking-svc: solo se usa para proteger
`GET /notifications/user/{user_id}` (historial de notificaciones de un
usuario), de forma que un usuario autenticado solo pueda ver sus propias
notificaciones. `POST /notifications` (llamado internamente por
booking-svc) queda sin auth por ahora — es trafico servicio-a-servicio, no
de un cliente final.
"""

from typing import Optional

import jwt
from fastapi import Header, HTTPException
from pydantic import BaseModel, ValidationError


class TokenPayload(BaseModel):
    user_id: int
    exp: float


def decode_token(token: str, settings) -> TokenPayload:
    """Decode and verify a JWT token."""
    try:
        if token.startswith("Bearer "):
            token = token[7:]

        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
        return TokenPayload(**payload)
    except (jwt.InvalidTokenError, ValidationError) as e:
        raise ValueError(f"Invalid token: {e}")


def get_current_user_id(authorization: Optional[str] = Header(None)) -> int:
    """FastAPI dependency: extrae y valida el user_id del header Authorization."""
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing authorization header")

    from .config import settings

    try:
        payload = decode_token(authorization, settings)
        return payload.user_id
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))
