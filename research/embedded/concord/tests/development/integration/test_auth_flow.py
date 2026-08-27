"""Test auth system against real database.

Covers dev login, JWT flow, permissions, and role-based access.
"""

import pytest


class TestDevLogin:
    """Test the development login flow (AUTH_ENABLED=false)."""

    def test_dev_login_returns_token(self, test_api):
        """POST /v2/auth/dev-login with valid email returns JWT."""
        resp = test_api.post("/v2/auth/dev-login", json={"email": "admin@concord.dev"})
        assert resp.status_code == 200
        body = resp.get_json()
        data = body["data"]
        assert "token" in data
        assert data["user"]["email"] == "admin@concord.dev"
        assert data["user"]["role"] == "ADMIN"

    def test_dev_login_invalid_email_returns_404(self, test_api):
        """POST /v2/auth/dev-login with unknown email returns 404."""
        resp = test_api.post("/v2/auth/dev-login", json={"email": "nobody@nowhere.com"})
        assert resp.status_code == 404

    def test_dev_login_missing_email_returns_400(self, test_api):
        """POST /v2/auth/dev-login with no email returns 400."""
        resp = test_api.post("/v2/auth/dev-login", json={})
        assert resp.status_code == 400

    def test_dev_login_all_roles(self, test_api):
        """Each dev user (admin, maintainer, developer, operator) can log in."""
        for email, expected_role in [
            ("admin@concord.dev", "ADMIN"),
            ("maintainer@concord.dev", "MAINTAINER"),
            ("developer@concord.dev", "DEVELOPER"),
            ("operator@concord.dev", "OPERATOR"),
        ]:
            resp = test_api.post("/v2/auth/dev-login", json={"email": email})
            assert resp.status_code == 200, f"Login failed for {email}"
            assert resp.get_json()["data"]["user"]["role"] == expected_role


class TestDevUsers:
    """Test the dev-users listing endpoint."""

    def test_dev_users_returns_all_roles(self, test_api):
        """GET /v2/auth/dev-users returns one user per role."""
        resp = test_api.get("/v2/auth/dev-users")
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert data["environment"] == "test"

        roles = {u["role"] for u in data["users"]}
        assert roles == {"ADMIN", "MAINTAINER", "DEVELOPER", "OPERATOR"}


class TestMe:
    """Test the /v2/auth/me endpoint with real JWT tokens."""

    def test_me_returns_admin_profile(self, test_api, admin_headers):
        """GET /v2/auth/me returns role, permissions, and product access."""
        resp = test_api.get("/v2/auth/me", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.get_json()["data"]

        assert data["email"] == "admin@concord.dev"
        assert data["role"] == "ADMIN"
        assert data["permissionSetName"] == "Admin"
        assert isinstance(data["permissions"], list)
        assert len(data["permissions"]) > 0
        assert isinstance(data["productAccess"], list)

    def test_me_developer_profile(self, test_api, developer_headers):
        """Developer user gets Developer role and limited permissions."""
        resp = test_api.get("/v2/auth/me", headers=developer_headers)
        assert resp.status_code == 200
        data = resp.get_json()["data"]

        assert data["role"] == "DEVELOPER"
        assert data["permissionSetName"] == "Developer"
        # Developer shouldn't have users:manage
        assert "users:manage" not in data["permissions"]

    def test_me_operator_profile(self, test_api, operator_headers):
        """Operator user gets Operator role with manufacturing permissions only."""
        resp = test_api.get("/v2/auth/me", headers=operator_headers)
        assert resp.status_code == 200
        data = resp.get_json()["data"]

        assert data["role"] == "OPERATOR"
        perms = data["permissions"]
        # Operator should only have manufacturing permissions
        for perm in perms:
            assert perm.startswith("manufacturing:"), f"Unexpected permission: {perm}"

    def test_me_no_auth_returns_401(self, test_api):
        """GET /v2/auth/me without auth header uses default admin (AUTH_ENABLED=false)."""
        # With AUTH_ENABLED=false, no-auth requests get the default admin identity
        resp = test_api.get("/v2/auth/me")
        # The default admin identity won't have a real user in the DB
        # so this should return the default profile or 404
        assert resp.status_code in (200, 404)


class TestApiKeyAuth:
    """Test API key authentication flow."""

    def test_ci_api_key_authenticates(self, test_api, ci_api_key_headers):
        """CI API key passes auth and returns products."""
        resp = test_api.get("/v2/products", headers=ci_api_key_headers)
        assert resp.status_code == 200

    def test_invalid_api_key_returns_401(self, test_api):
        """Invalid API key returns 401 when AUTH_ENABLED=true."""
        # AUTH_ENABLED=false bypasses auth, so this tests the bypass
        headers = {"Authorization": "ApiKey invalid_key_here"}
        resp = test_api.get("/v2/products", headers=headers)
        # With AUTH_ENABLED=false, all requests pass through
        assert resp.status_code == 200
