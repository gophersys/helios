"""Integration tests for Users API."""

import json
from datetime import datetime, timezone
from unittest.mock import patch

from src.lib.permissions import Permissions
from tests.conftest import make_obj

# All permission keys for the superadmin mock
_all_perms = [p["key"] for p in Permissions.all()]


def test_list_users(authed_client, mock_db):
    """Test listing users with pagination."""
    mock_db.user.count.return_value = 2
    mock_db.user.find_many.return_value = [
        make_obj(
            id="user-1",
            email="user1@example.com",
            name="User One",
            active=True,
            externalId="google-1",
            permissionSetId="perm-1",
            lastSeenAt=datetime(2025, 1, 15, tzinfo=timezone.utc),
            createdAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
            updatedAt=datetime(2025, 1, 15, tzinfo=timezone.utc),
            permissionSet=make_obj(
                id="perm-1",
                name="Admin",
            ),
        ),
        make_obj(
            id="user-2",
            email="user2@example.com",
            name="User Two",
            active=False,
            externalId=None,
            permissionSetId="perm-2",
            lastSeenAt=None,
            createdAt=datetime(2025, 1, 2, tzinfo=timezone.utc),
            updatedAt=datetime(2025, 1, 2, tzinfo=timezone.utc),
            permissionSet=make_obj(
                id="perm-2",
                name="Viewer",
            ),
        ),
    ]

    response = authed_client.get("/v2/auth/users")
    assert response.status_code == 200

    data = json.loads(response.data)
    assert "data" in data
    assert "data" in data["data"]
    assert "pagination" in data["data"]
    assert len(data["data"]["data"]) == 2
    assert data["data"]["pagination"]["total"] == 2


def test_create_user(authed_client, mock_db):
    """Test creating a new user."""
    # user.find_unique returns None (no duplicate email)
    mock_db.user.find_unique.return_value = None

    # permissionset.find_unique is used both by the auth decorator (cache) and
    # by the handler itself.  Always include the `permissions` field so the
    # auth decorator doesn't break.
    mock_db.permissionset.find_unique.return_value = make_obj(
        id="perm-1",
        name="Admin",
        permissions=_all_perms,
    )

    mock_db.user.create.return_value = make_obj(
        id="user-new",
        email="newuser@example.com",
        name="New User",
        active=True,
        externalId=None,
        permissionSetId="perm-1",
        lastSeenAt=None,
        createdAt=datetime(2025, 1, 15, tzinfo=timezone.utc),
        updatedAt=datetime(2025, 1, 15, tzinfo=timezone.utc),
        permissionSet=make_obj(
            id="perm-1",
            name="Admin",
        ),
    )

    with patch("api.v2.auth.users.log_audit"):
        response = authed_client.post(
            "/v2/auth/users",
            data=json.dumps({
                "email": "newuser@example.com",
                "name": "New User",
                "permissionSetId": "perm-1",
            }),
        )

    assert response.status_code == 201
    data = json.loads(response.data)
    assert data["data"]["email"] == "newuser@example.com"
    assert data["data"]["name"] == "New User"


def test_create_user_duplicate_email(authed_client, mock_db):
    """Test creating user with duplicate email returns 409."""
    mock_db.user.find_unique.return_value = make_obj(
        id="existing-user",
        email="existing@example.com",
        name="Existing User",
        active=True,
        externalId=None,
        permissionSetId="perm-1",
        lastSeenAt=None,
        createdAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
        updatedAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
    )

    response = authed_client.post(
        "/v2/auth/users",
        data=json.dumps({
            "email": "existing@example.com",
            "name": "Another User",
        }),
    )

    assert response.status_code == 409
    data = json.loads(response.data)
    assert len(data["errors"]) > 0


def test_update_user(authed_client, mock_db):
    """Test updating a user."""
    existing = make_obj(
        id="user-1",
        email="user@example.com",
        name="Old Name",
        active=True,
        externalId="google-1",
        permissionSetId="perm-1",
        lastSeenAt=datetime(2025, 1, 10, tzinfo=timezone.utc),
        createdAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
        updatedAt=datetime(2025, 1, 10, tzinfo=timezone.utc),
    )
    mock_db.user.find_unique.return_value = existing

    # Include `permissions` so the auth decorator also works
    mock_db.permissionset.find_unique.return_value = make_obj(
        id="perm-2",
        name="Viewer",
        permissions=_all_perms,
    )

    mock_db.user.update.return_value = make_obj(
        id="user-1",
        email="user@example.com",
        name="New Name",
        active=True,
        externalId="google-1",
        permissionSetId="perm-2",
        lastSeenAt=datetime(2025, 1, 10, tzinfo=timezone.utc),
        createdAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
        updatedAt=datetime(2025, 1, 15, tzinfo=timezone.utc),
        permissionSet=make_obj(
            id="perm-2",
            name="Viewer",
        ),
    )

    with patch("api.v2.auth.users.log_audit"):
        response = authed_client.put(
            "/v2/auth/users/user-1",
            data=json.dumps({
                "name": "New Name",
                "permissionSetId": "perm-2",
            }),
        )

    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["data"]["name"] == "New Name"


def test_delete_user(authed_client, mock_db):
    """Test soft deleting a user."""
    mock_db.user.find_unique.return_value = make_obj(
        id="user-to-delete",
        email="delete@example.com",
        name="User To Delete",
        active=True,
        externalId="google-2",
        permissionSetId="perm-1",
        lastSeenAt=datetime(2025, 1, 10, tzinfo=timezone.utc),
        createdAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
        updatedAt=datetime(2025, 1, 10, tzinfo=timezone.utc),
    )

    mock_db.user.update.return_value = None

    with patch("api.v2.auth.users.log_audit"):
        response = authed_client.delete("/v2/auth/users/user-to-delete")

    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["errors"] == []


def test_delete_user_self(authed_client, mock_db):
    """Test that users cannot delete themselves."""
    mock_db.user.find_unique.return_value = make_obj(
        id="test-user-id",
        email="test@example.com",
        name="Test User",
        active=True,
        externalId="google-1",
        permissionSetId="perm-1",
        lastSeenAt=datetime(2025, 1, 10, tzinfo=timezone.utc),
        createdAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
        updatedAt=datetime(2025, 1, 10, tzinfo=timezone.utc),
    )

    response = authed_client.delete("/v2/auth/users/test-user-id")
    assert response.status_code == 400
    data = json.loads(response.data)
    assert len(data["errors"]) > 0
