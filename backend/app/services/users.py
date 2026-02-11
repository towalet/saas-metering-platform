from sqlalchemy.orm import Session
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from app.models.user import User
from app.core.security import hash_password


def _normalize_email(email: str) -> str:
    return email.strip().lower()

def create_user(db: Session, email: str, password: str) -> User:
    """Create a new user with the given email and password."""
    normalized_email = _normalize_email(email)
    hashed_password = hash_password(password)
    user = User(email=normalized_email, password_hash=hashed_password)
    db.add(user)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ValueError("Email already registered") from exc
    db.refresh(user)
    return user

def get_user_by_email(db: Session, email: str) -> User | None:
    normalized_email = _normalize_email(email)
    return db.execute(select(User).where(User.email == normalized_email)).scalar_one_or_none()
