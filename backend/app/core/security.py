import os
from datetime import datetime, timedelta, timezone
from typing import Any

from jose import jwt
from passlib.context import CryptContext


# Argon2 strong password hashing scheme. passlib manages hashing/verification.
pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")


def _is_production() -> bool:
    return os.getenv("APP_ENV", "").lower() in {"prod", "production"}

def _get_jwt_secret() -> str:
    secret = os.getenv("JWT_SECRET", "")
    if _is_production():
        if not secret or secret in {"dev-secret", "change-me-in-dev"}:
            raise RuntimeError("JWT_SECRET must be set to a strong value in production")
    return secret or "dev-secret"

def _get_jwt_algorithm() -> str:
    return os.getenv("JWT_ALGORITHM", "HS256")

def _get_jwt_expire_minutes() -> int:
    raw = os.getenv("JWT_EXPIRES_MINUTES") or os.getenv("JWT_EXPIRE_MINUTES") or "60"
    try:
        value = int(raw)
    except ValueError as exc:
        raise RuntimeError("JWT_EXPIRES_MINUTES must be an integer") from exc
    if value <= 0:
        raise RuntimeError("JWT_EXPIRES_MINUTES must be positive")
    return value


def hash_password(password: str) -> str:
    """Hash a plain-text password for storage."""
    return pwd_context.hash(password)

def verify_password(password: str, hashed_password: str) -> bool:
    """Verify a plain-text password against its stored hash."""
    return pwd_context.verify(password, hashed_password)

def create_access_token(subject: str) -> str:
    """Create a signed JWT access token for a subject (typically a user id)."""
    secret = _get_jwt_secret()
    algorithm = _get_jwt_algorithm()
    expire_minutes = _get_jwt_expire_minutes()

    now = datetime.now(timezone.utc)
    payload = {
        "sub": subject,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=expire_minutes)).timestamp())
    }
    return jwt.encode(payload, secret, algorithm=algorithm)

def decode_token(token: str) -> Any:
    """Decode and validate a JWT access token. Raises on invalid/expired tokens."""
    secret = _get_jwt_secret()
    algorithm = _get_jwt_algorithm()
    return jwt.decode(token, secret, algorithms=[algorithm])
