"""Tests for Permission Sets API."""

import json
from datetime import datetime, timezone
from unittest.mock import patch

from src.lib.permissions import Permissions
from tests.conftest import make_obj

_all_perms = list(Permissions.all())


def test_list_permission_sets(authed_client, mock_db):
    """Test listing permission sets with pagination."""
    mock_db.permissionset.count.return_value = 2
    mock_db.permissionset.find_many.return_value = [
        make_obj(
            id="ps-1",
            name="Admin",
            description="Full access",
            permissions=["users:view", "users:manage"],
            users=[
                make_obj(id="u-1", name="Alice", email="alice@example.com"),
            ],
            createdAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
            updatedAt=datetime(2025, 1, 10, tzinfo=timezone.utc),
        ),
        make_obj(
            id="ps-2",
            name="Viewer",
            description=None,
            permissions=["users:view"],
            users=[],
            createdAt=datetime(2025, 1, 2, tzinfo=timezone.utc),
            updatedAt=datetime(2025, 1, 2, tzinfo=timezone.utc),
        ),
    ]

    response = authed_client.get("/v2/permissions")
    assert response.status_code == 200

    body = json.loads(response.data)
    assert "data" in body
    assert "data" in body["data"]
    assert "pagination" in body["data"]
    assert len(body["data"]["data"]) == 2
    assert body["data"]["pagination"]["total"] == 2

    first = body["data"]["data"][0]
    assert first["id"] == "ps-1"
    assert first["name"] == "Admin"
    assert first["userCount"] == 1


def test_create_permission_set(authed_client, mock_db):
    """Test creating a permission set."""
    mock_db.permissionset.find_unique.return_value = make_obj(
        id="test-perm-set-id",
        name="Test Admin",
        permissions=_all_perms,
    )

    created = make_obj(
        id="ps-new",
        name="Operators",
        description="Ops team",
        permissions=["users:view"],
        createdAt=datetime(2025, 2, 1, tzinfo=timezone.utc),
        updatedAt=datetime(2025, 2, 1, tzinfo=timezone.utc),
    )
    mock_db.permissionset.create.return_value = created

    # find_unique is used by auth decorator AND duplicate check.
    # Auth decorator lookup uses {"id": ...}, duplicate check uses {"name": ...}.
    # We use side_effect to return the right thing for each call.
    auth_perm_set = make_obj(
        id="test-perm-set-id",
        name="Test Admin",
        permissions=_all_perms,
    )

    def find_unique_side_effect(**kwargs):
        where = kwargs.get("where", {})
        if "id" in where:
            return auth_perm_set
        if "name" in where:
            return None  # no duplicate
        return None

    mock_db.permissionset.find_unique.side_effect = find_unique_side_effect

    with patch("api.v2.auth.permission_sets.log_audit"):
        response = authed_client.post(
            "/v2/permissions",
            data=json.dumps({
                "name": "Operators",
                "description": "Ops team",
                "permissions": ["users:view"],
            }),
        )

    assert response.status_code == 201
    body = json.loads(response.data)
    assert body["data"]["name"] == "Operators"
    assert body["data"]["description"] == "Ops team"


def test_create_permission_set_duplicate(authed_client, mock_db):
    """Test creating a permission set with duplicate name returns 409."""
    auth_perm_set = make_obj(
        id="test-perm-set-id",
        name="Test Admin",
        permissions=_all_perms,
    )
    existing = make_obj(
        id="ps-existing",
        name="Admin",
        permissions=["users:view"],
    )

    def find_unique_side_effect(**kwargs):
        where = kwargs.get("where", {})
        if "id" in where:
            return auth_perm_set
        if "name" in where:
            return existing  # duplicate found
        return None

    mock_db.permissionset.find_unique.side_effect = find_unique_side_effect

    with patch("api.v2.auth.permission_sets.log_audit"):
        response = authed_client.post(
            "/v2/permissions",
            data=json.dumps({
                "name": "Admin",
                "permissions": ["users:view"],
            }),
        )

    assert response.status_code == 409
    body = json.loads(response.data)
    assert len(body["errors"]) > 0


def test_update_permission_set(authed_client, mock_db):
    """Test updating a permission set."""
    existing = make_obj(
        id="ps-1",
        name="Old Name",
        description="Old desc",
        permissions=["users:view"],
        createdAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
        updatedAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
    )
    updated = make_obj(
        id="ps-1",
        name="New Name",
        description="New desc",
        permissions=["users:view", "users:manage"],
        createdAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
        updatedAt=datetime(2025, 2, 1, tzinfo=timezone.utc),
    )

    auth_perm_set = make_obj(
        id="test-perm-set-id",
        name="Test Admin",
        permissions=_all_perms,
    )

    def find_unique_side_effect(**kwargs):
        where = kwargs.get("where", {})
        if "id" in where:
            if where["id"] == "test-perm-set-id":
                return auth_perm_set
            if where["id"] == "ps-1":
                return existing
        if "name" in where:
            return None  # no duplicate
        return None

    mock_db.permissionset.find_unique.side_effect = find_unique_side_effect
    mock_db.permissionset.update.return_value = updated

    with patch("api.v2.auth.permission_sets.log_audit"):
        response = authed_client.put(
            "/v2/permissions/ps-1",
            data=json.dumps({
                "name": "New Name",
                "description": "New desc",
                "permissions": ["users:view", "users:manage"],
            }),
        )

    assert response.status_code == 200
    body = json.loads(response.data)
    assert body["data"]["name"] == "New Name"


def test_update_permission_set_not_found(authed_client, mock_db):
    """Test updating a non-existent permission set returns 404."""
    auth_perm_set = make_obj(
        id="test-perm-set-id",
        name="Test Admin",
        permissions=_all_perms,
    )

    def find_unique_side_effect(**kwargs):
        where = kwargs.get("where", {})
        if "id" in where:
            if where["id"] == "test-perm-set-id":
                return auth_perm_set
            return None  # not found
        return None

    mock_db.permissionset.find_unique.side_effect = find_unique_side_effect

    response = authed_client.put(
        "/v2/permissions/nonexistent",
        data=json.dumps({
            "name": "Updated",
        }),
    )

    assert response.status_code == 404
    body = json.loads(response.data)
    assert len(body["errors"]) > 0


def test_delete_permission_set(authed_client, mock_db):
    """Test deleting a permission set with no assigned users."""
    existing = make_obj(
        id="ps-1",
        name="To Delete",
        users=[],
    )

    auth_perm_set = make_obj(
        id="test-perm-set-id",
        name="Test Admin",
        permissions=_all_perms,
    )

    call_count = {"n": 0}

    def find_unique_side_effect(**kwargs):
        where = kwargs.get("where", {})
        if "id" in where:
            if where["id"] == "test-perm-set-id":
                return auth_perm_set
            if where["id"] == "ps-1":
                return existing
        return None

    mock_db.permissionset.find_unique.side_effect = find_unique_side_effect

    with patch("api.v2.auth.permission_sets.log_audit"):
        response = authed_client.delete("/v2/permissions/ps-1")

    assert response.status_code == 200
    body = json.loads(response.data)
    assert body["errors"] == []


def test_delete_permission_set_has_users(authed_client, mock_db):
    """Test deleting a permission set with assigned users returns 409."""
    existing = make_obj(
        id="ps-1",
        name="In Use",
        users=[
            make_obj(id="u-1", name="User", email="user@example.com"),
        ],
    )

    auth_perm_set = make_obj(
        id="test-perm-set-id",
        name="Test Admin",
        permissions=_all_perms,
    )

    def find_unique_side_effect(**kwargs):
        where = kwargs.get("where", {})
        if "id" in where:
            if where["id"] == "test-perm-set-id":
                return auth_perm_set
            if where["id"] == "ps-1":
                return existing
        return None

    mock_db.permissionset.find_unique.side_effect = find_unique_side_effect

    response = authed_client.delete("/v2/permissions/ps-1")

    assert response.status_code == 409
    body = json.loads(response.data)
    assert len(body["errors"]) > 0
