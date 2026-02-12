"""Tests for /orgs endpoints - create, list, add member, role enforcement."""

from fastapi.testclient import TestClient

from tests.conftest import VALID_PASSWORD


# Helpers functions
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
    """Create an org and return its JSON."""
    resp = client.post("/orgs", json={"name": name}, headers=headers)
    assert resp.status_code == 201
    return resp.json()


# Create Org endpoint
class TestCreateOrg:
    def test_create_org_success(self, client: TestClient, auth_headers):
        org = _create_org(client, auth_headers)
        assert org["name"] == "Acme Inc"
        assert "id" in org

    def test_create_org_unauthenticated(self, client: TestClient):
        resp = client.post("/orgs", json={"name": "Acme Inc"})
        assert resp.status_code == 401

    def test_create_org_name_too_short(self, client: TestClient, auth_headers):
        resp = client.post("/orgs", json={"name": "A"}, headers=auth_headers)
        assert resp.status_code == 422


# List Orgs endpoint
class TestListOrgs:
    def test_list_orgs_empty(self, client: TestClient, auth_headers):
        resp = client.get("/orgs", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_orgs_returns_own(self, client: TestClient, auth_headers):
        _create_org(client, auth_headers, "Org A")
        _create_org(client, auth_headers, "Org B")

        resp = client.get("/orgs", headers=auth_headers)
        assert resp.status_code == 200
        names = [o["name"] for o in resp.json()]
        assert "Org A" in names
        assert "Org B" in names

    def test_list_orgs_excludes_others(self, client: TestClient, auth_headers):
        """A second user should not see the first user's orgs."""
        _create_org(client, auth_headers, "Secret Org")

        _, bob_headers = _signup_and_login(client, "bob@example.com")
        resp = client.get("/orgs", headers=bob_headers)
        assert resp.status_code == 200
        assert resp.json() == []


# Add Member endpoint
class TestAddMember:
    def test_add_member_success(self, client: TestClient, auth_headers, registered_user):
        org = _create_org(client, auth_headers)
        bob, _ = _signup_and_login(client, "bob@example.com")

        resp = client.post(
            f"/orgs/{org['id']}/members",
            json={"email": bob["email"], "role": "member"},
            headers=auth_headers,
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["email"] == bob["email"]
        assert body["role"] == "member"

    def test_added_member_sees_org(self, client: TestClient, auth_headers):
        """After being added, the new member should see the org in their list."""
        org = _create_org(client, auth_headers)
        _, bob_headers = _signup_and_login(client, "bob@example.com")

        client.post(
            f"/orgs/{org['id']}/members",
            json={"email": "bob@example.com", "role": "member"},
            headers=auth_headers,
        )

        resp = client.get("/orgs", headers=bob_headers)
        assert any(o["id"] == org["id"] for o in resp.json())

    def test_add_nonexistent_user(self, client: TestClient, auth_headers):
        org = _create_org(client, auth_headers)
        resp = client.post(
            f"/orgs/{org['id']}/members",
            json={"email": "ghost@example.com", "role": "member"},
            headers=auth_headers,
        )
        assert resp.status_code == 404

    def test_add_member_unauthenticated(self, client: TestClient, auth_headers):
        org = _create_org(client, auth_headers)
        resp = client.post(
            f"/orgs/{org['id']}/members",
            json={"email": "anyone@example.com", "role": "member"},
        )
        assert resp.status_code == 401


# Role Enforcement endpoint
class TestRoleEnforcement:
    def test_member_cannot_add_members(self, client: TestClient, auth_headers):
        """A user with role 'member' should not be able to add others."""
        org = _create_org(client, auth_headers)
        bob, bob_headers = _signup_and_login(client, "bob@example.com")

        # Owner adds Bob as a regular member
        client.post(
            f"/orgs/{org['id']}/members",
            json={"email": bob["email"], "role": "member"},
            headers=auth_headers,
        )

        # Bob (member) tries to add Carol - should be denied
        _signup_and_login(client, "carol@example.com")
        resp = client.post(
            f"/orgs/{org['id']}/members",
            json={"email": "carol@example.com", "role": "member"},
            headers=bob_headers,
        )
        assert resp.status_code == 403

    def test_admin_can_add_members(self, client: TestClient, auth_headers):
        """A user with role 'admin' should be able to add members."""
        org = _create_org(client, auth_headers)
        bob, bob_headers = _signup_and_login(client, "bob@example.com")

        # Owner adds Bob as admin
        client.post(
            f"/orgs/{org['id']}/members",
            json={"email": bob["email"], "role": "admin"},
            headers=auth_headers,
        )

        # Bob (admin) adds Carol - should succeed
        _signup_and_login(client, "carol@example.com")
        resp = client.post(
            f"/orgs/{org['id']}/members",
            json={"email": "carol@example.com", "role": "member"},
            headers=bob_headers,
        )
        assert resp.status_code == 201

    def test_non_owner_cannot_grant_owner(self, client: TestClient, auth_headers):
        """Only owners can grant the 'owner' role."""
        org = _create_org(client, auth_headers)
        bob, bob_headers = _signup_and_login(client, "bob@example.com")

        # Owner adds Bob as admin
        client.post(
            f"/orgs/{org['id']}/members",
            json={"email": bob["email"], "role": "admin"},
            headers=auth_headers,
        )

        # Bob (admin) tries to add Carol as owner - should be denied
        _signup_and_login(client, "carol@example.com")
        resp = client.post(
            f"/orgs/{org['id']}/members",
            json={"email": "carol@example.com", "role": "owner"},
            headers=bob_headers,
        )
        assert resp.status_code == 403

    def test_cannot_remove_last_owner(self, client: TestClient, auth_headers, registered_user):
        """Demoting the only owner should be rejected."""
        org = _create_org(client, auth_headers)

        # Owner tries to demote themselves to member - should fail
        resp = client.post(
            f"/orgs/{org['id']}/members",
            json={"email": registered_user["email"], "role": "member"},
            headers=auth_headers,
        )
        assert resp.status_code == 400
        assert "at least one owner" in resp.json()["detail"].lower()

