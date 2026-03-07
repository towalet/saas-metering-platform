"""Tests for /v1/events protected API."""

from fastapi.testclient import TestClient

from app.models.orgs import Org
from tests.conftest import VALID_PASSWORD


def _signup_and_login(client: TestClient, email: str) -> tuple[dict, dict]:
    resp = client.post("/auth/signup", json={"email": email, "password": VALID_PASSWORD})
    assert resp.status_code == 201
    user = resp.json()
    resp = client.post("/auth/login", data={"username": email, "password": VALID_PASSWORD})
    assert resp.status_code == 200
    token = resp.json()["access_token"]
    return user, {"Authorization": f"Bearer {token}"}


def _create_org(client: TestClient, headers: dict, name: str = "Acme Inc") -> dict:
    resp = client.post("/orgs", json={"name": name}, headers=headers)
    assert resp.status_code == 201
    return resp.json()


def _create_api_key(client: TestClient, headers: dict, org_id: int, name: str = "Test Key") -> dict:
    resp = client.post(f"/orgs/{org_id}/api-keys", json={"name": name}, headers=headers)
    assert resp.status_code == 201
    return resp.json()


class TestPostEvents:
    def test_post_event_success(self, client: TestClient, auth_headers):
        """POST /v1/events with valid API key creates event and returns 201."""
        org = _create_org(client, auth_headers)
        key = _create_api_key(client, auth_headers, org["id"])
        api_headers = {"X-API-Key": key["key"]}

        resp = client.post(
            "/v1/events",
            json={"event_type": "page_view", "data": {"url": "/home", "user_id": "u123"}},
            headers=api_headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["event_type"] == "page_view"
        assert data["payload"] == {"url": "/home", "user_id": "u123"}
        assert data["org_id"] == org["id"]
        assert "id" in data
        assert "created_at" in data

    def test_post_event_invalid_key(self, client: TestClient):
        """POST /v1/events with invalid API key returns 401."""
        resp = client.post(
            "/v1/events",
            json={"event_type": "click", "data": {}},
            headers={"X-API-Key": "smp_live_invalid"},
        )
        assert resp.status_code == 401

    def test_post_event_missing_header(self, client: TestClient):
        """POST /v1/events without X-API-Key returns 401."""
        resp = client.post("/v1/events", json={"event_type": "click", "data": {}})
        assert resp.status_code == 401

    def test_post_event_rate_limit_headers(self, client: TestClient, auth_headers):
        """Response includes X-RateLimit-* headers."""
        org = _create_org(client, auth_headers)
        key = _create_api_key(client, auth_headers, org["id"])
        api_headers = {"X-API-Key": key["key"]}

        resp = client.post(
            "/v1/events",
            json={"event_type": "test", "data": {}},
            headers=api_headers,
        )
        assert resp.status_code == 201
        assert "X-RateLimit-Limit" in resp.headers
        assert "X-RateLimit-Remaining" in resp.headers
        assert "X-RateLimit-Reset" in resp.headers


class TestGetEvents:
    def test_get_events_empty(self, client: TestClient, auth_headers):
        """GET /v1/events returns empty list when no events."""
        org = _create_org(client, auth_headers)
        key = _create_api_key(client, auth_headers, org["id"])
        api_headers = {"X-API-Key": key["key"]}

        resp = client.get("/v1/events", headers=api_headers)
        assert resp.status_code == 200
        assert resp.json() == []

    def test_get_events_returns_created(self, client: TestClient, auth_headers):
        """GET /v1/events returns events created via POST."""
        org = _create_org(client, auth_headers)
        key = _create_api_key(client, auth_headers, org["id"])
        api_headers = {"X-API-Key": key["key"]}

        client.post(
            "/v1/events",
            json={"event_type": "a", "data": {"x": 1}},
            headers=api_headers,
        )
        client.post(
            "/v1/events",
            json={"event_type": "b", "data": {"y": 2}},
            headers=api_headers,
        )

        resp = client.get("/v1/events", headers=api_headers)
        assert resp.status_code == 200
        events = resp.json()
        assert len(events) == 2
        types = {e["event_type"] for e in events}
        assert types == {"a", "b"}

    def test_get_events_org_isolation(self, client: TestClient, auth_headers):
        """Events from one org are not visible to another org's API key."""
        org1 = _create_org(client, auth_headers, "Org1")
        org2 = _create_org(client, auth_headers, "Org2")
        key1 = _create_api_key(client, auth_headers, org1["id"], "Key1")
        key2 = _create_api_key(client, auth_headers, org2["id"], "Key2")

        client.post(
            "/v1/events",
            json={"event_type": "org1_only", "data": {}},
            headers={"X-API-Key": key1["key"]},
        )

        resp = client.get("/v1/events", headers={"X-API-Key": key2["key"]})
        assert resp.status_code == 200
        assert resp.json() == []


class TestRateLimit:
    def test_rate_limit_returns_429(self, client: TestClient, auth_headers, db_session):
        """When rate limit exceeded, returns 429."""
        org = _create_org(client, auth_headers)
        key = _create_api_key(client, auth_headers, org["id"])
        api_headers = {"X-API-Key": key["key"]}

        # Set very low rate limit
        org_row = db_session.query(Org).filter(Org.id == org["id"]).first()
        org_row.rate_limit_rpm = 2
        db_session.commit()

        # First 2 requests pass
        for _ in range(2):
            resp = client.post(
                "/v1/events",
                json={"event_type": "test", "data": {}},
                headers=api_headers,
            )
            assert resp.status_code == 201

        # 3rd request is rate limited
        resp = client.post(
            "/v1/events",
            json={"event_type": "test", "data": {}},
            headers=api_headers,
        )
        assert resp.status_code == 429
        assert "Rate limit exceeded" in resp.json().get("detail", "")
