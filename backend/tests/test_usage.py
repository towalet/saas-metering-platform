"""Tests for usage metering service and usage reporting API."""

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.models.orgs import Org
from app.models.usage_event import UsageEvent
from app.services.usage import count_usage_current_month, record_usage
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


def _create_api_key(client: TestClient, headers: dict, org_id: int) -> dict:
    resp = client.post(f"/orgs/{org_id}/api-keys", json={"name": "Test Key"}, headers=headers)
    assert resp.status_code == 201
    return resp.json()


def _seed_usage_events(
    db_session,
    *,
    org_id: int,
    api_key_id: int,
    events: list[tuple[datetime, int]],
) -> None:
    for created_at, latency_ms in events:
        db_session.add(
            UsageEvent(
                api_key_id=api_key_id,
                org_id=org_id,
                method="GET",
                path="/v1/events",
                status_code=200,
                response_time_ms=latency_ms,
                created_at=created_at,
            )
        )
    db_session.commit()


def _set_monthly_quota(db_session, *, org_id: int, quota: int) -> None:
    org = db_session.query(Org).filter(Org.id == org_id).first()
    assert org is not None
    org.monthly_quota = quota
    db_session.commit()


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


class TestUsageReportingApi:
    def test_group_by_day_aggregation_math(self, client: TestClient, db_session, auth_headers):
        org = _create_org(client, auth_headers)
        key = _create_api_key(client, auth_headers, org["id"])
        _set_monthly_quota(db_session, org_id=org["id"], quota=10)
        _seed_usage_events(
            db_session,
            org_id=org["id"],
            api_key_id=key["id"],
            events=[
                (datetime(2026, 2, 1, 1, 5, tzinfo=timezone.utc), 40),
                (datetime(2026, 2, 1, 11, 30, tzinfo=timezone.utc), 50),
                (datetime(2026, 2, 2, 8, 0, tzinfo=timezone.utc), 60),
            ],
        )

        resp = client.get(
            f"/orgs/{org['id']}/usage",
            params={"from_date": "2026-02-01", "to_date": "2026-02-02", "group_by": "day"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        body = resp.json()

        assert body["org_id"] == org["id"]
        assert body["period"] == {"from": "2026-02-01", "to": "2026-02-02"}
        assert body["total_requests"] == 3
        assert body["quota_limit"] == 10
        assert body["quota_used_pct"] == 30.0
        assert body["series"] == [
            {"period": "2026-02-01", "count": 2, "avg_latency_ms": 45},
            {"period": "2026-02-02", "count": 1, "avg_latency_ms": 60},
        ]

    def test_group_by_hour(self, client: TestClient, db_session, auth_headers):
        org = _create_org(client, auth_headers)
        key = _create_api_key(client, auth_headers, org["id"])
        _seed_usage_events(
            db_session,
            org_id=org["id"],
            api_key_id=key["id"],
            events=[
                (datetime(2026, 2, 3, 10, 5, tzinfo=timezone.utc), 10),
                (datetime(2026, 2, 3, 10, 45, tzinfo=timezone.utc), 20),
                (datetime(2026, 2, 3, 11, 1, tzinfo=timezone.utc), 40),
            ],
        )

        resp = client.get(
            f"/orgs/{org['id']}/usage",
            params={"from_date": "2026-02-03", "to_date": "2026-02-03", "group_by": "hour"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["total_requests"] == 3
        assert body["series"] == [
            {"period": "2026-02-03T10:00:00Z", "count": 2, "avg_latency_ms": 15},
            {"period": "2026-02-03T11:00:00Z", "count": 1, "avg_latency_ms": 40},
        ]

    def test_group_by_month(self, client: TestClient, db_session, auth_headers):
        org = _create_org(client, auth_headers)
        key = _create_api_key(client, auth_headers, org["id"])
        _seed_usage_events(
            db_session,
            org_id=org["id"],
            api_key_id=key["id"],
            events=[
                (datetime(2026, 1, 10, 9, 0, tzinfo=timezone.utc), 30),
                (datetime(2026, 1, 25, 14, 0, tzinfo=timezone.utc), 50),
                (datetime(2026, 2, 2, 8, 0, tzinfo=timezone.utc), 20),
            ],
        )

        resp = client.get(
            f"/orgs/{org['id']}/usage",
            params={"from_date": "2026-01-01", "to_date": "2026-02-28", "group_by": "month"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["total_requests"] == 3
        assert body["series"] == [
            {"period": "2026-01", "count": 2, "avg_latency_ms": 40},
            {"period": "2026-02", "count": 1, "avg_latency_ms": 20},
        ]

    def test_defaults_to_current_month_to_date(self, client: TestClient, db_session, auth_headers):
        org = _create_org(client, auth_headers)
        key = _create_api_key(client, auth_headers, org["id"])

        today = datetime.now(timezone.utc).date()
        month_start = today.replace(day=1)
        prior_month_day = month_start - timedelta(days=1)

        _seed_usage_events(
            db_session,
            org_id=org["id"],
            api_key_id=key["id"],
            events=[
                (
                    datetime(
                        month_start.year,
                        month_start.month,
                        month_start.day,
                        12,
                        0,
                        tzinfo=timezone.utc,
                    ),
                    25,
                ),
                (
                    datetime(
                        prior_month_day.year,
                        prior_month_day.month,
                        prior_month_day.day,
                        12,
                        0,
                        tzinfo=timezone.utc,
                    ),
                    75,
                ),
            ],
        )

        resp = client.get(f"/orgs/{org['id']}/usage", headers=auth_headers)
        assert resp.status_code == 200
        body = resp.json()

        assert body["period"] == {"from": month_start.isoformat(), "to": today.isoformat()}
        assert body["total_requests"] == 1
        assert body["series"] == [
            {"period": month_start.isoformat(), "count": 1, "avg_latency_ms": 25},
        ]

    def test_member_is_forbidden(self, client: TestClient, auth_headers):
        org = _create_org(client, auth_headers)
        bob, bob_headers = _signup_and_login(client, "bob@example.com")

        resp = client.post(
            f"/orgs/{org['id']}/members",
            json={"email": bob["email"], "role": "member"},
            headers=auth_headers,
        )
        assert resp.status_code == 201

        resp = client.get(f"/orgs/{org['id']}/usage", headers=bob_headers)
        assert resp.status_code == 403

    def test_admin_can_access(self, client: TestClient, auth_headers):
        org = _create_org(client, auth_headers)
        bob, bob_headers = _signup_and_login(client, "bob-admin@example.com")

        resp = client.post(
            f"/orgs/{org['id']}/members",
            json={"email": bob["email"], "role": "admin"},
            headers=auth_headers,
        )
        assert resp.status_code == 201

        resp = client.get(f"/orgs/{org['id']}/usage", headers=bob_headers)
        assert resp.status_code == 200
        assert resp.json()["org_id"] == org["id"]

    def test_rejects_invalid_date_range(self, client: TestClient, auth_headers):
        org = _create_org(client, auth_headers)
        resp = client.get(
            f"/orgs/{org['id']}/usage",
            params={"from_date": "2026-02-10", "to_date": "2026-02-01"},
            headers=auth_headers,
        )
        assert resp.status_code == 400
