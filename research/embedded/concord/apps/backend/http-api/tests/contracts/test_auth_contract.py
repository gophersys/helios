"""
API contract tests for /v2/auth endpoints.

Shapes derived from:
  - login() response in src/api/v2/auth/login.py
  - me() response in src/api/v2/auth/me.py
"""

import json
from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from tests.conftest import make_obj
from tests.contracts.validate import assert_envelope, assert_response_shape

# ---------------------------------------------------------------------------
# Shape definitions
# ---------------------------------------------------------------------------

_USER_SHAPE = {
    "id": str,
    "email": str,
    "name": str,
    "role": str,
    "permissionSetId": (str, type(None)),
    "permissionSetName": (str, type(None)),
}

_LOGIN_RESPONSE_SHAPE = {
    "token": str,
    "user": _USER_SHAPE,
}

_ME_SHAPE = {
    "id": str,
    "email": str,
    "name": str,
    "role": str,
    "viewAsRole": (str, type(None)),
    "permissionSetId": (str, type(None)),
    "permissionSetName": (str, type(None)),
    "permissions": list,
    "productAccess": list,
    "active": bool,
    "lastSeenAt": (str, type(None)),
    "createdAt": str,
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_user(**kwargs):
    defaults = dict(
        id="user-1",
        email="test@example.com",
        name="Test User",
        role="DEVELOPER",
        active=True,
        permissionSetId="perm-1",
        lastSeenAt=None,
        createdAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
        updatedAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
        permissionSet=make_obj(
            id="perm-1",
            name="Developer",
            permissions=["products.view"],
        ),
        productAccess=[],
    )
    defaults.update(kwargs)
    return make_obj(**defaults)


# ---------------------------------------------------------------------------
# Test: POST /v2/auth/login
# ---------------------------------------------------------------------------


@pytest.mark.contract
def test_login_response_shape(authed_client, mock_db):
    """POST /v2/auth/login returns token + user object with correct shape."""
    user = _make_user()
    mock_db.user.find_unique.return_value = user
    mock_db.user.update.return_value = user

    with patch("api.v2.auth.login.authenticate_corecloud") as mock_cc:
        mock_cc.return_value = ({"email": "test@example.com"}, None)
        resp = authed_client.post(
            "/v2/auth/login",
            data=json.dumps({"email": "test@example.com", "password": "secret"}),
        )

    assert resp.status_code == 200
    data = assert_envelope(json.loads(resp.data))
    assert_response_shape(data, _LOGIN_RESPONSE_SHAPE)

    # token must be a non-empty string
    assert len(data["token"]) > 0, "token must be non-empty"

    # TODO: test_login_wrong_credentials_returns_401
    # TODO: test_login_inactive_user_returns_403
    # TODO: test_login_unregistered_user_returns_403


# ---------------------------------------------------------------------------
# Test: GET /v2/auth/me
# ---------------------------------------------------------------------------


@pytest.mark.contract
def test_me_response_shape(authed_client, mock_db):
    """GET /v2/auth/me returns full user profile with correct shape."""
    user = _make_user()
    mock_db.user.find_unique.return_value = user

    resp = authed_client.get("/v2/auth/me")

    assert resp.status_code == 200
    data = assert_envelope(json.loads(resp.data))
    assert_response_shape(data, _ME_SHAPE)

    # permissions must be a list of strings
    assert all(isinstance(p, str) for p in data["permissions"]), (
        "permissions must be a list of strings"
    )

    # TODO: test_me_with_product_access_includes_product_name
    # TODO: test_me_view_as_role_changes_permissions
    # TODO: test_me_unauthenticated_returns_401
