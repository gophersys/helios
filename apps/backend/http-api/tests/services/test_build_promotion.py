"""Unit tests for build_promotion service.

Tests promote_build_run_to_firmware and create_asset_set_from_build_run
using a mocked Prisma DB client.
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from tests.conftest import make_obj, MockPrismaClient


@pytest.fixture
def mock_db():
    """Fresh MockPrismaClient for direct service tests."""
    import src.services.database.prisma as prisma_module
    client = MockPrismaClient()
    original = prisma_module.appPostgresClient
    prisma_module.appPostgresClient = client
    yield client
    prisma_module.appPostgresClient = original


def _make_artifact(**overrides):
    defaults = dict(
        id="art-1",
        name="109.0.5.2-BM.hex",
        storageKey="firmware/builds/prod-1/run-1/109.0.5.2-BM.hex",
        sizeBytes=128000,
        checksum="abc123",
        artifactType="plaintextHex",
        role="app",
        processor="nrf52840",
        contentType="application/octet-stream",
    )
    defaults.update(overrides)
    return make_obj(**defaults)


def _make_build_job(**overrides):
    defaults = dict(
        id="job-1",
        product="alpha",
        board="alpha_b0",
        target="app",
        variant="debug",
        versionString="109.0.5.2-BM",
        status="SUCCESS",
        matrixLabel="smoke_app_debug",
        artifacts=[_make_artifact()],
        startedAt=None,
        finishedAt=None,
    )
    defaults.update(overrides)
    return make_obj(**defaults)


def _make_build_run(**overrides):
    defaults = dict(
        id="run-1",
        productId="prod-1",
        board="alpha_b0",
        branch="main",
        commitSha="abc123",
        status="SUCCESS",
        stageConfigId="stage-1",
        builds=[_make_build_job()],
        product=make_obj(id="prod-1", name="Alpha", slug="alpha"),
    )
    defaults.update(overrides)
    return make_obj(**defaults)


class TestPromoteBuildRunToFirmware:
    """Tests for promote_build_run_to_firmware()."""

    def test_returns_none_when_build_run_not_found(self, mock_db):
        """promote_build_run_to_firmware returns None for unknown run ID."""
        mock_db.buildrun.find_unique.return_value = None

        from src.services.build_promotion import promote_build_run_to_firmware
        result = promote_build_run_to_firmware("bad-id")

        assert result is None

    def test_returns_none_when_no_builds(self, mock_db):
        """promote_build_run_to_firmware returns None when run has no builds."""
        run = _make_build_run(builds=[])
        mock_db.buildrun.find_unique.return_value = run

        from src.services.build_promotion import promote_build_run_to_firmware
        result = promote_build_run_to_firmware("run-1")

        assert result is None

    def test_creates_firmware_set_per_variant(self, mock_db):
        """promote_build_run_to_firmware creates one FirmwareSet per variant."""
        debug_job = _make_build_job(id="job-debug", variant="debug")
        mfg_job = _make_build_job(id="job-mfg", variant="mfg")
        run = _make_build_run(builds=[debug_job, mfg_job])
        mock_db.buildrun.find_unique.return_value = run
        mock_db.productstageconfig.find_unique.return_value = None
        mock_db.boardrevision.find_first.return_value = make_obj(id="rev-1")
        fw_set = make_obj(id="fwset-1")
        mock_db.firmwareset.create.return_value = fw_set
        mock_db.firmwarebuild.create.return_value = make_obj(id="fwbuild-1")
        mock_db.producttarget.find_first.return_value = None

        from src.services.build_promotion import promote_build_run_to_firmware
        result = promote_build_run_to_firmware("run-1")

        assert result is not None
        assert len(result) == 2
        variants = {r["variant"] for r in result}
        assert "debug" in variants
        assert "mfg" in variants

    def test_resolves_board_revision_from_stage_config(self, mock_db):
        """promote_build_run_to_firmware uses stage config's boardRevisionId first."""
        run = _make_build_run()
        stage_config = make_obj(id="stage-1", boardRevisionId="rev-from-config")
        mock_db.buildrun.find_unique.return_value = run
        mock_db.productstageconfig.find_unique.return_value = stage_config
        fw_set = make_obj(id="fwset-1")
        mock_db.firmwareset.create.return_value = fw_set
        mock_db.firmwarebuild.create.return_value = make_obj(id="fwbuild-1")
        mock_db.producttarget.find_first.return_value = None

        from src.services.build_promotion import promote_build_run_to_firmware
        promote_build_run_to_firmware("run-1")

        create_call = mock_db.firmwareset.create.call_args[1]["data"]
        assert create_call["boardRevisionId"] == "rev-from-config"

    def test_extracts_version_from_version_string(self, mock_db):
        """promote_build_run_to_firmware parses semver from the versionString field."""
        job = _make_build_job(versionString="109.0.5.2-BM")
        run = _make_build_run(builds=[job])
        mock_db.buildrun.find_unique.return_value = run
        mock_db.productstageconfig.find_unique.return_value = None
        mock_db.boardrevision.find_first.return_value = None
        fw_set = make_obj(id="fwset-1")
        mock_db.firmwareset.create.return_value = fw_set
        mock_db.firmwarebuild.create.return_value = make_obj(id="fwbuild-1")
        mock_db.producttarget.find_first.return_value = None

        from src.services.build_promotion import promote_build_run_to_firmware
        promote_build_run_to_firmware("run-1")

        create_call = mock_db.firmwareset.create.call_args[1]["data"]
        assert create_call["version"] == "0.5.2"


class TestCreateAssetSetFromBuildRun:
    """Tests for create_asset_set_from_build_run()."""

    def test_returns_none_when_build_run_not_found(self, mock_db):
        """create_asset_set_from_build_run returns None for unknown run."""
        mock_db.buildrun.find_unique.return_value = None

        from src.services.build_promotion import create_asset_set_from_build_run
        result = create_asset_set_from_build_run("bad-id")

        assert result is None

    def test_returns_none_when_no_builds(self, mock_db):
        """create_asset_set_from_build_run returns None when run has no builds."""
        run = _make_build_run(builds=[])
        mock_db.buildrun.find_unique.return_value = run

        from src.services.build_promotion import create_asset_set_from_build_run
        result = create_asset_set_from_build_run("run-1")

        assert result is None

    def test_returns_deduplicated_when_asset_set_exists(self, mock_db):
        """create_asset_set_from_build_run returns existing ID when already promoted."""
        run = _make_build_run()
        mock_db.buildrun.find_unique.return_value = run
        existing = make_obj(id="aset-existing")
        mock_db.assetset.find_first.return_value = existing

        from src.services.build_promotion import create_asset_set_from_build_run
        result = create_asset_set_from_build_run("run-1")

        assert result["assetSetId"] == "aset-existing"
        assert result["deduplicated"] is True
        mock_db.assetset.create.assert_not_called()

    def test_creates_asset_set_with_assets(self, mock_db):
        """create_asset_set_from_build_run creates AssetSet and Asset records."""
        run = _make_build_run()
        mock_db.buildrun.find_unique.return_value = run
        mock_db.assetset.find_first.return_value = None
        mock_db.productstageconfig.find_unique.return_value = None
        mock_db.boardrevision.find_first.return_value = None
        asset_set = make_obj(id="aset-1")
        mock_db.assetset.create.return_value = asset_set
        mock_db.boardrevision.find_unique.return_value = None

        from src.services.build_promotion import create_asset_set_from_build_run
        result = create_asset_set_from_build_run("run-1")

        assert result is not None
        assert result["assetSetId"] == "aset-1"
        assert result["assetCount"] == 1
        mock_db.asset.create.assert_called_once()

    def test_parses_app_id_from_numeric_filename_prefix(self, mock_db):
        """create_asset_set_from_build_run extracts appId from filenames like '109.0.5.2-BM.hex'."""
        artifact = _make_artifact(name="109.0.5.2-BM.hex")
        job = _make_build_job(artifacts=[artifact])
        run = _make_build_run(builds=[job])
        mock_db.buildrun.find_unique.return_value = run
        mock_db.assetset.find_first.return_value = None
        mock_db.productstageconfig.find_unique.return_value = None
        mock_db.boardrevision.find_first.return_value = None
        mock_db.assetset.create.return_value = make_obj(id="aset-1")
        mock_db.boardrevision.find_unique.return_value = None

        from src.services.build_promotion import create_asset_set_from_build_run
        create_asset_set_from_build_run("run-1")

        asset_create_call = mock_db.asset.create.call_args[1]["data"]
        assert asset_create_call["appId"] == 109

    def test_prefers_debug_variant_as_primary(self, mock_db):
        """create_asset_set_from_build_run uses 'debug' as primary variant when available."""
        debug_job = _make_build_job(id="j-debug", variant="debug")
        mfg_job = _make_build_job(id="j-mfg", variant="mfg")
        run = _make_build_run(builds=[debug_job, mfg_job])
        mock_db.buildrun.find_unique.return_value = run
        mock_db.assetset.find_first.return_value = None
        mock_db.productstageconfig.find_unique.return_value = None
        mock_db.boardrevision.find_first.return_value = None
        mock_db.assetset.create.return_value = make_obj(id="aset-1")
        mock_db.boardrevision.find_unique.return_value = None

        from src.services.build_promotion import create_asset_set_from_build_run
        create_asset_set_from_build_run("run-1")

        asset_set_data = mock_db.assetset.create.call_args[1]["data"]
        assert asset_set_data["variant"] == "debug"
