import os
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import APIKeyHeader
from jose import jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.db.deps import get_db


# Argon2 strong password hashing scheme. passlib manages hashing/verification.
pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")

# Header scheme for API key authentication -- integrates with OpenAPI docs.
_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


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

# API Key authentication dependency 
def get_current_api_key(
    raw_key: str | None = Security(_api_key_header),
    db: Session = Depends(get_db),
):
    """
    FastAPI dependency that authenticates requests via the X-API-Key header.

    Flow:
      1. Read X-API-Key header (returns None if missing thanks to auto_error=False).
      2. SHA-256 hash it.
      3. Look up the hash in the api_keys table.
      4. If not found, revoked, or expired -> 401.
      5. Otherwise return the ApiKey row so the endpoint knows which org is calling.

    Usage in an endpoint:
        @router.get("/something")
        def my_endpoint(api_key: ApiKey = Depends(get_current_api_key)):
            ...
    """
    from app.services.api_keys import hash_key, get_key_by_hash  # avoid circular import

    if not raw_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-API-Key header",
        )

    key_hash = hash_key(raw_key)
    api_key = get_key_by_hash(db, key_hash)

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or revoked API key",
        )

    return api_key
