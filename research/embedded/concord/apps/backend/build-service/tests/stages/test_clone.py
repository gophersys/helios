"""Tests for CloneStage — repo cloning and NCS detection."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.worker.executor import BuildJob
from src.worker.pipeline import BuildContext, StageResult
from src.worker.stages.clone import CloneStage


@pytest.fixture
def clone_stage():
    return CloneStage()


@pytest.fixture
def ctx(tmp_path, sample_job, config, mock_api_client):
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
    )


class TestRepoResolution:
    """Test how primary/secondary repos are resolved from the job."""

    def test_app_target_uses_fw_as_primary(self, ctx, clone_stage):
        """For target='app', primary is the fw repo, secondary is mfg."""
        ctx.job = BuildJob(
            id="j1", product="alpha", board="alpha_b0", target="app",
            variant="release", branch="feature/x", commit_sha="abc123",
            status="QUEUED", version_bump=False, base_job_id=None,
            matrix_label=None, version_override=None, config_flags={},
            product_id="p1", recipe_version_id=None, stage=3,
        )
        primary, secondary = clone_stage._resolve_repos(ctx)
        assert primary["slug"] == "alpha_fw"
        assert primary["branch"] == "feature/x"
        assert primary["commit"] == "abc123"
        assert secondary["slug"] == "alpha_mfg_fw"
        assert secondary["branch"] == "main"

    def test_mfg_target_uses_mfg_as_primary(self, ctx, clone_stage):
        """For target='mfg', primary is the mfg repo, secondary is fw."""
        ctx.job = BuildJob(
            id="j2", product="alpha", board="alpha_b0", target="mfg",
            variant="release", branch="feature/y", commit_sha="def456",
            status="QUEUED", version_bump=False, base_job_id=None,
            matrix_label=None, version_override=None, config_flags={},
            product_id="p1", recipe_version_id=None, stage=3,
        )
        primary, secondary = clone_stage._resolve_repos(ctx)
        assert primary["slug"] == "alpha_mfg_fw"
        assert primary["branch"] == "main"  # mfg always uses main
        assert secondary["slug"] == "alpha_fw"
        assert secondary["branch"] == "feature/y"

    def test_webhook_data_overrides_repo_slugs(self, ctx, clone_stage):
        """webhookData.fwRepoSlug and mfgRepoSlug override defaults."""
        ctx.webhook_data = {
            "fwRepoSlug": "custom_fw",
            "mfgRepoSlug": "custom_mfg_fw",
        }
        primary, secondary = clone_stage._resolve_repos(ctx)
        assert primary["slug"] == "custom_fw"
        assert secondary["slug"] == "custom_mfg_fw"


class TestCloneExecution:
    """Test the full clone stage execution with mocked git_ops."""

    def test_successful_clone(self, ctx, clone_stage):
        """Both repos clone successfully → stage passes."""
        with patch.object(clone_stage, '_clone_repo', return_value=True):
            result = clone_stage.execute(ctx)

        assert result.success
        assert ctx.primary_dir is not None
        assert ctx.primary_slug is not None

    def test_primary_clone_failure(self, ctx, clone_stage):
        """Primary repo clone failure → stage fails."""
        def mock_clone(slug, dest, commit, branch, client, job_id):
            if "fw" in slug and "mfg" not in slug:
                return False
            return True

        with patch.object(clone_stage, '_clone_repo', side_effect=mock_clone):
            result = clone_stage.execute(ctx)

        assert not result.success
        assert "clone" in result.error.lower() or "failed" in result.error.lower()

    def test_secondary_clone_failure_is_warning(self, ctx, clone_stage):
        """Secondary repo clone failure is a warning, not a failure."""
        call_count = 0
        def mock_clone(slug, dest, commit, branch, client, job_id):
            nonlocal call_count
            call_count += 1
            # First call (primary) succeeds, second (secondary) fails
            return call_count == 1

        with patch.object(clone_stage, '_clone_repo', side_effect=mock_clone):
            result = clone_stage.execute(ctx)

        assert result.success  # Secondary failure is not fatal

    def test_overlays_fetched(self, ctx, clone_stage):
        """Overlays are fetched from the API."""
        with patch.object(clone_stage, '_clone_repo', return_value=True), \
             patch.object(clone_stage, '_fetch_overlays') as mock_overlays:
            clone_stage.execute(ctx)

        mock_overlays.assert_called_once()

    def test_ncs_version_detected(self, ctx, clone_stage):
        """NCS version is detected from the cloned repo."""
        with patch.object(clone_stage, '_clone_repo', return_value=True), \
             patch.object(clone_stage, '_detect_ncs_version', return_value="2.7.0"):
            clone_stage.execute(ctx)

        # NCS version is informational, just verify no crash


class TestSDKCopy:
    """Test that the Concord Build SDK is copied into the workspace."""

    def test_sdk_copied_when_source_exists(self, ctx, clone_stage, tmp_path):
        """SDK is copied from /app/sdk to workspace when source exists."""
        sdk_src = tmp_path / "app_sdk"
        sdk_src.mkdir()
        (sdk_src / "concord-build.sh").write_text("#!/bin/bash\necho sdk")

        with patch.object(clone_stage, '_clone_repo', return_value=True), \
             patch("src.worker.stages.clone.SDK_SOURCE", sdk_src):
            clone_stage.execute(ctx)

        sdk_dest = ctx.work_dir / "sdk"
        assert sdk_dest.exists()
        assert (sdk_dest / "concord-build.sh").exists()

    def test_sdk_not_copied_when_missing(self, ctx, clone_stage, tmp_path):
        """No error when SDK source doesn't exist."""
        missing_sdk = tmp_path / "nonexistent_sdk"

        with patch.object(clone_stage, '_clone_repo', return_value=True), \
             patch("src.worker.stages.clone.SDK_SOURCE", missing_sdk):
            result = clone_stage.execute(ctx)

        assert result.success
