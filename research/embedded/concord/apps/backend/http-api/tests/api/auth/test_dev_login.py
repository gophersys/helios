"""Tests for dev-login endpoints (POST /v2/auth/dev-login, GET /v2/auth/dev-users)."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from tests.conftest import make_obj


def _dev_user(**overrides):
    defaults = dict(
        id="dev-user-1",
        email="admin@concord.dev",
        name="Admin Dev",
        role="ADMIN",
        active=True,
        permissionSetId="ps-admin",
        permissionSet=make_obj(id="ps-admin", name="Admin", permissions=[]),
    )
    defaults.update(overrides)
    return make_obj(**defaults)


class TestDevLogin:
    """Tests for POST /v2/auth/dev-login."""

    def test_dev_login_disabled_when_auth_enabled(self, client, mock_db):
        """POST /v2/auth/dev-login returns 403 when AUTH_ENABLED=true."""
        # conftest.py sets AUTH_ENABLED=true by default
        response = client.post(
            "/v2/auth/dev-login",
            data=json.dumps({"email": "admin@concord.dev"}),
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == 403
        body = json.loads(response.data)
        assert len(body["errors"]) > 0

    def test_dev_login_enabled_when_auth_disabled(self, client, mock_db):
        """POST /v2/auth/dev-login succeeds when AUTH_ENABLED=false."""
        mock_db.user.find_unique.return_value = _dev_user()

        with patch("config.env_config.AUTH_ENABLED", False):
            response = client.post(
                "/v2/auth/dev-login",
                data=json.dumps({"email": "admin@concord.dev"}),
                headers={"Content-Type": "application/json"},
            )

        assert response.status_code == 200
        body = json.loads(response.data)
        assert "token" in body["data"]
        assert body["data"]["user"]["email"] == "admin@concord.dev"

    def test_dev_login_missing_email_returns_400(self, client, mock_db):
        """POST /v2/auth/dev-login without email returns 400."""
        with patch("config.env_config.AUTH_ENABLED", False):
            response = client.post(
                "/v2/auth/dev-login",
                data=json.dumps({}),
                headers={"Content-Type": "application/json"},
            )

        assert response.status_code == 400
        body = json.loads(response.data)
        assert len(body["errors"]) > 0

    def test_dev_login_user_not_found_returns_404(self, client, mock_db):
        """POST /v2/auth/dev-login with unknown email returns 404."""
        mock_db.user.find_unique.return_value = None

        with patch("config.env_config.AUTH_ENABLED", False):
            response = client.post(
                "/v2/auth/dev-login",
                data=json.dumps({"email": "unknown@concord.dev"}),
                headers={"Content-Type": "application/json"},
            )

        assert response.status_code == 404

    def test_dev_login_inactive_user_returns_403(self, client, mock_db):
        """POST /v2/auth/dev-login with inactive user account returns 403."""
        mock_db.user.find_unique.return_value = _dev_user(active=False)

        with patch("config.env_config.AUTH_ENABLED", False):
            response = client.post(
                "/v2/auth/dev-login",
                data=json.dumps({"email": "admin@concord.dev"}),
                headers={"Content-Type": "application/json"},
            )

        assert response.status_code == 403

    def test_dev_login_returns_user_details(self, client, mock_db):
        """POST /v2/auth/dev-login response includes user id, email, name, role."""
        mock_db.user.find_unique.return_value = _dev_user(
            role="MAINTAINER", name="Maintainer Dev", email="maintainer@concord.dev"
        )

        with patch("config.env_config.AUTH_ENABLED", False):
            response = client.post(
                "/v2/auth/dev-login",
                data=json.dumps({"email": "maintainer@concord.dev"}),
                headers={"Content-Type": "application/json"},
            )

        assert response.status_code == 200
        body = json.loads(response.data)
        user = body["data"]["user"]
        assert user["role"] == "MAINTAINER"
        assert user["name"] == "Maintainer Dev"

    # TODO: test_dev_login_empty_body_returns_400


class TestDevUsers:
    """Tests for GET /v2/auth/dev-users."""

    def test_dev_users_disabled_when_auth_enabled(self, client, mock_db):
        """GET /v2/auth/dev-users returns 403 when AUTH_ENABLED=true."""
        response = client.get("/v2/auth/dev-users")
        assert response.status_code == 403

    def test_dev_users_returns_user_list(self, client, mock_db):
        """GET /v2/auth/dev-users returns list of dev sample users."""
        mock_db.user.find_many.return_value = [
            _dev_user(role="ADMIN"),
            _dev_user(id="dev-2", email="developer@concord.dev", role="DEVELOPER", name="Dev User"),
        ]

        with patch("config.env_config.AUTH_ENABLED", False):
            response = client.get("/v2/auth/dev-users")

        assert response.status_code == 200
        body = json.loads(response.data)
        assert "users" in body["data"]
        assert len(body["data"]["users"]) == 2

    def test_dev_users_includes_environment(self, client, mock_db):
        """GET /v2/auth/dev-users response includes environment name."""
        mock_db.user.find_many.return_value = []

        with patch("config.env_config.AUTH_ENABLED", False):
            response = client.get("/v2/auth/dev-users")

        assert response.status_code == 200
        body = json.loads(response.data)
        assert "environment" in body["data"]

    # TODO: test_dev_users_sorted_by_role_hierarchy
    # TODO: test_dev_users_empty_list_when_no_seed
