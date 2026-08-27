"""Integration tests for Login API (CoreKinect auth)."""

import json
from datetime import datetime, timezone
from unittest.mock import patch

from tests.conftest import make_obj


def test_login_missing_email(client):
    """Test login with missing email returns 400."""
    response = client.post(
        "/v2/auth/login",
        data=json.dumps({"password": "secret"}),
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 400
    data = json.loads(response.data)
    assert len(data["errors"]) > 0


def test_login_missing_password(client):
    """Test login with missing password returns 400."""
    response = client.post(
        "/v2/auth/login",
        data=json.dumps({"email": "user@example.com"}),
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 400
    data = json.loads(response.data)
    assert len(data["errors"]) > 0


def test_login_empty_body(client):
    """Test login with empty body returns 400."""
    response = client.post(
        "/v2/auth/login",
        data=json.dumps({}),
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 400
    data = json.loads(response.data)
    assert len(data["errors"]) > 0


def test_login_auth_server_error(client, mock_db):
    """Test login when auth server returns error."""
    with patch("api.v2.auth.login.authenticate_corecloud", return_value=(None, "Auth server unreachable")):
        response = client.post(
            "/v2/auth/login",
            data=json.dumps({"email": "user@example.com", "password": "secret"}),
            headers={"Content-Type": "application/json"},
        )
    assert response.status_code == 401
    data = json.loads(response.data)
    assert len(data["errors"]) > 0


def test_login_invalid_credentials(client, mock_db):
    """Test login with invalid credentials returns 401."""
    with patch("api.v2.auth.login.authenticate_corecloud", return_value=(None, "Invalid email or password")):
        response = client.post(
            "/v2/auth/login",
            data=json.dumps({"email": "user@example.com", "password": "wrong"}),
            headers={"Content-Type": "application/json"},
        )
    assert response.status_code == 401
    data = json.loads(response.data)
    assert len(data["errors"]) > 0


def test_login_user_not_found(client, mock_db):
    """Test login for unregistered user returns 403."""
    cc_result = {"email": "unregistered@example.com", "name": "Unknown", "role": "user"}
    with patch("api.v2.auth.login.authenticate_corecloud", return_value=(cc_result, None)):
        mock_db.user.find_unique.return_value = None

        response = client.post(
            "/v2/auth/login",
            data=json.dumps({"email": "unregistered@example.com", "password": "secret"}),
            headers={"Content-Type": "application/json"},
        )
    assert response.status_code == 403
    data = json.loads(response.data)
    assert len(data["errors"]) > 0


def test_login_inactive_user(client, mock_db):
    """Test login for inactive user returns 403."""
    cc_result = {"email": "inactive@example.com", "name": "Inactive", "role": "user"}
    with patch("api.v2.auth.login.authenticate_corecloud", return_value=(cc_result, None)):
        mock_db.user.find_unique.return_value = make_obj(
            id="user-inactive",
            email="inactive@example.com",
            name="Inactive User",
            active=False,
            permissionSetId="perm-1",
            createdAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
            permissionSet=make_obj(id="perm-1", name="Standard"),
        )

        response = client.post(
            "/v2/auth/login",
            data=json.dumps({"email": "inactive@example.com", "password": "secret"}),
            headers={"Content-Type": "application/json"},
        )
    assert response.status_code == 403
    data = json.loads(response.data)
    assert len(data["errors"]) > 0


def test_login_success(client, mock_db):
    """Test successful login returns token and user data."""
    cc_result = {"email": "user@example.com", "name": "Test User", "role": "admin"}
    with patch("api.v2.auth.login.authenticate_corecloud", return_value=(cc_result, None)):
        mock_db.user.find_unique.return_value = make_obj(
            id="user-1",
            email="user@example.com",
            name="Test User",
            active=True,
            permissionSetId="perm-1",
            createdAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
            lastSeenAt=None,
            permissionSet=make_obj(id="perm-1", name="Admin"),
        )
        mock_db.user.update.return_value = None

        with patch("api.v2.auth.login.log_audit"):
            response = client.post(
                "/v2/auth/login",
                data=json.dumps({"email": "user@example.com", "password": "secret"}),
                headers={"Content-Type": "application/json"},
            )

    assert response.status_code == 200
    data = json.loads(response.data)
    assert "data" in data
    assert "token" in data["data"]
    assert "user" in data["data"]
    assert data["data"]["user"]["id"] == "user-1"
    assert data["data"]["user"]["email"] == "user@example.com"
    assert data["data"]["user"]["permissionSetName"] == "Admin"
    mock_db.user.update.assert_called_once()


def test_login_updates_last_seen(client, mock_db):
    """Test that successful login updates lastSeenAt."""
    cc_result = {"email": "user@example.com", "name": "Test User", "role": "user"}
    with patch("api.v2.auth.login.authenticate_corecloud", return_value=(cc_result, None)):
        mock_db.user.find_unique.return_value = make_obj(
            id="user-1",
            email="user@example.com",
            name="Test User",
            active=True,
            permissionSetId="perm-1",
            createdAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
            lastSeenAt=None,
            permissionSet=make_obj(id="perm-1", name="User"),
        )
        mock_db.user.update.return_value = None

        with patch("api.v2.auth.login.log_audit"):
            response = client.post(
                "/v2/auth/login",
                data=json.dumps({"email": "user@example.com", "password": "secret"}),
                headers={"Content-Type": "application/json"},
            )

    assert response.status_code == 200
    mock_db.user.update.assert_called_once()
    update_call = mock_db.user.update.call_args
    assert "lastSeenAt" in update_call.kwargs["data"]
