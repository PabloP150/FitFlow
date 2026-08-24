import bcrypt
import jwt
from datetime import datetime, timedelta, timezone
from pydantic import BaseModel


class TokenPayload(BaseModel):
    user_id: int
    exp: float


def hash_password(password: str) -> str:
    """Hash password using bcrypt"""
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    """Verify password against hash"""
    return bcrypt.checkpw(password.encode(), hashed.encode())


def create_access_token(user_id: int, settings) -> str:
    """Create JWT token"""
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
    payload = {
        "user_id": user_id,
        "exp": expires_at.timestamp(),
    }
    return jwt.encode(
        payload,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )


def decode_token(token: str, settings) -> TokenPayload:
    """Decode and verify JWT token"""
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
        return TokenPayload(**payload)
    except jwt.InvalidTokenError as e:
        raise ValueError(f"Invalid token: {e}")
