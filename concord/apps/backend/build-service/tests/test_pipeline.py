"""Tests for BuildPipeline orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.worker.pipeline import BuildContext, BuildPipeline, Stage, StageResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

@dataclass
class PassStage:
    """A stage that always succeeds."""
    name: str = "pass"

    def execute(self, ctx: BuildContext) -> StageResult:
        return StageResult.ok()


@dataclass
class FailStage:
    """A stage that always fails with a given message."""
    name: str = "fail"
    error: str = "stage failed"

    def execute(self, ctx: BuildContext) -> StageResult:
        return StageResult.fail(self.error)


@dataclass
class TrackingStage:
    """A stage that records execution order."""
    name: str
    tracker: list

    def execute(self, ctx: BuildContext) -> StageResult:
        self.tracker.append(self.name)
        return StageResult.ok()


@dataclass
class ContextMutatingStage:
    """A stage that sets a field on the context."""
    name: str = "mutate"
    field_name: str = "version_string"
    field_value: str = "1.2.3"

    def execute(self, ctx: BuildContext) -> StageResult:
        setattr(ctx, self.field_name, self.field_value)
        return StageResult.ok()


def _make_context(tmp_path, sample_job, config, mock_api_client) -> BuildContext:
    work_dir = tmp_path / "work"
    output_dir = work_dir / "artifacts"
    return BuildContext(
        job=sample_job,
        config=config,
        client=mock_api_client,
        work_dir=work_dir,
        output_dir=output_dir,
    )


# ---------------------------------------------------------------------------
# StageResult
# ---------------------------------------------------------------------------

class TestStageResult:
    def test_ok_result(self):
        r = StageResult.ok()
        assert r.success is True
        assert r.error is None

    def test_fail_result(self):
        r = StageResult.fail("broke")
        assert r.success is False
        assert r.error == "broke"


# ---------------------------------------------------------------------------
# BuildPipeline execution
# ---------------------------------------------------------------------------

class TestBuildPipeline:
    def test_empty_pipeline_succeeds(self, tmp_path, sample_job, config, mock_api_client):
        """A pipeline with no stages reports SUCCESS."""
        ctx = _make_context(tmp_path, sample_job, config, mock_api_client)
        pipeline = BuildPipeline(stages=[], client=mock_api_client)

        result = pipeline.execute(ctx)

        assert result is True
        # Should have called api_patch with SUCCESS
        calls = mock_api_client.api_patch.call_args_list
        assert any("SUCCESS" in str(c) for c in calls)

    def test_all_stages_pass(self, tmp_path, sample_job, config, mock_api_client):
        """Pipeline succeeds when all stages pass."""
        ctx = _make_context(tmp_path, sample_job, config, mock_api_client)
        pipeline = BuildPipeline(
            stages=[PassStage("a"), PassStage("b"), PassStage("c")],
            client=mock_api_client,
        )

        result = pipeline.execute(ctx)

        assert result is True

    def test_first_stage_fails_stops_pipeline(self, tmp_path, sample_job, config, mock_api_client):
        """Pipeline stops after the first failing stage."""
        tracker = []
        ctx = _make_context(tmp_path, sample_job, config, mock_api_client)
        pipeline = BuildPipeline(
            stages=[
                FailStage(name="fail-early", error="boom"),
                TrackingStage(name="should-not-run", tracker=tracker),
            ],
            client=mock_api_client,
        )

        result = pipeline.execute(ctx)

        assert result is False
        assert "should-not-run" not in tracker

    def test_middle_stage_fails_stops_pipeline(self, tmp_path, sample_job, config, mock_api_client):
        """Later stages don't run when an earlier stage fails."""
        tracker = []
        ctx = _make_context(tmp_path, sample_job, config, mock_api_client)
        pipeline = BuildPipeline(
            stages=[
                TrackingStage(name="first", tracker=tracker),
                FailStage(name="second", error="broken"),
                TrackingStage(name="third", tracker=tracker),
            ],
            client=mock_api_client,
        )

        result = pipeline.execute(ctx)

        assert result is False
        assert tracker == ["first"]

    def test_stages_execute_in_order(self, tmp_path, sample_job, config, mock_api_client):
        """Stages execute in the order they're given."""
        tracker = []
        ctx = _make_context(tmp_path, sample_job, config, mock_api_client)
        pipeline = BuildPipeline(
            stages=[
                TrackingStage(name="clone", tracker=tracker),
                TrackingStage(name="recipe", tracker=tracker),
                TrackingStage(name="build", tracker=tracker),
                TrackingStage(name="upload", tracker=tracker),
            ],
            client=mock_api_client,
        )

        pipeline.execute(ctx)

        assert tracker == ["clone", "recipe", "build", "upload"]

    def test_context_flows_between_stages(self, tmp_path, sample_job, config, mock_api_client):
        """Stages can read values set by earlier stages via the context."""
        ctx = _make_context(tmp_path, sample_job, config, mock_api_client)
        pipeline = BuildPipeline(
            stages=[
                ContextMutatingStage(name="set-version", field_name="version_string", field_value="1.2.3"),
                PassStage("read-version"),
            ],
            client=mock_api_client,
        )

        pipeline.execute(ctx)

        assert ctx.version_string == "1.2.3"

    def test_failure_reports_to_api(self, tmp_path, sample_job, config, mock_api_client):
        """Failed pipeline reports FAILED status to the API."""
        ctx = _make_context(tmp_path, sample_job, config, mock_api_client)
        pipeline = BuildPipeline(
            stages=[FailStage(name="breaker", error="compile error")],
            client=mock_api_client,
        )

        pipeline.execute(ctx)

        # Find the FAILED patch call
        for call in mock_api_client.api_patch.call_args_list:
            args = call[0]
            if isinstance(args[1], dict) and args[1].get("status") == "FAILED":
                assert "compile error" in args[1]["errorMessage"]
                assert "finishedAt" in args[1]
                assert "durationSeconds" in args[1]
                return
        pytest.fail("No FAILED status reported to API")

    def test_success_reports_to_api(self, tmp_path, sample_job, config, mock_api_client):
        """Successful pipeline reports SUCCESS status to the API."""
        ctx = _make_context(tmp_path, sample_job, config, mock_api_client)
        pipeline = BuildPipeline(
            stages=[PassStage()],
            client=mock_api_client,
        )

        pipeline.execute(ctx)

        for call in mock_api_client.api_patch.call_args_list:
            args = call[0]
            if isinstance(args[1], dict) and args[1].get("status") == "SUCCESS":
                assert "finishedAt" in args[1]
                assert "durationSeconds" in args[1]
                return
        pytest.fail("No SUCCESS status reported to API")

    def test_success_includes_version_string(self, tmp_path, sample_job, config, mock_api_client):
        """SUCCESS report includes versionString if set by a stage."""
        ctx = _make_context(tmp_path, sample_job, config, mock_api_client)
        pipeline = BuildPipeline(
            stages=[ContextMutatingStage(name="ver", field_name="version_string", field_value="2.0.1")],
            client=mock_api_client,
        )

        pipeline.execute(ctx)

        for call in mock_api_client.api_patch.call_args_list:
            args = call[0]
            if isinstance(args[1], dict) and args[1].get("status") == "SUCCESS":
                assert args[1]["versionString"] == "2.0.1"
                return
        pytest.fail("No SUCCESS with versionString")

    def test_workspace_cleaned_on_success(self, tmp_path, sample_job, config, mock_api_client):
        """Workspace directory is deleted after successful pipeline."""
        ctx = _make_context(tmp_path, sample_job, config, mock_api_client)
        pipeline = BuildPipeline(stages=[PassStage()], client=mock_api_client)

        pipeline.execute(ctx)

        assert not ctx.work_dir.exists()

    def test_workspace_cleaned_on_failure(self, tmp_path, sample_job, config, mock_api_client):
        """Workspace directory is deleted after failed pipeline."""
        ctx = _make_context(tmp_path, sample_job, config, mock_api_client)
        pipeline = BuildPipeline(
            stages=[FailStage(error="fail")],
            client=mock_api_client,
        )

        pipeline.execute(ctx)

        assert not ctx.work_dir.exists()

    def test_fetches_webhook_data(self, tmp_path, sample_job, config, mock_api_client):
        """Pipeline fetches webhookData from API at start."""
        mock_api_client.api_get.return_value = {
            "data": {"webhookData": {"fwRepoSlug": "alpha_fw", "signingKeyValue": "abc123"}}
        }
        ctx = _make_context(tmp_path, sample_job, config, mock_api_client)
        pipeline = BuildPipeline(stages=[PassStage()], client=mock_api_client)

        pipeline.execute(ctx)

        assert ctx.webhook_data == {"fwRepoSlug": "alpha_fw", "signingKeyValue": "abc123"}

    def test_exception_in_stage_reports_failure(self, tmp_path, sample_job, config, mock_api_client):
        """Unhandled exception in a stage reports FAILED."""
        @dataclass
        class ExplodingStage:
            name: str = "boom"
            def execute(self, ctx):
                raise RuntimeError("unexpected explosion")

        ctx = _make_context(tmp_path, sample_job, config, mock_api_client)
        pipeline = BuildPipeline(stages=[ExplodingStage()], client=mock_api_client)

        result = pipeline.execute(ctx)

        assert result is False
