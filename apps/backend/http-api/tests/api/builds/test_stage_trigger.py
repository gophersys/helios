"""Tests for stage trigger endpoint."""
import json
from tests.conftest import make_obj


def _product(**overrides):
    defaults = dict(id="prod-1", name="Alpha", slug="alpha")
    defaults.update(overrides)
    return make_obj(**defaults)


def _stage_config(**overrides):
    defaults = dict(
        id="sc-1", productId="prod-1", stage=1, type="VALIDATION", enabled=True,
        boardRevisionId="rev-1", assetSources=["BUILD_SERVICE"],
    )
    defaults.update(overrides)
    return make_obj(**defaults)


def _asset_set(**overrides):
    defaults = dict(
        id="as-1", productId="prod-1", status="COMPLETE", version="1.0.0",
        variant="debug",
    )
    defaults.update(overrides)
    return make_obj(**defaults)


class TestTriggerStageRun:
    def test_trigger_valid_asset_set(self, authed_client, mock_db):
        """Happy path: valid product, enabled stage, complete asset set."""
        mock_db.product.find_unique.return_value = _product()
        mock_db.productstageconfig.find_first.return_value = _stage_config()
        mock_db.assetset.find_unique.return_value = _asset_set()
        mock_db.validationqueueentry.create.return_value = make_obj(
            id="qe-1", assetSetId="as-1", stageConfigId="sc-1", stage=1, status="QUEUED",
        )

        resp = authed_client.post(
            "/v2/products/prod-1/stages/1/trigger-run",
            data=json.dumps({"assetSetId": "as-1"}),
            content_type="application/json",
        )
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data["data"]["queued"] is True
        assert data["data"]["queueEntryId"] == "qe-1"
        assert data["data"]["stageConfigId"] == "sc-1"
        assert data["data"]["assetSetId"] == "as-1"

    def test_trigger_missing_asset_set_id(self, authed_client, mock_db):
        """Returns 400 when assetSetId is missing from request body."""
        resp = authed_client.post(
            "/v2/products/prod-1/stages/1/trigger-run",
            data=json.dumps({}),
            content_type="application/json",
        )
        assert resp.status_code == 400
        data = json.loads(resp.data)
        assert "assetsetid" in data["errors"][0]["message"].lower()

    def test_trigger_invalid_product(self, authed_client, mock_db):
        """Returns 404 when product does not exist."""
        mock_db.product.find_unique.return_value = None

        resp = authed_client.post(
            "/v2/products/nope/stages/1/trigger-run",
            data=json.dumps({"assetSetId": "as-1"}),
            content_type="application/json",
        )
        assert resp.status_code == 404

    def test_trigger_manufacturing_stage(self, authed_client, mock_db):
        """Returns 400 when the stage is manufacturing, not validation."""
        mock_db.product.find_unique.return_value = _product()
        # No enabled VALIDATION config found
        mock_db.productstageconfig.find_first.side_effect = [
            None,  # First call: VALIDATION + enabled
            None,  # Second call: disabled VALIDATION
            _stage_config(type="MANUFACTURING"),  # Third call: MANUFACTURING
        ]

        resp = authed_client.post(
            "/v2/products/prod-1/stages/1/trigger-run",
            data=json.dumps({"assetSetId": "as-1"}),
            content_type="application/json",
        )
        assert resp.status_code == 400
        data = json.loads(resp.data)
        assert "manufacturing" in data["errors"][0]["message"].lower()

    def test_trigger_disabled_stage(self, authed_client, mock_db):
        """Returns 400 when the validation stage exists but is disabled."""
        mock_db.product.find_unique.return_value = _product()
        # First call: no enabled VALIDATION config; second call: disabled exists
        mock_db.productstageconfig.find_first.side_effect = [
            None,
            _stage_config(enabled=False),
        ]

        resp = authed_client.post(
            "/v2/products/prod-1/stages/1/trigger-run",
            data=json.dumps({"assetSetId": "as-1"}),
            content_type="application/json",
        )
        assert resp.status_code == 400
        data = json.loads(resp.data)
        assert "not enabled" in data["errors"][0]["message"].lower()

    def test_trigger_asset_set_not_found(self, authed_client, mock_db):
        """Returns 404 when the asset set does not exist."""
        mock_db.product.find_unique.return_value = _product()
        mock_db.productstageconfig.find_first.return_value = _stage_config()
        mock_db.assetset.find_unique.return_value = None

        resp = authed_client.post(
            "/v2/products/prod-1/stages/1/trigger-run",
            data=json.dumps({"assetSetId": "as-missing"}),
            content_type="application/json",
        )
        assert resp.status_code == 404
        data = json.loads(resp.data)
        assert "asset set" in data["errors"][0]["message"].lower()

    def test_trigger_asset_set_wrong_product(self, authed_client, mock_db):
        """Returns 400 when the asset set belongs to a different product."""
        mock_db.product.find_unique.return_value = _product()
        mock_db.productstageconfig.find_first.return_value = _stage_config()
        mock_db.assetset.find_unique.return_value = _asset_set(productId="prod-other")

        resp = authed_client.post(
            "/v2/products/prod-1/stages/1/trigger-run",
            data=json.dumps({"assetSetId": "as-1"}),
            content_type="application/json",
        )
        assert resp.status_code == 400
        data = json.loads(resp.data)
        assert "does not belong" in data["errors"][0]["message"].lower()

    def test_trigger_asset_set_pending(self, authed_client, mock_db):
        """Returns 400 when the asset set is still pending."""
        mock_db.product.find_unique.return_value = _product()
        mock_db.productstageconfig.find_first.return_value = _stage_config()
        mock_db.assetset.find_unique.return_value = _asset_set(status="PENDING")

        resp = authed_client.post(
            "/v2/products/prod-1/stages/1/trigger-run",
            data=json.dumps({"assetSetId": "as-1"}),
            content_type="application/json",
        )
        assert resp.status_code == 400
        data = json.loads(resp.data)
        assert "pending" in data["errors"][0]["message"].lower()

    def test_trigger_no_stage_config(self, authed_client, mock_db):
        """Returns 404 when no stage config exists at all for the given stage."""
        mock_db.product.find_unique.return_value = _product()
        # All find_first calls return None (no config of any type)
        mock_db.productstageconfig.find_first.return_value = None

        resp = authed_client.post(
            "/v2/products/prod-1/stages/1/trigger-run",
            data=json.dumps({"assetSetId": "as-1"}),
            content_type="application/json",
        )
        assert resp.status_code == 404
        data = json.loads(resp.data)
        assert "not found" in data["errors"][0]["message"].lower()

    def test_trigger_invalid_stage_number(self, authed_client, mock_db):
        """Returns 400 when stage is not a valid number."""
        mock_db.product.find_unique.return_value = _product()

        resp = authed_client.post(
            "/v2/products/prod-1/stages/abc/trigger-run",
            data=json.dumps({"assetSetId": "as-1"}),
            content_type="application/json",
        )
        assert resp.status_code == 400

    def test_trigger_stage_out_of_range(self, authed_client, mock_db):
        """Returns 400 when stage number is outside 1-5 range."""
        mock_db.product.find_unique.return_value = _product()

        resp = authed_client.post(
            "/v2/products/prod-1/stages/9/trigger-run",
            data=json.dumps({"assetSetId": "as-1"}),
            content_type="application/json",
        )
        assert resp.status_code == 400
        data = json.loads(resp.data)
        assert "between 1 and 5" in data["errors"][0]["message"].lower()
