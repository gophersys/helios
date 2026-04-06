"""Tests for stage config endpoints."""
import json
from tests.conftest import make_obj


def _stage_obj(**overrides):
    defaults = dict(
        id="sc-1", productId="prod-1", stage=1, name="Smoke",
        enabled=False, boardRevisionId=None, boardRevision=None,
        watchBranch=None, signingKeyId=None, signingKey=None,
        createdAt="2026-01-01T00:00:00Z", updatedAt="2026-01-01T00:00:00Z",
    )
    defaults.update(overrides)
    return make_obj(**defaults)


class TestListStageConfigs:
    def test_success(self, authed_client, mock_db):
        mock_db.product.find_unique.return_value = make_obj(id="prod-1", name="Alpha")
        mock_db.productstageconfig.find_many.return_value = [_stage_obj()]
        resp = authed_client.get("/v2/products/prod-1/stages")
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert len(data["data"]) == 1

    def test_product_not_found(self, authed_client, mock_db):
        mock_db.product.find_unique.return_value = None
        resp = authed_client.get("/v2/products/nope/stages")
        assert resp.status_code == 404


class TestCreateStageConfig:
    def test_success(self, authed_client, mock_db):
        mock_db.product.find_unique.return_value = make_obj(id="prod-1", name="Alpha")
        mock_db.productstageconfig.find_first.return_value = None
        mock_db.productstageconfig.create.return_value = _stage_obj(stage=5, name="FUOTA")
        resp = authed_client.post("/v2/products/prod-1/stages",
            data=json.dumps({"stage": 5, "name": "FUOTA"}), content_type="application/json")
        assert resp.status_code == 201


class TestUpdateStageConfig:
    def test_success(self, authed_client, mock_db):
        mock_db.product.find_unique.return_value = make_obj(id="prod-1", name="Alpha")
        mock_db.productstageconfig.find_first.return_value = _stage_obj()
        mock_db.productstageconfig.update.return_value = _stage_obj(enabled=True)
        resp = authed_client.put("/v2/products/prod-1/stages/1",
            data=json.dumps({"enabled": True}), content_type="application/json")
        assert resp.status_code == 200


class TestInitializeStages:
    def test_success(self, authed_client, mock_db):
        mock_db.product.find_unique.return_value = make_obj(id="prod-1", name="Alpha")
        mock_db.productstageconfig.find_many.return_value = []
        mock_db.productstageconfig.create.return_value = _stage_obj()
        resp = authed_client.post("/v2/products/prod-1/stages/initialize")
        assert resp.status_code == 201
        data = json.loads(resp.data)
        assert len(data["data"]) == 5

    def test_already_initialized(self, authed_client, mock_db):
        mock_db.product.find_unique.return_value = make_obj(id="prod-1", name="Alpha")
        mock_db.productstageconfig.find_many.return_value = [_stage_obj()]
        resp = authed_client.post("/v2/products/prod-1/stages/initialize")
        assert resp.status_code == 409
