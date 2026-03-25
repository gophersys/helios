"""
Tests for AUTH_ENABLED bypass behavior.

Ensures that when AUTH_ENABLED=false:
- require_auth sets a default admin user without requiring any Authorization header
- require_permissions skips permission checks entirely
- /v2/auth/me returns a mock admin profile without a DB lookup

And when AUTH_ENABLED=true, auth is enforced normally.

These tests prevent regressions like the production OAuth error
where AUTH_ENABLED was in Helm values but never wired into Python code.
"""

import json
import os
import types as stdlib_types
from unittest.mock import patch, MagicMock

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_app_with_route(decorator, route_name="/test-bypass"):
    """Create a minimal Flask app with a single route wrapped by the given decorator."""
    from flask import Flask, g

    app = Flask(__name__)
    app.config["TESTING"] = True

    @app.route(route_name)
    @decorator
    def test_route():
        user = getattr(g, "current_user", None)
        return json.dumps({
            "userId": user["sub"] if user else None,
            "email": user.get("email") if user else None,
            "name": user.get("name") if user else None,
        }), 200

    return app


# ---------------------------------------------------------------------------
# require_auth — AUTH_ENABLED=false
# ---------------------------------------------------------------------------

class TestRequireAuthBypass:
    """Tests for require_auth when AUTH_ENABLED is False."""

    def test_no_auth_header_succeeds(self, mock_db):
        """Requests without Authorization header should succeed when auth is disabled."""
        with patch("config.env.env_config.AUTH_ENABLED", False):
            from src.lib.decorators import require_auth
            app = _make_app_with_route(require_auth)
            client = app.test_client()
            response = client.get("/test-bypass")

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["userId"] == "00000000-0000-0000-0000-000000000000"
        assert data["email"] == "admin@concord.local"
        assert data["name"] == "Admin (auth disabled)"

    def test_default_admin_identity(self, mock_db):
        """The default admin identity should have all expected fields."""
        from flask import Flask, g
        from src.lib.decorators import require_auth

        app = Flask(__name__)
        app.config["TESTING"] = True
        captured_user = {}

        @app.route("/test-identity")
        @require_auth
        def test_route():
            captured_user.update(g.current_user)
            return json.dumps({"ok": True}), 200

        with patch("config.env.env_config.AUTH_ENABLED", False):
            client = app.test_client()
            client.get("/test-identity")

        assert "sub" in captured_user
        assert "email" in captured_user
        assert "name" in captured_user
        assert "permissionSetId" in captured_user
        assert captured_user["permissionSetId"] is None

    def test_auth_still_works_when_enabled(self, mock_db, auth_headers):
        """When AUTH_ENABLED=true, valid JWT should still be required."""
        with patch("config.env.env_config.AUTH_ENABLED", True):
            from src.lib.decorators import require_auth
            app = _make_app_with_route(require_auth)
            client = app.test_client()

            # Without auth header → 401
            response_no_auth = client.get("/test-bypass")
            assert response_no_auth.status_code == 401

            # With valid auth header → 200
            response_with_auth = client.get("/test-bypass", headers=auth_headers)
            assert response_with_auth.status_code == 200


# ---------------------------------------------------------------------------
# require_permissions — AUTH_ENABLED=false
# ---------------------------------------------------------------------------

class TestRequirePermissionsBypass:
    """Tests for require_permissions when AUTH_ENABLED is False."""

    def test_skips_permission_check(self, mock_db):
        """No permission check should occur when auth is disabled."""
        with patch("config.env.env_config.AUTH_ENABLED", False):
            from src.lib.decorators import require_permissions
            app = _make_app_with_route(
                require_permissions("products:manage"),
                route_name="/test-perms-bypass",
            )
            client = app.test_client()
            response = client.get("/test-perms-bypass")

        assert response.status_code == 200
        # DB should never be queried for permission sets
        mock_db.permissionset.find_unique.assert_not_called()

    def test_multiple_permissions_skipped(self, mock_db):
        """Even strict multi-permission checks should be skipped when auth disabled."""
        with patch("config.env.env_config.AUTH_ENABLED", False):
            from src.lib.decorators import require_permissions
            app = _make_app_with_route(
                require_permissions(
                    "products:manage",
                    "users:manage",
                    "system:manage",
                ),
                route_name="/test-multi-bypass",
            )
            client = app.test_client()
            response = client.get("/test-multi-bypass")

        assert response.status_code == 200

    def test_permissions_enforced_when_enabled(self, mock_db, auth_headers):
        """When AUTH_ENABLED=true, permission checks should be enforced."""
        # Mock permission set with no matching permission
        perm_set = stdlib_types.SimpleNamespace(
            id="test-perm-set-id",
            name="Limited",
            permissions=["users:view"],
        )
        mock_db.permissionset.find_unique.return_value = perm_set

        with patch("config.env.env_config.AUTH_ENABLED", True):
            from src.lib.decorators import require_permissions
            app = _make_app_with_route(
                require_permissions("products:manage"),
                route_name="/test-perms-enforced",
            )
            client = app.test_client()
            response = client.get("/test-perms-enforced", headers=auth_headers)

        assert response.status_code == 403


# ---------------------------------------------------------------------------
# /v2/auth/me — AUTH_ENABLED=false
# ---------------------------------------------------------------------------

class TestMeEndpointBypass:
    """Tests for /v2/auth/me when AUTH_ENABLED is False."""

    def test_returns_mock_admin(self, client, mock_db):
        """Should return a mock admin profile without DB lookup."""
        with patch("config.env.env_config.AUTH_ENABLED", False):
            response = client.get("/v2/auth/me")

        assert response.status_code == 200
        data = json.loads(response.data)
        user = data["data"]
        assert user["id"] == "00000000-0000-0000-0000-000000000000"
        assert user["email"] == "admin@concord.local"
        assert user["name"] == "Admin (auth disabled)"
        assert user["permissionSetName"] == "Full Access"
        assert "products:view" in user["permissions"]
        assert user["active"] is True

        # Should NOT hit the database
        mock_db.user.find_unique.assert_not_called()

    def test_returns_real_user_when_enabled(self, authed_client, mock_db):
        """When AUTH_ENABLED=true, should query DB for real user."""
        from datetime import datetime, timezone
        from tests.conftest import make_obj

        mock_db.user.find_unique.return_value = make_obj(
            id="test-user-id",
            email="test@example.com",
            name="Test User",
            permissionSetId="perm-1",
            active=True,
            lastSeenAt=None,
            createdAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
            permissionSet=make_obj(
                id="perm-1",
                name="Admin",
                permissions=["products:view"],
            ),
        )

        with patch("config.env.env_config.AUTH_ENABLED", True):
            response = authed_client.get("/v2/auth/me")

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["data"]["email"] == "test@example.com"
        mock_db.user.find_unique.assert_called_once()
