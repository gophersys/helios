"""Integration tests for the Users CRUD API.

Covers: users_list, users_create, users_update, users_set_role, users_delete,
users_get_product_access, users_set_product_access.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from src.lib.permissions import Permissions
from tests.conftest import make_obj

NOW = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
_all_perms = list(Permissions.all())


def _make_user(**overrides):
    defaults = dict(
        id="user-1",
        email="alice@example.com",
        name="Alice",
        role="DEVELOPER",
        active=True,
        externalId=None,
        permissionSetId="perm-1",
        lastSeenAt=None,
        createdAt=NOW,
        updatedAt=NOW,
        permissionSet=make_obj(id="perm-1", name="Developers", permissions=_all_perms),
    )
    defaults.update(overrides)
    return make_obj(**defaults)


class TestUsersCreate:
    """Tests for POST /v2/users (users_create)."""

    def test_create_user_success(self, authed_client, mock_db):
        """users_create registers a new user and returns 201."""
        mock_db.user.find_unique.return_value = None  # no duplicate
        mock_db.permissionset.find_unique.return_value = make_obj(
            id="perm-1", name="Developers", permissions=_all_perms
        )
        new_user = _make_user()
        mock_db.user.create.return_value = new_user

        with patch("api.v2.auth.users.log_audit"):
            response = authed_client.post(
                "/v2/users",
                data=json.dumps({
                    "email": "alice@example.com",
                    "name": "Alice",
                    "role": "DEVELOPER",
                    "permissionSetId": "perm-1",
                }),
            )

        assert response.status_code == 201
        data = json.loads(response.data)
        assert data["data"]["email"] == "alice@example.com"
        assert data["data"]["name"] == "Alice"

    def test_create_user_duplicate_email_returns_409(self, authed_client, mock_db):
        """users_create returns 409 when email already exists."""
        mock_db.user.find_unique.return_value = _make_user()

        response = authed_client.post(
            "/v2/users",
            data=json.dumps({"email": "alice@example.com", "name": "Alice"}),
        )

        assert response.status_code == 409

    def test_create_user_missing_email_returns_400(self, authed_client, mock_db):
        """users_create returns 400 when email is absent."""
        response = authed_client.post(
            "/v2/users",
            data=json.dumps({"name": "Alice"}),
        )

        assert response.status_code == 400

    def test_create_user_invalid_role_returns_400(self, authed_client, mock_db):
        """users_create returns 400 for an unrecognized role value."""
        mock_db.user.find_unique.return_value = None

        response = authed_client.post(
            "/v2/users",
            data=json.dumps({"email": "new@example.com", "name": "New", "role": "SUPERUSER"}),
        )

        assert response.status_code == 400

    def test_create_user_unknown_permission_set_returns_400(self, authed_client, mock_db):
        """users_create returns 400 when permissionSetId does not exist."""
        mock_db.user.find_unique.return_value = None
        mock_db.permissionset.find_unique.side_effect = [
            # First call is from authed_client perm check — return valid perm set
            make_obj(id="test-perm-set-id", name="Test Admin", permissions=_all_perms),
            None,  # Second call is from users_create — not found
        ]

        response = authed_client.post(
            "/v2/users",
            data=json.dumps({
                "email": "new@example.com",
                "name": "New",
                "permissionSetId": "nonexistent",
            }),
        )

        assert response.status_code == 400


class TestUsersUpdate:
    """Tests for PATCH /v2/users/<id> (users_update)."""

    def test_update_user_name(self, authed_client, mock_db):
        """users_update updates the user's name successfully."""
        mock_db.user.find_unique.return_value = _make_user()
        updated = _make_user(name="Alice Updated")
        mock_db.user.update.return_value = updated

        with patch("api.v2.auth.users.log_audit"):
            response = authed_client.put(
                "/v2/users/user-1",
                data=json.dumps({"name": "Alice Updated"}),
            )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["data"]["name"] == "Alice Updated"

    def test_update_user_not_found(self, authed_client, mock_db):
        """users_update returns 404 when user does not exist."""
        mock_db.user.find_unique.return_value = None

        response = authed_client.put(
            "/v2/users/bad-id",
            data=json.dumps({"name": "Ghost"}),
        )

        assert response.status_code == 404

    def test_update_user_cannot_deactivate_self(self, authed_client, mock_db):
        """users_update returns 400 when admin tries to deactivate own account."""
        # The auth token is for "test-user-id"
        mock_db.user.find_unique.return_value = _make_user(id="test-user-id")

        response = authed_client.put(
            "/v2/users/test-user-id",
            data=json.dumps({"active": False}),
        )

        assert response.status_code == 400


class TestUsersSetRole:
    """Tests for PUT /v2/users/<id>/role (users_set_role)."""

    def test_set_role_success(self, authed_client, mock_db):
        """users_set_role updates the user role and returns 200."""
        mock_db.user.find_unique.return_value = _make_user(id="other-user", role="DEVELOPER")
        updated = _make_user(id="other-user", role="MAINTAINER")
        mock_db.user.update.return_value = updated

        with patch("api.v2.auth.users.log_audit"):
            response = authed_client.put(
                "/v2/users/other-user/role",
                data=json.dumps({"role": "MAINTAINER"}),
            )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["data"]["role"] == "MAINTAINER"

    def test_set_role_invalid_returns_400(self, authed_client, mock_db):
        """users_set_role returns 400 for unrecognized roles."""
        response = authed_client.put(
            "/v2/users/other-user/role",
            data=json.dumps({"role": "GODMODE"}),
        )

        assert response.status_code == 400

    def test_set_role_user_not_found(self, authed_client, mock_db):
        """users_set_role returns 404 when user does not exist."""
        mock_db.user.find_unique.return_value = None

        response = authed_client.put(
            "/v2/users/bad-id/role",
            data=json.dumps({"role": "ADMIN"}),
        )

        assert response.status_code == 404

    def test_set_role_cannot_change_own_role(self, authed_client, mock_db):
        """users_set_role returns 400 when user attempts to change their own role."""
        mock_db.user.find_unique.return_value = _make_user(id="test-user-id", role="DEVELOPER")

        response = authed_client.put(
            "/v2/users/test-user-id/role",
            data=json.dumps({"role": "ADMIN"}),
        )

        assert response.status_code == 400


class TestUsersDelete:
    """Tests for DELETE /v2/users/<id> (users_delete)."""

    def test_delete_user_success(self, authed_client, mock_db):
        """users_delete deactivates the user and returns 200."""
        mock_db.user.find_unique.return_value = _make_user(id="other-user")

        with patch("api.v2.auth.users.log_audit"):
            response = authed_client.delete("/v2/users/other-user")

        assert response.status_code == 200
        mock_db.user.update.assert_called_once()
        update_data = mock_db.user.update.call_args[1]["data"]
        assert update_data["active"] is False

    def test_delete_user_not_found(self, authed_client, mock_db):
        """users_delete returns 404 when user does not exist."""
        mock_db.user.find_unique.return_value = None

        response = authed_client.delete("/v2/users/bad-id")

        assert response.status_code == 404

    def test_delete_cannot_deactivate_self(self, authed_client, mock_db):
        """users_delete returns 400 when user tries to delete their own account."""
        mock_db.user.find_unique.return_value = _make_user(id="test-user-id")

        response = authed_client.delete("/v2/users/test-user-id")

        assert response.status_code == 400


class TestUsersProductAccess:
    """Tests for GET/PUT /v2/users/<id>/product-access."""

    def test_get_product_access_success(self, authed_client, mock_db):
        """users_get_product_access returns list of product access entries."""
        mock_db.user.find_unique.return_value = _make_user()
        mock_db.productaccess.find_many.return_value = [
            make_obj(
                id="pa-1",
                userId="user-1",
                productId="prod-1",
                level="develop",
                createdAt=NOW,
                updatedAt=NOW,
                product=make_obj(id="prod-1", name="Alpha", slug="alpha"),
            ),
        ]

        response = authed_client.get("/v2/users/user-1/product-access")

        assert response.status_code == 200
        data = json.loads(response.data)
        assert len(data["data"]) == 1
        assert data["data"][0]["level"] == "develop"

    def test_set_product_access_replaces_entries(self, authed_client, mock_db):
        """users_set_product_access replaces all existing access entries."""
        mock_db.user.find_unique.return_value = _make_user()
        mock_db.product.find_unique.return_value = make_obj(id="prod-1", name="Alpha")
        new_entry = make_obj(
            id="pa-new",
            userId="user-1",
            productId="prod-1",
            level="view",
            createdAt=NOW,
            updatedAt=NOW,
            product=make_obj(id="prod-1", name="Alpha"),
        )
        mock_db.productaccess.create.return_value = new_entry

        with patch("api.v2.auth.users.log_audit"):
            response = authed_client.put(
                "/v2/users/user-1/product-access",
                data=json.dumps({
                    "access": [{"productId": "prod-1", "level": "view"}],
                }),
            )

        assert response.status_code == 200
        mock_db.productaccess.delete_many.assert_called_once()
        data = json.loads(response.data)
        assert len(data["data"]) == 1
