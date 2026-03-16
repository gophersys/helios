"""Tests for product stage config API endpoints."""
import json
import types
import pytest
from tests.conftest import make_obj


class TestListStageConfigs:
    def test_returns_configs_for_product(self, authed_client, mock_db):
        mock_db.product.find_unique.return_value = make_obj(id="prod-1", name="Alpha")
        mock_db.productstageconfig.find_many.return_value = [
            make_obj(id="sc-1", productId="prod-1", stage=1, name="Smoke", enabled=True,
                     buildScript=None, buildTarget="native_sim", fwRepoUrl=None, fwRepoBranch=None,
                     mfgRepoUrl=None, mfgRepoBranch=None, buildVariant="test", configFlags=None,
                     buildMatrix=None, testDirectory="tests/stage1/", testMarker=None,
                     testTimeout=120, priority=10, blocksMerge=True, requiresFuota=False,
                     requiresBench=False, maxDurationSec=300, description=None,
                     createdAt="2026-01-01T00:00:00Z", updatedAt="2026-01-01T00:00:00Z"),
        ]
        resp = authed_client.get("/v2/products/prod-1/stages")
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data["data"]) == 1
        assert data["data"][0]["stage"] == 1

    def test_product_not_found(self, authed_client, mock_db):
        mock_db.product.find_unique.return_value = None
        resp = authed_client.get("/v2/products/bad-id/stages")
        assert resp.status_code == 404


class TestCreateStageConfig:
    def test_creates_config(self, authed_client, mock_db):
        mock_db.product.find_unique.return_value = make_obj(id="prod-1", name="Alpha")
        mock_db.productstageconfig.find_first.return_value = None  # No existing
        mock_db.productstageconfig.create.return_value = make_obj(
            id="sc-new", productId="prod-1", stage=5, name="FUOTA", enabled=True,
            buildScript=None, buildTarget="alpha_b0", fwRepoUrl=None, fwRepoBranch=None,
            mfgRepoUrl=None, mfgRepoBranch=None, buildVariant="release", configFlags=None,
            buildMatrix=None, testDirectory="tests/stage5/", testMarker=None,
            testTimeout=900, priority=100, blocksMerge=True, requiresFuota=True,
            requiresBench=True, maxDurationSec=900, description=None,
            createdAt="2026-01-01T00:00:00Z", updatedAt="2026-01-01T00:00:00Z",
        )
        resp = authed_client.post("/v2/products/prod-1/stages", json={
            "stage": 5, "name": "FUOTA", "priority": 100,
            "blocksMerge": True, "requiresFuota": True,
        })
        assert resp.status_code == 201

    def test_rejects_duplicate_stage(self, authed_client, mock_db):
        mock_db.product.find_unique.return_value = make_obj(id="prod-1", name="Alpha")
        mock_db.productstageconfig.find_first.return_value = make_obj(id="existing")
        resp = authed_client.post("/v2/products/prod-1/stages", json={
            "stage": 5, "name": "FUOTA",
        })
        assert resp.status_code == 409


class TestInitializeStages:
    def test_creates_all_five_stages(self, authed_client, mock_db):
        mock_db.product.find_unique.return_value = make_obj(id="prod-1", name="Alpha")
        mock_db.productstageconfig.find_many.return_value = []  # No existing
        mock_db.productstageconfig.create.return_value = make_obj(
            id="sc-new", productId="prod-1", stage=1, name="Smoke", enabled=True,
            buildScript=None, buildTarget=None, fwRepoUrl=None, fwRepoBranch=None,
            mfgRepoUrl=None, mfgRepoBranch=None, buildVariant=None, configFlags=None,
            buildMatrix=None, testDirectory=None, testMarker=None,
            testTimeout=120, priority=10, blocksMerge=True, requiresFuota=False,
            requiresBench=False, maxDurationSec=300, description=None,
            createdAt="2026-01-01T00:00:00Z", updatedAt="2026-01-01T00:00:00Z",
        )
        resp = authed_client.post("/v2/products/prod-1/stages/initialize")
        assert resp.status_code == 201
        assert mock_db.productstageconfig.create.call_count == 5


class TestDeleteStageConfig:
    def test_deletes_config(self, authed_client, mock_db):
        mock_db.product.find_unique.return_value = make_obj(id="prod-1", name="Alpha")
        mock_db.productstageconfig.find_first.return_value = make_obj(id="sc-1", productId="prod-1", stage=3)
        mock_db.productstageconfig.delete.return_value = make_obj(id="sc-1")
        resp = authed_client.delete("/v2/products/prod-1/stages/3")
        assert resp.status_code == 200

    def test_not_found(self, authed_client, mock_db):
        mock_db.product.find_unique.return_value = make_obj(id="prod-1", name="Alpha")
        mock_db.productstageconfig.find_first.return_value = None
        resp = authed_client.delete("/v2/products/prod-1/stages/3")
        assert resp.status_code == 404
