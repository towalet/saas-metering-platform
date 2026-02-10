from typing import Generator

from app.db.session import SessionLocal

def get_db() -> Generator:
    """FastAPI dependency that provides a DB session and guarantees cleanup."""
    db = SessionLocal()
    try:
        yield db
    finally:
        # Ensure the session is closed even if the request raises an error.
        db.close()
