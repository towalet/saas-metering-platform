from sqlalchemy.orm import Session
from sqlalchemy import select
from app.models.user import User
from app.core.security import hash_password

def create_user(db: Session, email: str, password: str) -> User:
    """Create a new user with the given email and password."""
    hashed_password = hash_password(password)
    user = User(email=email, password_hash=hashed_password)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

def get_user_by_email(db: Session, email: str) -> User | None:
    return db.execute(select(User).where(User.email == email)).scalar_one_or_none()
