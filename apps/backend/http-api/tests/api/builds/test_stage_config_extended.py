"""Extended tests for stage_config.py — covering uncovered branches."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from tests.conftest import make_obj


def _stage_obj(**overrides):
    defaults = dict(
        id="sc-1", productId="prod-1", type="VALIDATION", stage=1, name="Smoke",
        enabled=False, boardRevisionId="rev-1", boardRevision=None,
        watchBranch=None, triggerTypes="manual", signingKeyId=None,
        signingKey=None, assetSources=["BUILD_SERVICE"],
        buildMatrixEntries=[], requiresBench=False,
        createdAt="2026-01-01T00:00:00Z", updatedAt="2026-01-01T00:00:00Z",
    )
    defaults.update(overrides)
    return make_obj(**defaults)


def _rev_obj(**overrides):
    defaults = dict(
        id="rev-1", version="1.0", ckBoardsName="alpha_b0", status="ACTIVE",
        board=make_obj(id="board-1", productId="prod-1"),
    )
    defaults.update(overrides)
    return make_obj(**defaults)


class TestGetStageConfig:
    """Tests for GET /v2/products/<id>/stages/<stage>."""

    def test_get_stage_config_success(self, authed_client, mock_db):
        """GET returns the stage config when product and stage exist."""
        mock_db.product.find_unique.return_value = make_obj(id="prod-1", name="Alpha", status="ACTIVE")
        mock_db.productstageconfig.find_first.return_value = _stage_obj(stage=3, name="Integration")

        resp = authed_client.get("/v2/products/prod-1/stages/3")

        assert resp.status_code == 200
        body = json.loads(resp.data)
        assert body["data"]["stage"] == 3

    def test_get_stage_config_product_not_found(self, authed_client, mock_db):
        """GET returns 404 when product does not exist."""
        mock_db.product.find_unique.return_value = None

        resp = authed_client.get("/v2/products/bad/stages/1")

        assert resp.status_code == 404

    def test_get_stage_config_not_found(self, authed_client, mock_db):
        """GET returns 404 when stage config does not exist."""
        mock_db.product.find_unique.return_value = make_obj(id="prod-1", name="Alpha", status="ACTIVE")
        mock_db.productstageconfig.find_first.return_value = None

        resp = authed_client.get("/v2/products/prod-1/stages/99")

        assert resp.status_code == 404

    def test_get_stage_config_non_numeric_stage_returns_400(self, authed_client, mock_db):
        """GET with non-numeric stage returns 400."""
        mock_db.product.find_unique.return_value = make_obj(id="prod-1", name="Alpha", status="ACTIVE")

        resp = authed_client.get("/v2/products/prod-1/stages/abc")

        assert resp.status_code == 400


class TestDeleteStageConfig:
    """Tests for DELETE /v2/products/<id>/stages/<stage>."""

    def test_delete_stage_config_success(self, authed_client, mock_db):
        """DELETE removes the stage config and returns deleted=true."""
        mock_db.product.find_unique.return_value = make_obj(id="prod-1", name="Alpha", status="ACTIVE")
        mock_db.productstageconfig.find_first.return_value = _stage_obj()

        with patch("api.v2.builds.stage_config.log_audit"):
            resp = authed_client.delete("/v2/products/prod-1/stages/1")

        assert resp.status_code == 200
        body = json.loads(resp.data)
        assert body["data"]["deleted"] is True

    def test_delete_stage_config_not_found(self, authed_client, mock_db):
        """DELETE returns 404 when stage config does not exist."""
        mock_db.product.find_unique.return_value = make_obj(id="prod-1", name="Alpha", status="ACTIVE")
        mock_db.productstageconfig.find_first.return_value = None

        resp = authed_client.delete("/v2/products/prod-1/stages/5")

        assert resp.status_code == 404

    def test_delete_stage_config_product_not_found(self, authed_client, mock_db):
        """DELETE returns 404 when product does not exist."""
        mock_db.product.find_unique.return_value = None

        resp = authed_client.delete("/v2/products/bad/stages/1")

        assert resp.status_code == 404

    def test_delete_stage_config_invalid_stage(self, authed_client, mock_db):
        """DELETE with non-numeric stage returns 400."""
        mock_db.product.find_unique.return_value = make_obj(id="prod-1", name="Alpha", status="ACTIVE")

        resp = authed_client.delete("/v2/products/prod-1/stages/xyz")

        assert resp.status_code == 400


class TestCreateStageConfigGuards:
    """Tests for deprecation guard in create_stage_config."""

    def test_create_stage_for_deprecated_revision_returns_400(self, authed_client, mock_db):
        """Cannot create enabled stage config for a DEPRECATED revision."""
        mock_db.product.find_unique.return_value = make_obj(id="prod-1", name="Alpha", status="ACTIVE")
        mock_db.productstageconfig.find_first.return_value = None
        mock_db.boardrevision.find_unique.return_value = _rev_obj(status="DEPRECATED", version="1.0")

        resp = authed_client.post(
            "/v2/products/prod-1/stages",
            data=json.dumps({
                "stage": 2,
                "name": "Driver",
                "enabled": True,
                "boardRevisionId": "rev-1",
            }),
            content_type="application/json",
        )

        assert resp.status_code == 400
        body = json.loads(resp.data)
        assert "DEPRECATED" in body["errors"][0]["message"]

    def test_create_stage_for_eol_revision_returns_400(self, authed_client, mock_db):
        """Cannot create enabled stage config for an EOL revision."""
        mock_db.product.find_unique.return_value = make_obj(id="prod-1", name="Alpha", status="ACTIVE")
        mock_db.productstageconfig.find_first.return_value = None
        mock_db.boardrevision.find_unique.return_value = _rev_obj(status="EOL", version="0.9")

        resp = authed_client.post(
            "/v2/products/prod-1/stages",
            data=json.dumps({
                "stage": 1,
                "name": "Smoke",
                "enabled": True,
                "boardRevisionId": "rev-1",
            }),
            content_type="application/json",
        )

        assert resp.status_code == 400

    def test_create_disabled_stage_for_deprecated_revision_succeeds(self, authed_client, mock_db):
        """Creating a disabled stage config for a deprecated revision is allowed."""
        created = _stage_obj(stage=3, enabled=False)
        mock_db.product.find_unique.return_value = make_obj(id="prod-1", name="Alpha", status="ACTIVE")
        mock_db.boardrevision.find_unique.return_value = _rev_obj(status="DEPRECATED", version="1.0")
        mock_db.productstageconfig.find_first.return_value = None
        mock_db.productstageconfig.create.return_value = created
        mock_db.productstageconfig.find_unique.return_value = created
        mock_db.producttarget.find_many.return_value = []

        resp = authed_client.post(
            "/v2/products/prod-1/stages",
            data=json.dumps({
                "stage": 3,
                "name": "Integration",
                "enabled": False,
                "boardRevisionId": "rev-1",
            }),
            content_type="application/json",
        )

        # enabled=False bypasses the deprecated guard
        assert resp.status_code == 201

    def test_create_stage_conflict_returns_409(self, authed_client, mock_db):
        """Creating duplicate stage for same product and revision returns 409."""
        mock_db.product.find_unique.return_value = make_obj(id="prod-1", name="Alpha", status="ACTIVE")
        mock_db.boardrevision.find_unique.return_value = _rev_obj()
        mock_db.productstageconfig.find_first.return_value = _stage_obj()

        resp = authed_client.post(
            "/v2/products/prod-1/stages",
            data=json.dumps({"stage": 1, "name": "Smoke", "boardRevisionId": "rev-1"}),
            content_type="application/json",
        )

        assert resp.status_code == 409


class TestUpdateStageConfigGuards:
    """Tests for deprecation guard in update_stage_config."""

    def test_update_enabling_for_deprecated_revision_returns_400(self, authed_client, mock_db):
        """Cannot enable a stage config when the linked revision is DEPRECATED."""
        mock_db.product.find_unique.return_value = make_obj(id="prod-1", name="Alpha", status="ACTIVE")
        mock_db.productstageconfig.find_first.return_value = _stage_obj(boardRevisionId="rev-dep")
        mock_db.boardrevision.find_unique.return_value = _rev_obj(status="DEPRECATED", version="0.8")

        resp = authed_client.put(
            "/v2/products/prod-1/stages/1",
            data=json.dumps({"enabled": True}),
            content_type="application/json",
        )

        assert resp.status_code == 400
        body = json.loads(resp.data)
        assert "DEPRECATED" in body["errors"][0]["message"]

    def test_update_no_fields_returns_400(self, authed_client, mock_db):
        """PUT with empty update dict returns 400."""
        mock_db.product.find_unique.return_value = make_obj(id="prod-1", name="Alpha", status="ACTIVE")
        mock_db.productstageconfig.find_first.return_value = _stage_obj()

        resp = authed_client.put(
            "/v2/products/prod-1/stages/1",
            data=json.dumps({}),
            content_type="application/json",
        )

        assert resp.status_code == 400


class TestBuildMatrix:
    """Tests for build matrix sub-resource."""

    def test_get_stage_build_matrix_success(self, authed_client, mock_db):
        """GET /v2/products/<id>/stages/<stage>/build-matrix returns entries."""
        mock_db.product.find_unique.return_value = make_obj(id="prod-1", name="Alpha", status="ACTIVE")
        mock_db.productstageconfig.find_first.return_value = _stage_obj()
        entry = make_obj(
            id="e1", stageConfigId="sc-1", sortOrder=0,
            label="MFG_APP_DEBUG", fwType="alpha_mfg_fw", variant="release",
            configLog=True, producesHex=True, producesCfw=False,
            gitRef="pr", isVersionBump=False, baseLabel=None, description=None,
            processor="nrf52840", filenamePattern=None,
        )
        mock_db.stagebuildmatrix.find_many.return_value = [entry]

        resp = authed_client.get("/v2/products/prod-1/stages/1/build-matrix")

        assert resp.status_code == 200
        body = json.loads(resp.data)
        assert len(body["data"]) == 1
        assert body["data"][0]["label"] == "MFG_APP_DEBUG"

    def test_update_stage_build_matrix_success(self, authed_client, mock_db):
        """PUT /v2/products/<id>/stages/<stage>/build-matrix replaces entries."""
        mock_db.product.find_unique.return_value = make_obj(id="prod-1", name="Alpha", status="ACTIVE")
        mock_db.productstageconfig.find_first.return_value = _stage_obj()
        new_entry = make_obj(
            id="e-new", stageConfigId="sc-1", sortOrder=0,
            label="SMOKE_APP_DEBUG", fwType="alpha_fw", variant="debug",
            configLog=True, producesHex=True, producesCfw=False,
            gitRef="pr", isVersionBump=False, baseLabel=None, description=None,
            processor=None, filenamePattern=None,
        )
        mock_db.stagebuildmatrix.create.return_value = new_entry

        with patch("api.v2.builds.stage_config.log_audit"):
            resp = authed_client.put(
                "/v2/products/prod-1/stages/1/build-matrix",
                data=json.dumps({"entries": [
                    {"label": "SMOKE_APP_DEBUG", "fwType": "alpha_fw", "variant": "debug"}
                ]}),
                content_type="application/json",
            )

        assert resp.status_code == 200
        body = json.loads(resp.data)
        assert body["data"][0]["label"] == "SMOKE_APP_DEBUG"
        mock_db.stagebuildmatrix.delete_many.assert_called_once()

    def test_update_stage_build_matrix_duplicate_label_returns_400(self, authed_client, mock_db):
        """PUT with duplicate labels in entries returns 400."""
        mock_db.product.find_unique.return_value = make_obj(id="prod-1", name="Alpha", status="ACTIVE")
        mock_db.productstageconfig.find_first.return_value = _stage_obj()

        resp = authed_client.put(
            "/v2/products/prod-1/stages/1/build-matrix",
            data=json.dumps({"entries": [
                {"label": "SAME", "fwType": "alpha_fw", "variant": "debug"},
                {"label": "SAME", "fwType": "alpha_mfg_fw", "variant": "release"},
            ]}),
            content_type="application/json",
        )

        assert resp.status_code == 400
        body = json.loads(resp.data)
        assert "duplicate" in body["errors"][0]["message"].lower()

    def test_update_stage_build_matrix_missing_entries_returns_400(self, authed_client, mock_db):
        """PUT without entries array returns 400."""
        mock_db.product.find_unique.return_value = make_obj(id="prod-1", name="Alpha", status="ACTIVE")
        mock_db.productstageconfig.find_first.return_value = _stage_obj()

        resp = authed_client.put(
            "/v2/products/prod-1/stages/1/build-matrix",
            data=json.dumps({}),
            content_type="application/json",
        )

        assert resp.status_code == 400

    # TODO: test_reset_stage_build_matrix_success
    # TODO: test_reset_stage_build_matrix_invalid_stage_num
