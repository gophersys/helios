"""Tests for build dedup, auto-cancel, and auto-progress logic."""

import types
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def svc_mock_db():
    """Fresh mock DB for service-level tests (not patched into module global)."""
    from tests.conftest import MockPrismaClient
    client = MockPrismaClient()
    return client


def _make_build_run(**kwargs):
    defaults = {
        "id": "run-1",
        "productId": "prod-1",
        "board": "alpha_b0",
        "branch": "feature/test",
        "commitSha": "abc1234",
        "status": "BUILDING",
        "triggerType": "pr_push",
        "stage": 5,
        "stageConfigId": "stage-cfg-1",
        "prNumber": 42,
        "prTitle": "Test PR",
        "prAuthor": "mateo",
        "sourceBranch": "feature/test",
        "targetBranch": "main",
        "prUrl": "https://bitbucket.org/test/pr/42",
        "expectedBuilds": 2,
        "completedBuilds": 0,
        "startedAt": datetime(2026, 4, 1, tzinfo=timezone.utc),
        "finishedAt": None,
        "createdAt": datetime(2026, 4, 1, tzinfo=timezone.utc),
        "updatedAt": datetime(2026, 4, 1, tzinfo=timezone.utc),
    }
    defaults.update(kwargs)
    return types.SimpleNamespace(**defaults)


class TestCancelStaleRuns:
    """Test _cancel_stale_runs() in build_trigger.py."""

    def test_cancels_old_runs_for_same_pr_stage(self, svc_mock_db):
        from src.services.builds.trigger import _cancel_stale_runs

        old_run = _make_build_run(id="old-run", commitSha="old1234", status="BUILDING")
        svc_mock_db.buildrun.find_many.return_value = [old_run]

        _cancel_stale_runs(svc_mock_db, "prod-1", 42, 5, "new5678")

        # Should cancel the old run's jobs
        svc_mock_db.buildjob.update_many.assert_called_once()
        cancel_args = svc_mock_db.buildjob.update_many.call_args
        assert cancel_args.kwargs["where"]["buildRunId"] == "old-run"
        assert cancel_args.kwargs["data"]["status"] == "CANCELLED"

        # Should cancel the old run itself
        svc_mock_db.buildrun.update.assert_called_once()
        update_args = svc_mock_db.buildrun.update.call_args
        assert update_args.kwargs["where"]["id"] == "old-run"
        assert update_args.kwargs["data"]["status"] == "CANCELLED"

    def test_skips_if_no_stale_runs(self, svc_mock_db):
        from src.services.builds.trigger import _cancel_stale_runs

        svc_mock_db.buildrun.find_many.return_value = []

        _cancel_stale_runs(svc_mock_db, "prod-1", 42, 5, "new5678")

        svc_mock_db.buildjob.update_many.assert_not_called()
        svc_mock_db.buildrun.update.assert_not_called()

    def test_cancels_multiple_stale_runs(self, svc_mock_db):
        from src.services.builds.trigger import _cancel_stale_runs

        old1 = _make_build_run(id="old-1", commitSha="aaa", status="BUILDING")
        old2 = _make_build_run(id="old-2", commitSha="bbb", status="PENDING")
        svc_mock_db.buildrun.find_many.return_value = [old1, old2]

        _cancel_stale_runs(svc_mock_db, "prod-1", 42, 5, "new5678")

        assert svc_mock_db.buildjob.update_many.call_count == 2
        assert svc_mock_db.buildrun.update.call_count == 2


class TestDedup:
    """Test dedup logic in trigger_stage_build()."""

    @patch("src.services.builds.trigger.get_db_client")
    @patch("src.services.builds.trigger.log_audit")
    def test_dedup_skips_duplicate_commit(self, mock_audit, mock_get_db, svc_mock_db):
        from src.services.builds.trigger import trigger_stage_build

        mock_get_db.return_value = svc_mock_db

        product = types.SimpleNamespace(
            id="prod-1", name="Alpha", fwRepoSlug="alpha_fw",
            mfgFwRepoSlug="alpha_mfg_fw", builderImage="builder:latest",
            boards=[],
        )
        stage_config = types.SimpleNamespace(
            id="sc-1", stage=5, name="FUOTA", watchBranch="main",
            boardRevisionId="rev-1", signingKeyId=None,
            boardRevision=types.SimpleNamespace(id="rev-1", ckBoardsName="alpha_b0"),
            signingKey=None,
        )
        svc_mock_db.product.find_unique.return_value = product
        svc_mock_db.productstageconfig.find_unique.return_value = stage_config

        existing_run = _make_build_run(id="existing-run", commitSha="abc1234")
        svc_mock_db.buildrun.find_first.return_value = existing_run

        result = trigger_stage_build(
            "prod-1", "sc-1",
            event_metadata={"source_commit": "abc1234", "source": "poller"},
        )

        assert result is not None
        assert result["deduplicated"] is True
        assert result["buildRunId"] == "existing-run"
        svc_mock_db.buildrun.create.assert_not_called()


class TestTriggerTypeNormalization:
    """Test that trigger types are normalized to the correct vocabulary."""

    @patch("src.services.builds.trigger.get_db_client")
    @patch("src.services.builds.trigger.log_audit")
    @patch("src.services.builds.trigger.get_stage_build_defs")
    def test_pr_push_trigger_type(self, mock_defs, mock_audit, mock_get_db, svc_mock_db):
        from src.services.builds.trigger import trigger_stage_build

        mock_get_db.return_value = svc_mock_db

        # Give it a build def so it gets past the empty check
        build_def = types.SimpleNamespace(
            label="mfg_app_debug", fw_type="app", variant="debug",
            config_log=True, produces_hex=True, produces_cfw=False,
            git_ref="pr", is_version_bump=False, base_label=None,
        )
        mock_defs.return_value = [build_def]

        product = types.SimpleNamespace(
            id="prod-1", name="Alpha", fwRepoSlug="alpha_fw",
            mfgFwRepoSlug="alpha_mfg_fw", builderImage=None, boards=[],
        )
        stage_config = types.SimpleNamespace(
            id="sc-1", stage=1, name="Smoke", watchBranch="main",
            boardRevisionId="rev-1", signingKeyId=None,
            boardRevision=types.SimpleNamespace(id="rev-1", ckBoardsName="alpha_b0"),
            signingKey=None,
        )
        svc_mock_db.product.find_unique.return_value = product
        svc_mock_db.productstageconfig.find_unique.return_value = stage_config
        svc_mock_db.buildrun.find_first.return_value = None  # No dedup match

        created_run = types.SimpleNamespace(id="new-run")
        svc_mock_db.buildrun.create.return_value = created_run
        created_job = types.SimpleNamespace(id="job-1", status="QUEUED")
        svc_mock_db.buildjob.create.return_value = created_job
        svc_mock_db.buildjob.find_unique.return_value = created_job

        with patch("src.services.builds.job_runner.create_build_k8s_job", return_value=None):
            result = trigger_stage_build(
                "prod-1", "sc-1",
                event_metadata={"pr_id": 42, "source_commit": "abc", "source_branch": "feat/x"},
            )

        # Verify BuildRun was created with normalized trigger type
        create_call = svc_mock_db.buildrun.create.call_args
        assert create_call.kwargs["data"]["triggerType"] == "pr_push"
        # And PR fields are populated
        assert create_call.kwargs["data"]["prNumber"] == 42
        assert create_call.kwargs["data"]["sourceBranch"] == "feat/x"


class TestPrBuildsSummary:
    """Test the PR builds and summary endpoints.

    These tests use the authed_client/mock_db from conftest which properly
    patches the module-level DB global.
    """

    @pytest.fixture(autouse=True)
    def _use_conftest_db(self, mock_db):
        """Ensure we use the conftest mock_db that patches the global."""
        pass

    def test_pr_build_runs_empty(self, authed_client, mock_db):
        mock_db.buildrun.find_many.return_value = []
        resp = authed_client.get("/v2/builds/prs")
        assert resp.status_code == 200
        data = resp.get_json()["data"]["data"]
        assert data == []

    def test_pr_build_runs_groups_by_pr(self, authed_client, mock_db):
        product = types.SimpleNamespace(name="Alpha", id="prod-1")
        run1 = _make_build_run(
            id="run-1", prNumber=42, stage=1, status="SUCCESS",
            product=product,
        )
        run2 = _make_build_run(
            id="run-2", prNumber=42, stage=5, status="BUILDING",
            product=product,
        )
        mock_db.buildrun.find_many.return_value = [run2, run1]

        resp = authed_client.get("/v2/builds/prs")
        assert resp.status_code == 200
        data = resp.get_json()["data"]["data"]
        assert len(data) == 1
        pr = data[0]
        assert pr["prNumber"] == 42
        assert pr["stages"]["1"]["status"] == "SUCCESS"
        assert pr["stages"]["5"]["status"] == "BUILDING"
        assert pr["stages"]["3"] is None  # Not triggered

    def test_summary_endpoint(self, authed_client, mock_db):
        mock_db.buildrun.count.return_value = 0
        mock_db.buildjob.count.return_value = 0
        mock_db.buildrun.find_many.return_value = []

        resp = authed_client.get("/v2/builds/summary")
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert "activeRuns" in data
        assert "queuedJobs" in data
        assert "successRate24h" in data
        assert "byStage" in data
        assert len(data["byStage"]) == 5

    def test_build_runs_stage_filter(self, authed_client, mock_db):
        mock_db.buildrun.count.return_value = 0
        mock_db.buildrun.find_many.return_value = []

        resp = authed_client.get("/v2/builds/runs?stage=5")
        assert resp.status_code == 200
        call_args = mock_db.buildrun.find_many.call_args
        assert call_args.kwargs["where"]["stage"] == 5

    def test_build_runs_pr_number_filter(self, authed_client, mock_db):
        mock_db.buildrun.count.return_value = 0
        mock_db.buildrun.find_many.return_value = []

        resp = authed_client.get("/v2/builds/runs?prNumber=42")
        assert resp.status_code == 200
        call_args = mock_db.buildrun.find_many.call_args
        assert call_args.kwargs["where"]["prNumber"] == 42

    def test_build_runs_trigger_type_filter(self, authed_client, mock_db):
        mock_db.buildrun.count.return_value = 0
        mock_db.buildrun.find_many.return_value = []

        resp = authed_client.get("/v2/builds/runs?triggerType=pr_push")
        assert resp.status_code == 200
        call_args = mock_db.buildrun.find_many.call_args
        assert call_args.kwargs["where"]["triggerType"] == "pr_push"
