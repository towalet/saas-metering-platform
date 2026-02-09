import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

def _db_url() -> str:
    user = os.getenv("POSTGRES_USER", "app")
    pwd = os.getenv("POSTGRES_PASSWORD", "app")
    host = os.getenv("POSTGRES_HOST", "db")
    port = os.getenv("POSTGRES_PORT", "5432")
    db = os.getenv("POSTGRES_DB", "appdb")
    return f"postgresql+psycopg://{user}:{pwd}@{host}:{port}/{db}"

engine = create_engine(_db_url(), pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
