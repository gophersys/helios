"""Extended tests for lib/decorators.py — role-based access, product access, auth bypass.

Covers: require_role, require_product_access, X-View-As-Role, auth disabled bypass,
API key expiry, deactivated user, invalid auth format.
"""

from __future__ import annotations

import hashlib
import json
import time
import types as stdlib_types
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch

import pytest

from tests.conftest import make_obj


def _make_flask_app():
    """Create a minimal Flask app for decorator testing."""
    from flask import Flask
    app = Flask(__name__)
    app.config["TESTING"] = True
    return app


def _make_auth_headers(role="DEVELOPER", perm_set_id="test-perm-set-id"):
    """Create JWT auth headers for a specific role."""
    from src.services.auth.jwt import create_token
    token = create_token(
        user_id="test-user-id",
        email="test@example.com",
        name="Test User",
        permission_set_id=perm_set_id,
        role=role,
    )
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


# ---------------------------------------------------------------------------
# require_auth — auth disabled bypass
# ---------------------------------------------------------------------------

class TestRequireAuthDisabled:
    """Tests for require_auth behavior when AUTH_ENABLED=false."""

    def test_auth_disabled_injects_admin_identity(self, mock_db):
        """When auth is disabled, default admin identity is injected."""
        from flask import g
        from src.lib.decorators import require_auth

        app = _make_flask_app()

        @app.route("/test-bypass")
        @require_auth
        def handler():
            return json.dumps({"email": g.current_user["email"]}), 200

        with patch("config.env.env_config.AUTH_ENABLED", False):
            client = app.test_client()
            resp = client.get("/test-bypass")

        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data["email"] == "admin@concord.local"

    def test_auth_disabled_with_valid_bearer(self, mock_db):
        """When auth is disabled but a valid Bearer token is sent, it is decoded."""
        from flask import g
        from src.lib.decorators import require_auth

        app = _make_flask_app()

        @app.route("/test-bypass-bearer")
        @require_auth
        def handler():
            return json.dumps({"email": g.current_user["email"]}), 200

        headers = _make_auth_headers()

        with patch("config.env.env_config.AUTH_ENABLED", False):
            client = app.test_client()
            resp = client.get("/test-bypass-bearer", headers=headers)

        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data["email"] == "test@example.com"

    def test_auth_disabled_with_invalid_bearer_falls_back(self, mock_db):
        """When auth is disabled and invalid Bearer token, falls back to admin."""
        from flask import g
        from src.lib.decorators import require_auth

        app = _make_flask_app()

        @app.route("/test-bypass-invalid")
        @require_auth
        def handler():
            return json.dumps({"email": g.current_user["email"]}), 200

        with patch("config.env.env_config.AUTH_ENABLED", False):
            client = app.test_client()
            resp = client.get(
                "/test-bypass-invalid",
                headers={"Authorization": "Bearer bad.token.here"},
            )

        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data["email"] == "admin@concord.local"


# ---------------------------------------------------------------------------
# require_auth — API key edge cases
# ---------------------------------------------------------------------------

class TestRequireAuthApiKeyEdgeCases:
    """Tests for API key auth edge cases."""

    def test_expired_api_key_rejected(self, mock_db):
        """Expired API keys return 401."""
        from src.lib.decorators import require_auth

        app = _make_flask_app()

        raw_key = "test-expired-key"
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()

        mock_db.apikey.find_unique.return_value = stdlib_types.SimpleNamespace(
            id="key-1",
            keyHash=key_hash,
            expiresAt=datetime(2020, 1, 1, tzinfo=timezone.utc),
            user=stdlib_types.SimpleNamespace(
                id="u-1", email="user@test.com", name="Test",
                permissionSetId=None, active=True,
            ),
        )

        @app.route("/test-expired-key")
        @require_auth
        def handler():
            return json.dumps({"ok": True}), 200

        client = app.test_client()
        resp = client.get(
            "/test-expired-key",
            headers={"Authorization": f"ApiKey {raw_key}"},
        )

        assert resp.status_code == 401
        data = json.loads(resp.data)
        assert "expired" in data["errors"][0]["message"].lower()

    def test_deactivated_user_rejected(self, mock_db):
        """API keys belonging to deactivated users return 403."""
        from src.lib.decorators import require_auth

        app = _make_flask_app()

        raw_key = "test-deactivated-key"
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()

        mock_db.apikey.find_unique.return_value = stdlib_types.SimpleNamespace(
            id="key-1",
            keyHash=key_hash,
            expiresAt=None,
            user=stdlib_types.SimpleNamespace(
                id="u-1", email="user@test.com", name="Test",
                permissionSetId=None, active=False,
            ),
        )

        @app.route("/test-deactivated")
        @require_auth
        def handler():
            return json.dumps({"ok": True}), 200

        client = app.test_client()
        resp = client.get(
            "/test-deactivated",
            headers={"Authorization": f"ApiKey {raw_key}"},
        )

        assert resp.status_code == 403

    def test_invalid_auth_format_rejected(self, mock_db):
        """Invalid auth header format (not Bearer or ApiKey) returns 401."""
        from src.lib.decorators import require_auth

        app = _make_flask_app()

        @app.route("/test-invalid-format")
        @require_auth
        def handler():
            return json.dumps({"ok": True}), 200

        client = app.test_client()
        resp = client.get(
            "/test-invalid-format",
            headers={"Authorization": "Basic dXNlcjpwYXNz"},
        )

        assert resp.status_code == 401
        data = json.loads(resp.data)
        assert "format" in data["errors"][0]["message"].lower()


# ---------------------------------------------------------------------------
# require_role
# ---------------------------------------------------------------------------

class TestRequireRole:
    """Tests for require_role() decorator."""

    def test_admin_passes_admin_check(self, mock_db):
        """Admin role passes ADMIN requirement."""
        from src.lib.decorators import require_role

        app = _make_flask_app()
        headers = _make_auth_headers(role="ADMIN")
        mock_db.permissionset.find_unique.return_value = None

        @app.route("/test-admin-role")
        @require_role("ADMIN")
        def handler():
            return json.dumps({"ok": True}), 200

        client = app.test_client()
        resp = client.get("/test-admin-role", headers=headers)
        assert resp.status_code == 200

    def test_developer_fails_admin_check(self, mock_db):
        """Developer role fails ADMIN requirement."""
        from src.lib.decorators import require_role

        app = _make_flask_app()
        headers = _make_auth_headers(role="DEVELOPER")

        @app.route("/test-dev-admin")
        @require_role("ADMIN")
        def handler():
            return json.dumps({"ok": True}), 200

        client = app.test_client()
        resp = client.get("/test-dev-admin", headers=headers)
        assert resp.status_code == 403

    def test_maintainer_passes_developer_check(self, mock_db):
        """Maintainer role passes DEVELOPER requirement (higher rank)."""
        from src.lib.decorators import require_role

        app = _make_flask_app()
        headers = _make_auth_headers(role="MAINTAINER")
        mock_db.permissionset.find_unique.return_value = None

        @app.route("/test-maintainer-dev")
        @require_role("DEVELOPER")
        def handler():
            return json.dumps({"ok": True}), 200

        client = app.test_client()
        resp = client.get("/test-maintainer-dev", headers=headers)
        assert resp.status_code == 200

    def test_auth_disabled_bypasses_role_check(self, mock_db):
        """Role checks are bypassed when auth is disabled."""
        from src.lib.decorators import require_role

        app = _make_flask_app()

        @app.route("/test-role-bypass")
        @require_role("ADMIN")
        def handler():
            return json.dumps({"ok": True}), 200

        with patch("config.env.env_config.AUTH_ENABLED", False):
            client = app.test_client()
            resp = client.get("/test-role-bypass")

        assert resp.status_code == 200

    def test_view_as_role_downgrades(self, mock_db):
        """X-View-As-Role header downgrades effective role for Admin."""
        from src.lib.decorators import require_role
        from flask import g

        app = _make_flask_app()
        headers = _make_auth_headers(role="ADMIN")
        headers["X-View-As-Role"] = "OPERATOR"
        mock_db.permissionset.find_unique.return_value = None

        @app.route("/test-view-as")
        @require_role("DEVELOPER")
        def handler():
            return json.dumps({"role": g.effective_role}), 200

        client = app.test_client()
        resp = client.get("/test-view-as", headers=headers)

        # OPERATOR < DEVELOPER, so should be 403
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# require_product_access
# ---------------------------------------------------------------------------

class TestRequireProductAccess:
    """Tests for require_product_access() decorator."""

    def test_admin_bypasses_product_check(self, mock_db):
        """Admin role bypasses product access checks."""
        from src.lib.decorators import require_product_access

        app = _make_flask_app()
        headers = _make_auth_headers(role="ADMIN")
        mock_db.permissionset.find_unique.return_value = None

        @app.route("/products/<product_id>")
        @require_product_access("develop")
        def handler(product_id):
            return json.dumps({"ok": True}), 200

        client = app.test_client()
        resp = client.get("/products/prod-1", headers=headers)
        assert resp.status_code == 200

    def test_developer_with_access(self, mock_db):
        """Developer with sufficient product access passes."""
        from src.lib.decorators import require_product_access

        app = _make_flask_app()
        headers = _make_auth_headers(role="DEVELOPER")

        mock_db.productaccess.find_first.return_value = make_obj(
            userId="test-user-id", productId="prod-1", level="develop",
        )

        @app.route("/products/<product_id>")
        @require_product_access("develop")
        def handler(product_id):
            return json.dumps({"ok": True}), 200

        client = app.test_client()
        resp = client.get("/products/prod-1", headers=headers)
        assert resp.status_code == 200

    def test_developer_insufficient_access(self, mock_db):
        """Developer with lower access level is rejected."""
        from src.lib.decorators import require_product_access

        app = _make_flask_app()
        headers = _make_auth_headers(role="DEVELOPER")

        mock_db.productaccess.find_first.return_value = make_obj(
            userId="test-user-id", productId="prod-1", level="view",
        )

        @app.route("/products/<product_id>")
        @require_product_access("develop")
        def handler(product_id):
            return json.dumps({"ok": True}), 200

        client = app.test_client()
        resp = client.get("/products/prod-1", headers=headers)
        assert resp.status_code == 403

    def test_developer_no_access_record(self, mock_db):
        """Developer with no ProductAccess record is rejected."""
        from src.lib.decorators import require_product_access

        app = _make_flask_app()
        headers = _make_auth_headers(role="DEVELOPER")

        mock_db.productaccess.find_first.return_value = None

        @app.route("/products/<product_id>")
        @require_product_access("develop")
        def handler(product_id):
            return json.dumps({"ok": True}), 200

        client = app.test_client()
        resp = client.get("/products/prod-1", headers=headers)
        assert resp.status_code == 403

    def test_no_product_id_allows_through(self, mock_db):
        """When no product_id can be found, request passes through."""
        from src.lib.decorators import require_product_access

        app = _make_flask_app()
        headers = _make_auth_headers(role="DEVELOPER")

        @app.route("/products-list")
        @require_product_access("view")
        def handler():
            return json.dumps({"ok": True}), 200

        client = app.test_client()
        resp = client.get("/products-list", headers=headers)
        assert resp.status_code == 200

    def test_auth_disabled_bypasses_product_check(self, mock_db):
        """Product access checks are bypassed when auth is disabled."""
        from src.lib.decorators import require_product_access

        app = _make_flask_app()

        @app.route("/products/<product_id>")
        @require_product_access("admin")
        def handler(product_id):
            return json.dumps({"ok": True}), 200

        with patch("config.env.env_config.AUTH_ENABLED", False):
            client = app.test_client()
            resp = client.get("/products/prod-1")

        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# require_permissions — admin/maintainer bypass
# ---------------------------------------------------------------------------

class TestRequirePermissionsRoleBypass:
    """Tests for role-based bypass in require_permissions."""

    def test_admin_bypasses_permission_check(self, mock_db):
        """Admin role bypasses permission set checks entirely."""
        from src.lib.decorators import require_permissions

        app = _make_flask_app()
        headers = _make_auth_headers(role="ADMIN")
        mock_db.permissionset.find_unique.return_value = None

        @app.route("/test-admin-bypass")
        @require_permissions("some:nonexistent:perm")
        def handler():
            return json.dumps({"ok": True}), 200

        client = app.test_client()
        resp = client.get("/test-admin-bypass", headers=headers)
        assert resp.status_code == 200

    def test_maintainer_bypasses_permission_check(self, mock_db):
        """Maintainer role bypasses permission set checks entirely."""
        from src.lib.decorators import require_permissions

        app = _make_flask_app()
        headers = _make_auth_headers(role="MAINTAINER")
        mock_db.permissionset.find_unique.return_value = None

        @app.route("/test-maintainer-bypass")
        @require_permissions("some:nonexistent:perm")
        def handler():
            return json.dumps({"ok": True}), 200

        client = app.test_client()
        resp = client.get("/test-maintainer-bypass", headers=headers)
        assert resp.status_code == 200

    def test_permission_set_not_found_returns_403(self, mock_db):
        """Returns 403 when permission set ID exists but record not found."""
        from src.lib.decorators import require_permissions

        app = _make_flask_app()
        headers = _make_auth_headers(role="DEVELOPER", perm_set_id="missing-set")

        mock_db.permissionset.find_unique.return_value = None

        @app.route("/test-perm-not-found")
        @require_permissions("products:view")
        def handler():
            return json.dumps({"ok": True}), 200

        client = app.test_client()
        resp = client.get("/test-perm-not-found", headers=headers)
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# _resolve_effective_role
# ---------------------------------------------------------------------------

class TestResolveEffectiveRole:
    """Tests for _resolve_effective_role()."""

    def test_developer_cannot_view_as(self, mock_db):
        """Developer cannot use X-View-As-Role."""
        from src.lib.decorators import _resolve_effective_role
        from flask import Flask

        app = Flask(__name__)
        with app.test_request_context(headers={"X-View-As-Role": "ADMIN"}):
            result = _resolve_effective_role({"role": "DEVELOPER"})
            assert result == "DEVELOPER"

    def test_admin_view_as_operator(self, mock_db):
        """Admin can view-as OPERATOR."""
        from src.lib.decorators import _resolve_effective_role
        from flask import Flask

        app = Flask(__name__)
        with app.test_request_context(headers={"X-View-As-Role": "OPERATOR"}):
            result = _resolve_effective_role({"role": "ADMIN"})
            assert result == "OPERATOR"

    def test_admin_view_as_invalid_role_ignored(self, mock_db):
        """Invalid X-View-As-Role values are ignored."""
        from src.lib.decorators import _resolve_effective_role
        from flask import Flask

        app = Flask(__name__)
        with app.test_request_context(headers={"X-View-As-Role": "SUPERADMIN"}):
            result = _resolve_effective_role({"role": "ADMIN"})
            assert result == "ADMIN"

    def test_no_role_defaults_to_developer(self, mock_db):
        """Missing role key defaults to DEVELOPER."""
        from src.lib.decorators import _resolve_effective_role
        from flask import Flask

        app = Flask(__name__)
        with app.test_request_context():
            result = _resolve_effective_role({})
            assert result == "DEVELOPER"
