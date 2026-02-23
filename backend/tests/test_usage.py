"""Tests for usage metering service — record and count."""

from app.services.usage import record_usage, count_usage_current_month
from app.models.usage_event import UsageEvent
from tests.conftest import VALID_PASSWORD
from fastapi.testclient import TestClient


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


def _create_api_key(client: TestClient, headers: dict, org_id: int) -> dict:
    resp = client.post(f"/orgs/{org_id}/api-keys", json={"name": "Test Key"}, headers=headers)
    assert resp.status_code == 201
    return resp.json()


class TestRecordUsage:
    def test_record_creates_row(self, db_session, client, auth_headers):
        org = _create_org(client, auth_headers)
        key = _create_api_key(client, auth_headers, org["id"])

        event = record_usage(
            db_session,
            api_key_id=key["id"],
            org_id=org["id"],
            method="POST",
            path="/v1/events",
            status_code=200,
            response_time_ms=42,
        )
        assert event.id is not None
        assert event.org_id == org["id"]
        assert event.method == "POST"
        assert event.response_time_ms == 42

    def test_record_multiple(self, db_session, client, auth_headers):
        org = _create_org(client, auth_headers)
        key = _create_api_key(client, auth_headers, org["id"])

        for i in range(5):
            record_usage(
                db_session,
                api_key_id=key["id"],
                org_id=org["id"],
                method="GET",
                path="/v1/events",
                status_code=200,
                response_time_ms=10 + i,
            )

        rows = db_session.query(UsageEvent).filter_by(org_id=org["id"]).all()
        assert len(rows) == 5


class TestCountUsage:
    def test_count_current_month(self, db_session, client, auth_headers):
        org = _create_org(client, auth_headers)
        key = _create_api_key(client, auth_headers, org["id"])

        for _ in range(3):
            record_usage(
                db_session,
                api_key_id=key["id"],
                org_id=org["id"],
                method="POST",
                path="/v1/events",
                status_code=200,
                response_time_ms=10,
            )

        count = count_usage_current_month(db_session, org["id"])
        assert count == 3

    def test_count_zero_when_empty(self, db_session, client, auth_headers):
        org = _create_org(client, auth_headers)
        count = count_usage_current_month(db_session, org["id"])
        assert count == 0

    def test_count_isolates_orgs(self, db_session, client, auth_headers):
        """Usage for org A should not appear in org B's count."""
        org_a = _create_org(client, auth_headers, "Org A")
        key_a = _create_api_key(client, auth_headers, org_a["id"])

        _, bob_headers = _signup_and_login(client, "bob@example.com")
        org_b = _create_org(client, bob_headers, "Org B")

        for _ in range(4):
            record_usage(
                db_session,
                api_key_id=key_a["id"],
                org_id=org_a["id"],
                method="POST",
                path="/v1/events",
                status_code=200,
                response_time_ms=10,
            )

        assert count_usage_current_month(db_session, org_a["id"]) == 4
        assert count_usage_current_month(db_session, org_b["id"]) == 0
