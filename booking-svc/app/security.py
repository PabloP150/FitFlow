from typing import Optional

import jwt
from fastapi import Header, HTTPException
from pydantic import BaseModel


class TokenPayload(BaseModel):
    user_id: int
    exp: float


def decode_token(token: str, settings) -> TokenPayload:
    """Decode and verify a JWT token."""
    try:
        # Remove "Bearer " prefix if present
        if token.startswith("Bearer "):
            token = token[7:]

        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
        return TokenPayload(**payload)
    except jwt.InvalidTokenError as e:
        raise ValueError(f"Invalid token: {e}")


def get_current_user_id(authorization: Optional[str] = Header(None)) -> int:
    """FastAPI dependency: extract and validate user_id from the Authorization header.

    Deferred import of `settings` avoids a circular import between security.py
    and config.py at module load time.
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing authorization header")

    from .config import settings

    try:
        payload = decode_token(authorization, settings)
        return payload.user_id
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))
