"""Tests for the quota enforcement."""

from datetime import datetime, timezone

from tests.conftest import VALID_PASSWORD
from fastapi.testclient import TestClient
from app.models.orgs import Org

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

class TestQuotaEnforcement:
    def test_monthly_quota_blocks_on_fourth_request(self, client: TestClient, db_session):
        _, auth_headers = _signup_and_login(client, "quota@example.com")
        org = _create_org(client, auth_headers)
        key = _create_api_key(client, auth_headers, org["id"])

        # Set a low monthly quota for this org
        org_row = db_session.query(Org).filter(Org.id == org["id"]).first()
        org_row.monthly_quota = 3
        db_session.commit()

        api_headers = {"X-API-Key": key["key"]}

        # First 3 requests pass
        for _ in range(3):
            resp = client.get("/test/api-key-check", headers=api_headers)
            assert resp.status_code == 200

        # 4th request is blocked
        resp = client.get("/test/api-key-check", headers=api_headers)
        assert resp.status_code == 429

        body = resp.json()
        assert body["detail"] == "Monthly quota exceeded"
        assert body["limit"] == 3
        assert body["used"] == 3
        resets_at = datetime.fromisoformat(body["resets_at"].replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        if now.month == 12:
            expected_year, expected_month = now.year + 1, 1
        else:
            expected_year, expected_month = now.year, now.month + 1
        assert resets_at == datetime(expected_year, expected_month, 1, tzinfo=timezone.utc)
