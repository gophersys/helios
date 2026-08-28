"""Tests for GET /v2/auth/me endpoint."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from tests.conftest import make_obj


def _user_obj(**overrides):
    defaults = dict(
        id="test-user-id",
        email="test@example.com",
        name="Test User",
        role="DEVELOPER",
        active=True,
        permissionSetId="test-perm-set-id",
        permissionSet=make_obj(id="test-perm-set-id", name="Developer", permissions=["ADMIN_PRODUCTS_VIEW"]),
        productAccess=[],
        lastSeenAt=None,
        createdAt=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    defaults.update(overrides)
    return make_obj(**defaults)


class TestMe:
    """Tests for GET /v2/auth/me."""

    def test_me_returns_current_user(self, authed_client, mock_db):
        """GET /v2/auth/me returns the authenticated user's profile."""
        mock_db.user.find_unique.return_value = _user_obj()

        response = authed_client.get("/v2/auth/me")

        assert response.status_code == 200
        body = json.loads(response.data)
        assert body["data"]["id"] == "test-user-id"
        assert body["data"]["email"] == "test@example.com"
        assert body["data"]["name"] == "Test User"
        assert body["data"]["role"] == "DEVELOPER"
        assert body["data"]["active"] is True

    def test_me_user_not_found_returns_404(self, authed_client, mock_db):
        """GET /v2/auth/me returns 404 when user record is missing from DB."""
        mock_db.user.find_unique.return_value = None

        response = authed_client.get("/v2/auth/me")

        assert response.status_code == 404
        body = json.loads(response.data)
        assert len(body["errors"]) > 0

    def test_me_without_auth_returns_401(self, client, mock_db):
        """GET /v2/auth/me without auth header returns 401."""
        response = client.get("/v2/auth/me")
        assert response.status_code == 401

    def test_me_includes_product_access(self, authed_client, mock_db):
        """GET /v2/auth/me includes product access entries."""
        product_access = [
            make_obj(
                id="pa-1",
                productId="prod-1",
                level="FULL",
                product=make_obj(id="prod-1", name="Alpha", slug="alpha"),
            )
        ]
        mock_db.user.find_unique.return_value = _user_obj(productAccess=product_access)

        response = authed_client.get("/v2/auth/me")

        assert response.status_code == 200
        body = json.loads(response.data)
        access = body["data"]["productAccess"]
        assert len(access) == 1
        assert access[0]["productId"] == "prod-1"
        assert access[0]["productName"] == "Alpha"

    def test_me_includes_permissions_list(self, authed_client, mock_db):
        """GET /v2/auth/me includes the permission list from the permission set."""
        perms = ["ADMIN_PRODUCTS_VIEW", "ADMIN_PRODUCTS_MANAGE"]
        mock_db.user.find_unique.return_value = _user_obj(
            permissionSet=make_obj(id="ps-1", name="Admin", permissions=perms)
        )

        response = authed_client.get("/v2/auth/me")

        assert response.status_code == 200
        body = json.loads(response.data)
        assert "ADMIN_PRODUCTS_VIEW" in body["data"]["permissions"]

    def test_me_admin_view_as_developer(self, authed_client, mock_db):
        """Admin user with X-View-As-Role header returns effective developer permissions."""
        target_perm_set = make_obj(id="dev-ps", name="Developer", permissions=["ADMIN_PRODUCTS_VIEW"])
        mock_db.user.find_unique.return_value = _user_obj(role="ADMIN")
        mock_db.permissionset.find_first.return_value = target_perm_set

        response = authed_client.get(
            "/v2/auth/me",
            headers={"X-View-As-Role": "DEVELOPER"},
        )

        assert response.status_code == 200
        body = json.loads(response.data)
        assert body["data"]["viewAsRole"] == "DEVELOPER"

    def test_me_developer_view_as_ignored(self, authed_client, mock_db):
        """Developer user with X-View-As-Role header — view-as is not applied."""
        mock_db.user.find_unique.return_value = _user_obj(role="DEVELOPER")

        response = authed_client.get(
            "/v2/auth/me",
            headers={"X-View-As-Role": "ADMIN"},
        )

        assert response.status_code == 200
        body = json.loads(response.data)
        # DEVELOPER cannot use view-as, so viewAsRole should be None
        assert body["data"]["viewAsRole"] is None

    def test_me_last_seen_at_isoformat(self, authed_client, mock_db):
        """GET /v2/auth/me serializes lastSeenAt as ISO string."""
        last_seen = datetime(2026, 3, 15, 10, 30, 0, tzinfo=timezone.utc)
        mock_db.user.find_unique.return_value = _user_obj(lastSeenAt=last_seen)

        response = authed_client.get("/v2/auth/me")

        assert response.status_code == 200
        body = json.loads(response.data)
        assert body["data"]["lastSeenAt"] == last_seen.isoformat()

    # TODO: test_me_no_permission_set_returns_empty_permissions
    # TODO: test_me_auth_disabled_returns_mock_admin
