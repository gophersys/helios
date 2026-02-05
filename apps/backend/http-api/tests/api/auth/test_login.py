"""Integration tests for Login API."""

import json
from datetime import datetime, timezone
from unittest.mock import patch

from tests.conftest import make_obj


def test_login_missing_credential(client):
    """Test login with missing credential returns 400."""
    response = client.post(
        "/v2/auth/login",
        data=json.dumps({}),
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 400
    data = json.loads(response.data)
    assert len(data["errors"]) > 0


def test_login_invalid_google_token(client, mock_db):
    """Test login with invalid Google token returns 401."""
    with patch("api.v2.auth.login.verify_google_token", return_value=(None, "Invalid token")):
        response = client.post(
            "/v2/auth/login",
            data=json.dumps({"credential": "invalid-token"}),
            headers={"Content-Type": "application/json"},
        )

    assert response.status_code == 401
    data = json.loads(response.data)
    assert len(data["errors"]) > 0


def test_login_user_not_found(client, mock_db):
    """Test login for unregistered user returns 403."""
    with patch("api.v2.auth.login.verify_google_token", return_value=(
        {
            "sub": "google-123",
            "email": "unregistered@example.com",
            "name": "Unregistered User",
        },
        None,
    )):
        mock_db.user.find_unique.return_value = None

        response = client.post(
            "/v2/auth/login",
            data=json.dumps({"credential": "valid-google-token"}),
            headers={"Content-Type": "application/json"},
        )

    assert response.status_code == 403
    data = json.loads(response.data)
    assert len(data["errors"]) > 0


def test_login_inactive_user(client, mock_db):
    """Test login for inactive user returns 403."""
    with patch("api.v2.auth.login.verify_google_token", return_value=(
        {
            "sub": "google-123",
            "email": "inactive@example.com",
            "name": "Inactive User",
        },
        None,
    )):
        mock_db.user.find_unique.return_value = make_obj(
            id="user-inactive",
            email="inactive@example.com",
            name="Inactive User",
            active=False,
            externalId=None,
            permissionSetId="perm-1",
            createdAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
            updatedAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
            permissionSet=make_obj(
                id="perm-1",
                name="Standard User",
            ),
        )

        response = client.post(
            "/v2/auth/login",
            data=json.dumps({"credential": "valid-google-token"}),
            headers={"Content-Type": "application/json"},
        )

    assert response.status_code == 403
    data = json.loads(response.data)
    assert len(data["errors"]) > 0


def test_login_success(client, mock_db):
    """Test successful login returns token and user data."""
    with patch("api.v2.auth.login.verify_google_token", return_value=(
        {
            "sub": "google-123",
            "email": "user@example.com",
            "name": "Test User",
        },
        None,
    )):
        mock_db.user.find_unique.return_value = make_obj(
            id="user-1",
            email="user@example.com",
            name="Test User",
            active=True,
            externalId=None,
            permissionSetId="perm-1",
            createdAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
            updatedAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
            lastSeenAt=None,
            permissionSet=make_obj(
                id="perm-1",
                name="Admin",
            ),
        )

        mock_db.user.update.return_value = None

        with patch("api.v2.auth.login.log_audit"):
            response = client.post(
                "/v2/auth/login",
                data=json.dumps({"credential": "valid-google-token"}),
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
