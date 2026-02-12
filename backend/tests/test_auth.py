"""Tests for /auth endpoints - signup, login, and /me."""

from fastapi.testclient import TestClient

from tests.conftest import VALID_PASSWORD


# Signup endpoint
class TestSignup:
    def test_signup_success(self, client: TestClient):
        resp = client.post("/auth/signup", json={"email": "new@example.com", "password": VALID_PASSWORD})
        assert resp.status_code == 201
        body = resp.json()
        assert body["email"] == "new@example.com"
        assert "id" in body
        # password hash must never leak
        assert "password_hash" not in body

    def test_signup_duplicate_email(self, client: TestClient, registered_user):
        resp = client.post(
            "/auth/signup",
            json={"email": registered_user["email"], "password": VALID_PASSWORD},
        )
        assert resp.status_code == 400
        assert "already registered" in resp.json()["detail"].lower()

    def test_signup_password_too_short(self, client: TestClient):
        resp = client.post("/auth/signup", json={"email": "short@example.com", "password": "short"})
        assert resp.status_code == 422  # Pydantic validation error

    def test_signup_invalid_email(self, client: TestClient):
        resp = client.post("/auth/signup", json={"email": "not-an-email", "password": VALID_PASSWORD})
        assert resp.status_code == 422

    def test_signup_normalizes_email(self, client: TestClient):
        resp = client.post("/auth/signup", json={"email": "  UPPER@Example.COM  ", "password": VALID_PASSWORD})
        assert resp.status_code == 201
        assert resp.json()["email"] == "upper@example.com"


# Login endpoint
class TestLogin:
    def test_login_success(self, client: TestClient, registered_user):
        resp = client.post(
            "/auth/login",
            data={"username": registered_user["email"], "password": registered_user["password"]},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "access_token" in body
        assert body["token_type"] == "bearer"

    def test_login_wrong_password(self, client: TestClient, registered_user):
        resp = client.post(
            "/auth/login",
            data={"username": registered_user["email"], "password": "wrong-password"},
        )
        assert resp.status_code == 401
        assert "invalid credentials" in resp.json()["detail"].lower()

    def test_login_nonexistent_user(self, client: TestClient):
        resp = client.post(
            "/auth/login",
            data={"username": "ghost@example.com", "password": VALID_PASSWORD},
        )
        assert resp.status_code == 401


# /me endpoint
class TestMe:
    def test_me_authenticated(self, client: TestClient, auth_headers, registered_user):
        resp = client.get("/auth/me", headers=auth_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["email"] == registered_user["email"]
        assert body["id"] == registered_user["id"]

    def test_me_no_token(self, client: TestClient):
        resp = client.get("/auth/me")
        assert resp.status_code == 401

    def test_me_invalid_token(self, client: TestClient):
        resp = client.get("/auth/me", headers={"Authorization": "Bearer garbage.token.here"})
        assert resp.status_code == 401

