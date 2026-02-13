"""Tests for API key management and API key authentication."""

from fastapi.testclient import TestClient

from tests.conftest import VALID_PASSWORD


# Helpers
def _signup_and_login(client: TestClient, email: str) -> tuple[dict, dict]:
    """Register a user and return (user_data, auth_headers)."""
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


# Create API Key 
class TestCreateApiKey:
    def test_create_key_returns_plaintext(self, client: TestClient, auth_headers):
        """Creating a key should return the full plaintext key exactly once."""
        org = _create_org(client, auth_headers)
        key_data = _create_api_key(client, auth_headers, org["id"])

        assert "key" in key_data  # plaintext is present in creation response
        assert key_data["key"].startswith("smp_live_")
        assert len(key_data["key"]) > 40  # prefix + 64 hex chars
        assert "key_prefix" in key_data
        assert key_data["name"] == "Test Key"

    def test_create_key_unauthenticated(self, client: TestClient, auth_headers):
        org = _create_org(client, auth_headers)
        resp = client.post(f"/orgs/{org['id']}/api-keys", json={"name": "Nope"})
        assert resp.status_code == 401

    def test_create_key_member_denied(self, client: TestClient, auth_headers):
        """A regular member (not owner/admin) should not be able to create keys."""
        org = _create_org(client, auth_headers)
        _, bob_headers = _signup_and_login(client, "bob@example.com")

        # Add Bob as a member (not admin)
        client.post(
            f"/orgs/{org['id']}/members",
            json={"email": "bob@example.com", "role": "member"},
            headers=auth_headers,
        )

        resp = client.post(
            f"/orgs/{org['id']}/api-keys",
            json={"name": "Sneaky"},
            headers=bob_headers,
        )
        assert resp.status_code == 403


# List API Keys 
class TestListApiKeys:
    def test_list_keys_hides_secret(self, client: TestClient, auth_headers):
        """Listing keys should show prefix/metadata but NEVER the full key or hash."""
        org = _create_org(client, auth_headers)
        _create_api_key(client, auth_headers, org["id"], "Key A")
        _create_api_key(client, auth_headers, org["id"], "Key B")

        resp = client.get(f"/orgs/{org['id']}/api-keys", headers=auth_headers)
        assert resp.status_code == 200
        keys = resp.json()
        assert len(keys) == 2

        for k in keys:
            assert "key" not in k         # plaintext never returned on list
            assert "key_hash" not in k     # hash never returned
            assert "key_prefix" in k       # safe prefix is shown
            assert "is_active" in k

    def test_list_keys_empty(self, client: TestClient, auth_headers):
        org = _create_org(client, auth_headers)
        resp = client.get(f"/orgs/{org['id']}/api-keys", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json() == []


# Revoke API Key
class TestRevokeApiKey:
    def test_revoke_key(self, client: TestClient, auth_headers):
        org = _create_org(client, auth_headers)
        key_data = _create_api_key(client, auth_headers, org["id"])

        resp = client.delete(
            f"/orgs/{org['id']}/api-keys/{key_data['id']}",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["is_active"] is False

    def test_revoke_nonexistent_key(self, client: TestClient, auth_headers):
        org = _create_org(client, auth_headers)
        resp = client.delete(
            f"/orgs/{org['id']}/api-keys/99999",
            headers=auth_headers,
        )
        assert resp.status_code == 404

    def test_revoked_key_shows_in_list(self, client: TestClient, auth_headers):
        """Revoked keys are kept for audit -- they still appear in the list."""
        org = _create_org(client, auth_headers)
        key_data = _create_api_key(client, auth_headers, org["id"])

        client.delete(
            f"/orgs/{org['id']}/api-keys/{key_data['id']}",
            headers=auth_headers,
        )

        resp = client.get(f"/orgs/{org['id']}/api-keys", headers=auth_headers)
        keys = resp.json()
        assert len(keys) == 1
        assert keys[0]["is_active"] is False


# API Key Authentication
class TestApiKeyAuth:
    """Test the X-API-Key header authentication using the /health endpoint
    indirectly, and by calling a purpose-built test-only route."""

    def test_auth_with_valid_key(self, client: TestClient, auth_headers):
        """A valid API key in X-API-Key header should authenticate successfully."""
        org = _create_org(client, auth_headers)
        key_data = _create_api_key(client, auth_headers, org["id"])

        # Use the key to call the test-only route we registered in conftest
        resp = client.get(
            "/test/api-key-check",
            headers={"X-API-Key": key_data["key"]},
        )
        assert resp.status_code == 200
        assert resp.json()["org_id"] == org["id"]

    def test_auth_with_invalid_key(self, client: TestClient):
        resp = client.get(
            "/test/api-key-check",
            headers={"X-API-Key": "smp_live_fakefakefakefake"},
        )
        assert resp.status_code == 401

    def test_auth_missing_header(self, client: TestClient):
        resp = client.get("/test/api-key-check")
        assert resp.status_code == 401

    def test_auth_revoked_key_fails(self, client: TestClient, auth_headers):
        """After revocation, the key should no longer authenticate."""
        org = _create_org(client, auth_headers)
        key_data = _create_api_key(client, auth_headers, org["id"])

        # Revoke it
        client.delete(
            f"/orgs/{org['id']}/api-keys/{key_data['id']}",
            headers=auth_headers,
        )

        # Try to use it
        resp = client.get(
            "/test/api-key-check",
            headers={"X-API-Key": key_data["key"]},
        )
        assert resp.status_code == 401

