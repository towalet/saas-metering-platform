"""
Shared test fixtures.

Uses an in-process SQLite database so tests run fast and don't
need Docker / Postgres.
"""

import pytest
from fastapi import Depends
from sqlalchemy import create_engine, StaticPool
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from app.db.base import Base
from app.db.deps import get_db
from app.main import app
from app.models.api_key import ApiKey
from app.core.security import get_current_api_key

# In-memory SQLite engine shared across a single test 
SQLITE_URL = "sqlite://"

# Test-only route to verify API key authentication 
# This tiny endpoint exists solely so tests can verify X-API-Key auth
# works end-to-end, without depending on /v1/events (built in Phase 6).

@app.get("/test/api-key-check", tags=["test"], include_in_schema=False)
def _test_api_key_check(api_key: ApiKey = Depends(get_current_api_key)):
    return {"org_id": api_key.org_id, "key_id": api_key.id}


@pytest.fixture()
def db_session():
    """Yield a SQLAlchemy session backed by a fresh in-memory SQLite DB."""
    engine = create_engine(
        SQLITE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    session = TestingSession()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def client(db_session):
    """FastAPI TestClient with the DB dependency overridden."""

    def _override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as tc:
        yield tc
    app.dependency_overrides.clear()


# Auth helper fixtures
VALID_PASSWORD = "supersecure10"  # meets the 10-char minimum


@pytest.fixture()
def registered_user(client: TestClient) -> dict:
    """Register a user and return {"email": ..., "password": ..., "id": ...}."""
    email = "alice@example.com"
    resp = client.post("/auth/signup", json={"email": email, "password": VALID_PASSWORD})
    assert resp.status_code == 201
    data = resp.json()
    return {"email": email, "password": VALID_PASSWORD, "id": data["id"]}


@pytest.fixture()
def auth_headers(client: TestClient, registered_user: dict) -> dict:
    """Return Authorization headers for the registered user."""
    resp = client.post(
        "/auth/login",
        data={"username": registered_user["email"], "password": registered_user["password"]},
    )
    assert resp.status_code == 200
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}

