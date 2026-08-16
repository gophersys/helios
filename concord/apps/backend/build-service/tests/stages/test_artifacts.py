"""Tests for ArtifactStage — artifact collection, verification, upload."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.worker.pipeline import BuildContext
from src.worker.stages.artifacts import ArtifactStage


@pytest.fixture
def artifact_stage():
    return ArtifactStage()


@pytest.fixture
def ctx(tmp_path, sample_job, config, mock_api_client, sample_build_config):
    work_dir = tmp_path / "work"
    work_dir.mkdir()
    output_dir = work_dir / "artifacts"
    output_dir.mkdir()
    return BuildContext(
        job=sample_job,
        config=config,
        client=mock_api_client,
        work_dir=work_dir,
        output_dir=output_dir,
        build_config=sample_build_config,
        version_string="0.8.3",
    )


class TestArtifactCollection:
    """Test artifact collection and upload."""

    @patch("src.worker.stages.artifacts.BuildExecutor")
    def test_successful_upload(self, MockExecutor, ctx, artifact_stage):
        """Artifacts are collected and uploaded."""
        mock_exec = MockExecutor.return_value
        mock_exec.collect_artifacts.return_value = [ctx.output_dir / "109.0.8.3.hex"]
        mock_exec.verify_artifacts.return_value = (True, "ok")
        mock_exec.upload_artifacts.return_value = 2
        mock_exec.write_manifest.return_value = ctx.output_dir / "build.json"

        (ctx.output_dir / "109.0.8.3.hex").write_text("fake hex")
        (ctx.output_dir / "build.json").write_text("{}")

        result = artifact_stage.execute(ctx)

        assert result.success
        mock_exec.upload_artifacts.assert_called_once()

    @patch("src.worker.stages.artifacts.BuildExecutor")
    def test_verification_failure(self, MockExecutor, ctx, artifact_stage):
        """Verification failure returns error and uploads log."""
        mock_exec = MockExecutor.return_value
        mock_exec.collect_artifacts.return_value = []
        mock_exec.verify_artifacts.return_value = (False, "version mismatch")
        mock_exec.write_manifest.return_value = None

        result = artifact_stage.execute(ctx)

        assert not result.success
        assert "version mismatch" in result.error

    @patch("src.worker.stages.artifacts.BuildExecutor")
    def test_no_build_config_skips_manifest(self, MockExecutor, ctx, artifact_stage, mock_api_client):
        """No buildConfig → manifest generation is skipped."""
        ctx.build_config = None
        # Also ensure API doesn't return a buildConfig
        mock_api_client.get_product.return_value = None
        mock_exec = MockExecutor.return_value
        mock_exec.collect_artifacts.return_value = []
        mock_exec.verify_artifacts.return_value = (True, "ok")
        mock_exec.upload_artifacts.return_value = 0

        result = artifact_stage.execute(ctx)

        assert result.success
        mock_exec.write_manifest.assert_not_called()

    @patch("src.worker.stages.artifacts.BuildExecutor")
    def test_build_log_included(self, MockExecutor, ctx, artifact_stage):
        """Build log is included in uploaded artifacts."""
        log_file = ctx.output_dir / "build.log"
        log_file.write_text("build output here")

        mock_exec = MockExecutor.return_value
        mock_exec.collect_artifacts.return_value = []
        mock_exec.verify_artifacts.return_value = (True, "ok")
        mock_exec.upload_artifacts.return_value = 1
        mock_exec.write_manifest.return_value = None
        ctx.build_config = None

        artifact_stage.execute(ctx)

        upload_call = mock_exec.upload_artifacts.call_args
        artifact_list = upload_call[0][1]
        assert any("build.log" in str(a) for a in artifact_list)
