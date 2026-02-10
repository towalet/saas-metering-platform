import os
from datetime import datetime, timedelta, timezone
from typing import Any

from jose import jwt
from passlib.context import CryptContext


# Argon2 strong password hashing scheme. passlib manages hashing/verification.
pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")


def hash_password(password: str) -> str:
    """Hash a plain-text password for storage."""
    return pwd_context.hash(password)

def verify_password(password: str, hashed_password: str) -> bool:
    """Verify a plain-text password against its stored hash."""
    return pwd_context.verify(password, hashed_password)

def create_access_token(subject: str) -> str:
    """Create a signed JWT access token for a subject (typically a user id)."""
    secret = os.getenv("JWT_SECRET", "dev-secret")
    algorithm = os.getenv("JWT_ALGORITHM", "HS256")
    expire_minutes = int(os.getenv("JWT_EXPIRE_MINUTES", "60"))

    now = datetime.now(timezone.utc)
    payload = {
        "sub": subject,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=expire_minutes)).timestamp())
    }
    return jwt.encode(payload, secret, algorithm=algorithm)

def decode_token(token: str) -> Any:
    """Decode and validate a JWT access token. Raises on invalid/expired tokens."""
    secret = os.getenv("JWT_SECRET", "dev-secret")
    algorithm = os.getenv("JWT_ALGORITHM", "HS256")
    return jwt.decode(token, secret, algorithms=[algorithm])
