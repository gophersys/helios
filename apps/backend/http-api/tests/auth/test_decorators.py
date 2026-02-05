"""
Unit tests for decorators in src/lib/decorators.py.

Tests require_auth, require_permissions, and cache invalidation.
"""

import hashlib
import json
import time
import types as stdlib_types
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest


def test_require_auth_missing_header(mock_db):
    from flask import Flask
    from src.lib.decorators import require_auth

    app = Flask(__name__)
    app.config["TESTING"] = True

    @app.route("/test-auth-missing")
    @require_auth
    def test_route():
        return json.dumps({"success": True}), 200

    client = app.test_client()
    response = client.get("/test-auth-missing")

    assert response.status_code == 401
    data = json.loads(response.data)
    assert data["data"] is None
    assert len(data["errors"]) > 0
    assert "Missing authorization header" in data["errors"][0]["message"]


def test_require_auth_invalid_token(mock_db):
    from flask import Flask
    from src.lib.decorators import require_auth

    app = Flask(__name__)
    app.config["TESTING"] = True

    @app.route("/test-auth-invalid")
    @require_auth
    def test_route():
        return json.dumps({"success": True}), 200

    client = app.test_client()
    response = client.get(
        "/test-auth-invalid",
        headers={"Authorization": "Bearer invalid.token.here"},
    )

    assert response.status_code == 401
    data = json.loads(response.data)
    assert data["data"] is None
    assert len(data["errors"]) > 0
    assert "Invalid token" in data["errors"][0]["message"]


def test_require_auth_valid_jwt(auth_headers, mock_db):
    from flask import Flask, g
    from src.lib.decorators import require_auth

    app = Flask(__name__)
    app.config["TESTING"] = True

    @app.route("/test-auth-valid")
    @require_auth
    def test_route():
        user = g.current_user
        return json.dumps({
            "userId": user["sub"],
            "email": user["email"],
            "name": user["name"],
        }), 200

    client = app.test_client()
    response = client.get("/test-auth-valid", headers=auth_headers)

    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["userId"] == "test-user-id"
    assert data["email"] == "test@example.com"
    assert data["name"] == "Test User"


def test_require_auth_valid_api_key(mock_db):
    from flask import Flask, g
    from src.lib.decorators import require_auth

    app = Flask(__name__)
    app.config["TESTING"] = True

    # Create test API key
    test_key = "test-api-key-12345"
    key_hash = hashlib.sha256(test_key.encode()).hexdigest()

    # Mock DB responses
    api_key_obj = stdlib_types.SimpleNamespace(
        id="api-key-id",
        keyHash=key_hash,
        expiresAt=None,
        user=stdlib_types.SimpleNamespace(
            id="api-user-id",
            email="apiuser@example.com",
            name="API User",
            permissionSetId="api-perm-set",
            active=True,
        ),
    )
    mock_db.apikey.find_unique.return_value = api_key_obj
    mock_db.apikey.update.return_value = None

    @app.route("/test-api-key")
    @require_auth
    def test_route():
        user = g.current_user
        return json.dumps({
            "userId": user["sub"],
            "email": user["email"],
        }), 200

    client = app.test_client()
    response = client.get(
        "/test-api-key",
        headers={"Authorization": f"ApiKey {test_key}"},
    )

    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["userId"] == "api-user-id"
    assert data["email"] == "apiuser@example.com"

    # Verify that lastUsedAt was updated
    mock_db.apikey.update.assert_called_once()


def test_require_permissions_missing_permission(auth_headers, mock_db):
    from flask import Flask
    from src.lib.decorators import require_permissions

    app = Flask(__name__)
    app.config["TESTING"] = True

    # Mock permission set with limited permissions
    perm_set = stdlib_types.SimpleNamespace(
        id="test-perm-set-id",
        name="Limited User",
        permissions=["Concord.Admin.Users.View"],
    )
    mock_db.permissionset.find_unique.return_value = perm_set

    @app.route("/test-perms-missing")
    @require_permissions("Concord.Admin.Products.Manage")
    def test_route():
        return json.dumps({"success": True}), 200

    client = app.test_client()
    response = client.get("/test-perms-missing", headers=auth_headers)

    assert response.status_code == 403
    data = json.loads(response.data)
    assert data["data"] is None
    assert len(data["errors"]) > 0
    assert "Forbidden" in data["errors"][0]["message"]


def test_require_permissions_valid_permission(auth_headers, mock_db):
    from flask import Flask
    from src.lib.decorators import require_permissions

    app = Flask(__name__)
    app.config["TESTING"] = True

    # Mock permission set with the required permission
    perm_set = stdlib_types.SimpleNamespace(
        id="test-perm-set-id",
        name="Admin User",
        permissions=["Concord.Admin.Products.View", "Concord.Admin.Products.Manage"],
    )
    mock_db.permissionset.find_unique.return_value = perm_set

    @app.route("/test-perms-valid")
    @require_permissions("Concord.Admin.Products.Manage")
    def test_route():
        return json.dumps({"success": True}), 200

    client = app.test_client()
    response = client.get("/test-perms-valid", headers=auth_headers)

    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["success"] is True


def test_require_permissions_multiple_permissions(auth_headers, mock_db):
    from flask import Flask
    from src.lib.decorators import require_permissions

    app = Flask(__name__)
    app.config["TESTING"] = True

    # Mock permission set with all required permissions
    perm_set = stdlib_types.SimpleNamespace(
        id="test-perm-set-id",
        name="Admin User",
        permissions=[
            "Concord.Admin.Products.View",
            "Concord.Admin.Products.Manage",
            "Concord.Admin.Users.View",
        ],
    )
    mock_db.permissionset.find_unique.return_value = perm_set

    @app.route("/test-perms-multiple")
    @require_permissions("Concord.Admin.Products.Manage", "Concord.Admin.Users.View")
    def test_route():
        return json.dumps({"success": True}), 200

    client = app.test_client()
    response = client.get("/test-perms-multiple", headers=auth_headers)

    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["success"] is True


def test_require_permissions_no_permission_set(mock_db):
    from flask import Flask
    from src.lib.decorators import require_permissions
    from src.services.auth.jwt import create_token

    app = Flask(__name__)
    app.config["TESTING"] = True

    # Create token with no permission set
    token = create_token(
        user_id="no-perm-user",
        email="noperm@example.com",
        name="No Perm User",
        permission_set_id=None,
    )

    @app.route("/test-perms-no-set")
    @require_permissions("Concord.Admin.Products.View")
    def test_route():
        return json.dumps({"success": True}), 200

    client = app.test_client()
    response = client.get(
        "/test-perms-no-set",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403
    data = json.loads(response.data)
    assert data["data"] is None
    assert "No permission set assigned" in data["errors"][0]["message"]


def test_invalidate_permission_set_cache(mock_db):
    from src.lib.decorators import invalidate_permission_set_cache, _get_permissions_for_set

    # Mock permission set
    perm_set = stdlib_types.SimpleNamespace(
        id="perm-set-1",
        name="Test Set",
        permissions=["Concord.Admin.Products.View"],
    )
    mock_db.permissionset.find_unique.return_value = perm_set

    # Load into cache
    perms = _get_permissions_for_set("perm-set-1")
    assert perms == ["Concord.Admin.Products.View"]

    # Verify it was cached (DB should not be called again)
    mock_db.permissionset.find_unique.reset_mock()
    perms_cached = _get_permissions_for_set("perm-set-1")
    assert perms_cached == ["Concord.Admin.Products.View"]
    mock_db.permissionset.find_unique.assert_not_called()

    # Invalidate specific permission set
    invalidate_permission_set_cache("perm-set-1")

    # Should hit DB again
    perms_after = _get_permissions_for_set("perm-set-1")
    assert perms_after == ["Concord.Admin.Products.View"]
    mock_db.permissionset.find_unique.assert_called_once()


def test_invalidate_permission_set_cache_all(mock_db):
    from src.lib.decorators import invalidate_permission_set_cache, _get_permissions_for_set

    # Mock permission sets
    perm_set_1 = stdlib_types.SimpleNamespace(
        id="perm-set-1",
        permissions=["Concord.Admin.Products.View"],
    )
    perm_set_2 = stdlib_types.SimpleNamespace(
        id="perm-set-2",
        permissions=["Concord.Admin.Users.View"],
    )

    def find_unique_side_effect(where):
        perm_id = where["id"]
        if perm_id == "perm-set-1":
            return perm_set_1
        elif perm_id == "perm-set-2":
            return perm_set_2
        return None

    mock_db.permissionset.find_unique.side_effect = find_unique_side_effect

    # Load both into cache
    _get_permissions_for_set("perm-set-1")
    _get_permissions_for_set("perm-set-2")

    # Reset mock to verify cache hit
    mock_db.permissionset.find_unique.reset_mock()
    mock_db.permissionset.find_unique.side_effect = find_unique_side_effect

    # Both should be cached (no DB calls)
    _get_permissions_for_set("perm-set-1")
    _get_permissions_for_set("perm-set-2")
    assert mock_db.permissionset.find_unique.call_count == 0

    # Invalidate all
    invalidate_permission_set_cache()

    # Both should hit DB again
    _get_permissions_for_set("perm-set-1")
    _get_permissions_for_set("perm-set-2")
    assert mock_db.permissionset.find_unique.call_count == 2


def test_permission_cache_ttl(mock_db):
    from src.lib.decorators import _get_permissions_for_set, _CACHE_TTL_SECONDS
    from unittest.mock import patch

    perm_set = stdlib_types.SimpleNamespace(
        id="perm-set-ttl",
        permissions=["Concord.Admin.Products.View"],
    )
    mock_db.permissionset.find_unique.return_value = perm_set

    # Load into cache
    with patch("time.time", return_value=1000.0):
        perms = _get_permissions_for_set("perm-set-ttl")
        assert perms == ["Concord.Admin.Products.View"]

    # Within TTL, should use cache
    mock_db.permissionset.find_unique.reset_mock()
    with patch("time.time", return_value=1000.0 + _CACHE_TTL_SECONDS - 1):
        perms_cached = _get_permissions_for_set("perm-set-ttl")
        assert perms_cached == ["Concord.Admin.Products.View"]
        mock_db.permissionset.find_unique.assert_not_called()

    # After TTL, should reload from DB
    with patch("time.time", return_value=1000.0 + _CACHE_TTL_SECONDS + 1):
        perms_expired = _get_permissions_for_set("perm-set-ttl")
        assert perms_expired == ["Concord.Admin.Products.View"]
        mock_db.permissionset.find_unique.assert_called_once()
