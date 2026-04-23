"""Tests for manufacturing config CRUD — /v2/products/<id>/manufacturing."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from tests.conftest import make_obj


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now():
    return datetime(2026, 1, 1, tzinfo=timezone.utc)


def _product(**overrides):
    defaults = dict(id="s10-prod-1", name="s10-Alpha B0", slug="s10-alpha-b0")
    defaults.update(overrides)
    return make_obj(**defaults)


def _config(**overrides):
    defaults = dict(
        id="s10-cfg-1",
        productId="s10-prod-1",
        boardRevisionId="s10-rev-1",
        enabled=False,
        stages=[{"name": "Electrical", "enabled": True, "config": {}}],
        firmwareSource="latest_build",
        firmwareSetId=None,
        personalizationConfig=None,
        passCriteria=None,
        createdAt=_now(),
        updatedAt=_now(),
        product=_product(),
        boardRevision=make_obj(id="s10-rev-1", version="B0"),
    )
    defaults.update(overrides)
    return make_obj(**defaults)


@pytest.fixture(autouse=True)
def _mock_audit():
    with patch("api.v2.products.manufacturing_config.log_audit"):
        yield


# ---------------------------------------------------------------------------
# GET /v2/products/<id>/manufacturing — get config
# ---------------------------------------------------------------------------

class TestGetConfig:
    def test_returns_config_when_exists(self, authed_client, mock_db):
        mock_db.product.find_unique.return_value = _product()
        mock_db.manufacturingconfig.find_unique.return_value = _config()

        resp = authed_client.get("/v2/products/s10-prod-1/manufacturing")
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert data["id"] == "s10-cfg-1"
        assert data["enabled"] is False

    def test_returns_404_when_product_not_found(self, authed_client, mock_db):
        mock_db.product.find_unique.return_value = None

        resp = authed_client.get("/v2/products/s10-missing/manufacturing")
        assert resp.status_code == 404

    def test_returns_404_when_config_not_found(self, authed_client, mock_db):
        mock_db.product.find_unique.return_value = _product()
        mock_db.manufacturingconfig.find_unique.return_value = None

        resp = authed_client.get("/v2/products/s10-prod-1/manufacturing")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# POST /v2/products/<id>/manufacturing — create config
# ---------------------------------------------------------------------------

class TestCreateConfig:
    def test_creates_config(self, authed_client, mock_db):
        mock_db.product.find_unique.return_value = _product()
        mock_db.manufacturingconfig.find_unique.return_value = None
        created = _config()
        mock_db.manufacturingconfig.create.return_value = created

        resp = authed_client.post(
            "/v2/products/s10-prod-1/manufacturing",
            data=json.dumps({
                "boardRevisionId": "s10-rev-1",
                "stages": [{"name": "Electrical", "enabled": True, "config": {}}],
            }),
        )
        assert resp.status_code == 201

    def test_returns_409_when_config_exists(self, authed_client, mock_db):
        mock_db.product.find_unique.return_value = _product()
        mock_db.manufacturingconfig.find_unique.return_value = _config()

        resp = authed_client.post(
            "/v2/products/s10-prod-1/manufacturing",
            data=json.dumps({"boardRevisionId": "s10-rev-1", "stages": []}),
        )
        assert resp.status_code == 409

    def test_returns_400_missing_board_revision(self, authed_client, mock_db):
        mock_db.product.find_unique.return_value = _product()
        mock_db.manufacturingconfig.find_unique.return_value = None

        resp = authed_client.post(
            "/v2/products/s10-prod-1/manufacturing",
            data=json.dumps({"stages": []}),
        )
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# PUT /v2/products/<id>/manufacturing — update config
# ---------------------------------------------------------------------------

class TestUpdateConfig:
    def test_updates_config(self, authed_client, mock_db):
        mock_db.product.find_unique.return_value = _product()
        existing = _config()
        mock_db.manufacturingconfig.find_first.return_value = existing
        updated = _config(enabled=True)
        mock_db.manufacturingconfig.update.return_value = updated

        resp = authed_client.put(
            "/v2/products/s10-prod-1/manufacturing",
            data=json.dumps({"enabled": True}),
        )
        assert resp.status_code == 200

    def test_returns_404_when_config_missing(self, authed_client, mock_db):
        mock_db.product.find_unique.return_value = _product()
        mock_db.manufacturingconfig.find_first.return_value = None

        resp = authed_client.put(
            "/v2/products/s10-prod-1/manufacturing",
            data=json.dumps({"enabled": True}),
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /v2/products/<id>/manufacturing — delete config
# ---------------------------------------------------------------------------

class TestDeleteConfig:
    def test_deletes_config(self, authed_client, mock_db):
        mock_db.product.find_unique.return_value = _product()
        mock_db.manufacturingconfig.find_first.return_value = _config()
        mock_db.manufacturingconfig.delete.return_value = _config()

        resp = authed_client.delete("/v2/products/s10-prod-1/manufacturing")
        assert resp.status_code == 200

    def test_returns_404_when_config_missing(self, authed_client, mock_db):
        mock_db.product.find_unique.return_value = _product()
        mock_db.manufacturingconfig.find_first.return_value = None

        resp = authed_client.delete("/v2/products/s10-prod-1/manufacturing")
        assert resp.status_code == 404
