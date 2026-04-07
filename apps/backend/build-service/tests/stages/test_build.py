"""Tests for BuildStage — build execution and version extraction."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.worker.pipeline import BuildContext
from src.worker.stages.build import BuildStage


@pytest.fixture
def build_stage():
    return BuildStage()


@pytest.fixture
def ctx(tmp_path, sample_job, config, mock_api_client):
    work_dir = tmp_path / "work"
    work_dir.mkdir()
    output_dir = work_dir / "artifacts"
    output_dir.mkdir()
    primary_dir = work_dir / "alpha_fw"
    primary_dir.mkdir()
    return BuildContext(
        job=sample_job,
        config=config,
        client=mock_api_client,
        work_dir=work_dir,
        output_dir=output_dir,
        primary_dir=primary_dir,
        primary_slug="alpha_fw",
    )


class TestVersionExtraction:
    """Test firmware version extraction from build output."""

    def test_explicit_resolved_version(self, build_stage):
        """Extracts version from 'Resolved version: X.Y.Z' marker."""
        log_output = "Building...\nResolved version: 0.8.3\nDone."
        version = build_stage._extract_version(log_output)
        assert version == "0.8.3"

    def test_fallback_to_last_semver(self, build_stage):
        """Falls back to last X.Y.Z pattern when no explicit marker."""
        log_output = "NCS 2.7.0\nBuilding fw 0.5.2\nComplete."
        version = build_stage._extract_version(log_output)
        assert version == "0.5.2"

    def test_prefers_explicit_over_fallback(self, build_stage):
        """Explicit marker takes precedence over other versions in output."""
        log_output = "NCS 2.7.0\nResolved version: 1.0.0\nSome other 3.2.1"
        version = build_stage._extract_version(log_output)
        assert version == "1.0.0"

    def test_empty_output_returns_none(self, build_stage):
        """Empty output returns None."""
        assert build_stage._extract_version("") is None
        assert build_stage._extract_version(None) is None

    def test_no_version_in_output(self, build_stage):
        """No version pattern returns None."""
        assert build_stage._extract_version("no version here") is None


class TestBuildExecution:
    """Test build execution with mocked executor."""

    @patch("src.worker.stages.build.BuildExecutor")
    def test_successful_build(self, MockExecutor, ctx, build_stage, mock_api_client):
        """Successful build sets version_string and returns ok."""
        mock_exec = MockExecutor.return_value
        mock_exec.run_build.return_value = (True, "Resolved version: 0.8.3\nBuild complete")

        result = build_stage.execute(ctx)

        assert result.success
        assert ctx.version_string == "0.8.3"
        assert "Build complete" in ctx.log_output

    @patch("src.worker.stages.build.BuildExecutor")
    def test_failed_build(self, MockExecutor, ctx, build_stage, mock_api_client):
        """Failed build returns error with log tail."""
        mock_exec = MockExecutor.return_value
        mock_exec.run_build.return_value = (False, "error: undefined reference to 'main'")

        result = build_stage.execute(ctx)

        assert not result.success
        assert "undefined reference" in result.error

    @patch("src.worker.stages.build.BuildExecutor")
    def test_updates_status_to_building(self, MockExecutor, ctx, build_stage, mock_api_client):
        """Status is set to BUILDING before execution."""
        mock_exec = MockExecutor.return_value
        mock_exec.run_build.return_value = (True, "ok")

        build_stage.execute(ctx)

        # Check that BUILDING status was sent
        calls = mock_api_client.api_patch.call_args_list
        building_calls = [c for c in calls if c[0][1].get("status") == "BUILDING"]
        assert len(building_calls) >= 1


class TestDockerImageResolution:
    """Test Docker builder image resolution."""

    @patch("src.worker.stages.build.GitOps")
    @patch("src.worker.stages.build.BuildExecutor")
    def test_uses_devcontainer_image(self, MockExecutor, MockGitOps, ctx, build_stage):
        """Uses image from devcontainer.json when available."""
        ctx.docker_runner = MagicMock()
        ctx.docker_runner.ensure_image.return_value = True
        MockGitOps.get_builder_image.return_value = "containers.ad.corekinect.com/ncs-fw-dev:3.0.0"
        MockExecutor.return_value.run_build.return_value = (True, "ok")

        build_stage.execute(ctx)

        assert ctx.builder_image == "containers.ad.corekinect.com/ncs-fw-dev:3.0.0"

    @patch("src.worker.stages.build.GitOps")
    @patch("src.worker.stages.build.BuildExecutor")
    def test_falls_back_to_default_image(self, MockExecutor, MockGitOps, ctx, build_stage):
        """Falls back to default builder image when devcontainer.json is missing."""
        ctx.docker_runner = MagicMock()
        ctx.docker_runner.ensure_image.return_value = True
        MockGitOps.get_builder_image.return_value = None
        MockExecutor.return_value.run_build.return_value = (True, "ok")

        build_stage.execute(ctx)

        assert ctx.builder_image == ctx.config.default_builder_image

    @patch("src.worker.stages.build.GitOps")
    def test_image_pull_failure(self, MockGitOps, ctx, build_stage):
        """Fails when builder image can't be pulled."""
        ctx.docker_runner = MagicMock()
        ctx.docker_runner.ensure_image.return_value = False
        MockGitOps.get_builder_image.return_value = "bad:image"

        result = build_stage.execute(ctx)

        assert not result.success
        assert "pull" in result.error.lower()


class TestFetchProductTargets:
    """Test product target metadata fetching."""

    @patch("src.worker.stages.build.BuildExecutor")
    def test_fetches_targets_matching_board(self, MockExecutor, ctx, build_stage):
        """Populates config_flags with matching board targets."""
        ctx.job.product_id = "prod-1"
        ctx.job.board = "alpha_b0"
        ctx.client.api_get.return_value = {
            "data": {
                "id": "prod-1",
                "buildConfig": {"sdk": "ncs-3.2.1"},
                "boards": [{
                    "revisions": [{
                        "ckBoardsName": "alpha_b0",
                        "targets": [
                            {"role": "app", "appId": 109, "processor": "nRF52840"},
                            {"role": "comms", "appId": 108, "soc": "nRF9151"},
                        ],
                    }],
                }],
            },
        }
        MockExecutor.return_value.run_build.return_value = (True, "ok")

        build_stage.execute(ctx)

        assert ctx.build_config == {"sdk": "ncs-3.2.1"}
        targets_json = ctx.job.config_flags.get("_targets_json", "[]")
        import json
        targets = json.loads(targets_json)
        assert len(targets) == 2
        assert targets[0]["role"] == "app"
        assert targets[1]["appId"] == 108

    @patch("src.worker.stages.build.BuildExecutor")
    def test_no_matching_board_produces_empty_targets(self, MockExecutor, ctx, build_stage):
        """When board doesn't match any revision, targets list is empty."""
        ctx.job.product_id = "prod-1"
        ctx.job.board = "alpha_c0"
        ctx.client.api_get.return_value = {
            "data": {
                "id": "prod-1",
                "boards": [{
                    "revisions": [{"ckBoardsName": "alpha_b0", "targets": []}],
                }],
            },
        }
        MockExecutor.return_value.run_build.return_value = (True, "ok")

        build_stage.execute(ctx)

        targets_json = ctx.job.config_flags.get("_targets_json", "[]")
        assert targets_json == "[]"

    @patch("src.worker.stages.build.BuildExecutor")
    def test_no_product_id_skips_fetch(self, MockExecutor, ctx, build_stage):
        """When product_id is None, target fetch is skipped entirely."""
        ctx.job.product_id = None
        ctx.webhook_data = {}
        MockExecutor.return_value.run_build.return_value = (True, "ok")

        build_stage.execute(ctx)

        ctx.client.api_get.assert_not_called()

    @patch("src.worker.stages.build.BuildExecutor")
    def test_api_error_skips_targets(self, MockExecutor, ctx, build_stage):
        """When API returns None, targets are not populated."""
        ctx.job.product_id = "prod-1"
        ctx.client.api_get.return_value = None
        MockExecutor.return_value.run_build.return_value = (True, "ok")

        build_stage.execute(ctx)

        assert ctx.build_config is None
