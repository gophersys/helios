"""Tests for BuildWorkerLoop with fully mocked dependencies."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.worker.executor import BuildJob


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_loop(config, mock_api_client):
    """Instantiate BuildWorkerLoop without real Docker access."""
    from src.worker.loop import BuildWorkerLoop
    from src.worker.state import WorkerState

    loop = BuildWorkerLoop.__new__(BuildWorkerLoop)
    loop.config = config
    loop.client = mock_api_client
    loop.shutdown_event = None
    from pathlib import Path
    loop.workspace_dir = Path("/tmp/test-workspace")
    loop.docker_runner = None
    loop.state = WorkerState(worker_id=config.worker_id)
    return loop


# ---------------------------------------------------------------------------
# fetch_queued_job
# ---------------------------------------------------------------------------

class TestFetchQueuedJob:
    """Tests for BuildWorkerLoop.fetch_queued_job()."""

    def test_fetch_queued_job_parses_correctly(self, config, mock_api_client):
        """fetch_queued_job returns a BuildJob with all fields from the API response."""
        mock_api_client.api_get.return_value = {
            "data": {
                "data": [
                    {
                        "id": "build-job-001",
                        "product": "alpha",
                        "board": "alpha_b0",
                        "target": "app",
                        "variant": "release",
                        "branch": "main",
                        "commitSha": "deadbeef01",
                        "status": "QUEUED",
                        "versionBump": False,
                        "baseJobId": None,
                        "matrixLabel": "release-r1",
                        "configFlags": {},
                        "productId": "prod-001",
                        "recipeVersionId": None,
                        "stage": 3,
                    }
                ],
                "total": 1,
            }
        }

        loop = _make_loop(config, mock_api_client)
        job = loop.fetch_queued_job()

        assert job is not None
        assert isinstance(job, BuildJob)
        assert job.id == "build-job-001"
        assert job.product == "alpha"
        assert job.board == "alpha_b0"
        assert job.target == "app"
        assert job.variant == "release"
        assert job.branch == "main"
        assert job.commit_sha == "deadbeef01"
        assert job.status == "QUEUED"
        assert job.matrix_label == "release-r1"
        assert job.product_id == "prod-001"
        assert job.stage == 3

    def test_fetch_queued_job_empty_queue_returns_none(self, config, mock_api_client):
        """Returns None when the API reports no queued jobs."""
        mock_api_client.api_get.return_value = {"data": {"data": [], "total": 0}}

        loop = _make_loop(config, mock_api_client)
        job = loop.fetch_queued_job()

        assert job is None

    def test_fetch_queued_job_api_error_returns_none(self, config, mock_api_client):
        """Returns None when the API returns None (network error)."""
        mock_api_client.api_get.return_value = None

        loop = _make_loop(config, mock_api_client)
        job = loop.fetch_queued_job()

        assert job is None

    def test_fetch_queued_job_flat_data_list(self, config, mock_api_client):
        """Handles flat list response (data.data is already a list at top level)."""
        mock_api_client.api_get.return_value = {
            "data": [
                {
                    "id": "build-flat-001",
                    "product": "alpha",
                    "board": "alpha_b0",
                    "target": "app",
                    "variant": "release",
                    "branch": "main",
                    "commitSha": "abc",
                    "status": "QUEUED",
                    "configFlags": {},
                }
            ]
        }

        loop = _make_loop(config, mock_api_client)
        job = loop.fetch_queued_job()

        assert job is not None
        assert job.id == "build-flat-001"

    def test_fetch_queued_job_stage_field_is_parsed(self, config, mock_api_client):
        """stage field is parsed into BuildJob.stage."""
        mock_api_client.api_get.return_value = {
            "data": {
                "data": [
                    {
                        "id": "build-stage-test",
                        "product": "alpha",
                        "board": "alpha_b0",
                        "target": "app",
                        "variant": "mfg",
                        "branch": "main",
                        "commitSha": "",
                        "status": "QUEUED",
                        "configFlags": {},
                        "stage": 101,
                    }
                ]
            }
        }
        loop = _make_loop(config, mock_api_client)
        job = loop.fetch_queued_job()
        assert job.stage == 101


# ---------------------------------------------------------------------------
# claim_job
# ---------------------------------------------------------------------------

class TestClaimJob:
    """Tests for BuildWorkerLoop.claim_job()."""

    def test_claim_job_success(self, config, mock_api_client):
        """claim_job returns True when PATCH succeeds without errors."""
        mock_api_client.api_patch.return_value = {"id": "build-job-001"}

        loop = _make_loop(config, mock_api_client)
        result = loop.claim_job("build-job-001")

        assert result is True
        mock_api_client.api_patch.assert_called_once()

    def test_claim_job_sets_status_to_cloning(self, config, mock_api_client):
        """claim_job sends status=CLONING to the API."""
        mock_api_client.api_patch.return_value = {}

        loop = _make_loop(config, mock_api_client)
        loop.claim_job("build-job-001")

        _, kwargs = mock_api_client.api_patch.call_args
        # Second positional arg is the data dict
        args = mock_api_client.api_patch.call_args[0]
        assert args[1]["status"] == "CLONING"

    def test_claim_job_failure_returns_false(self, config, mock_api_client):
        """claim_job returns False when API returns None."""
        mock_api_client.api_patch.return_value = None

        loop = _make_loop(config, mock_api_client)
        result = loop.claim_job("build-job-001")

        assert result is False

    def test_claim_job_failure_on_errors_field(self, config, mock_api_client):
        """claim_job returns False when response contains an 'errors' field."""
        mock_api_client.api_patch.return_value = {"errors": ["conflict"]}

        loop = _make_loop(config, mock_api_client)
        result = loop.claim_job("build-job-001")

        assert result is False


# ---------------------------------------------------------------------------
# update_job
# ---------------------------------------------------------------------------

class TestUpdateJob:
    """Tests for BuildWorkerLoop.update_job()."""

    def test_update_job_truncates_long_error(self, config, mock_api_client):
        """Error messages longer than 2000 chars are truncated."""
        mock_api_client.api_patch.return_value = {}
        long_error = "E" * 5000

        loop = _make_loop(config, mock_api_client)
        loop.update_job("job-001", "FAILED", error=long_error)

        args = mock_api_client.api_patch.call_args[0]
        sent_error = args[1]["errorMessage"]
        assert len(sent_error) <= 2000

    def test_update_job_sets_finished_at_on_success(self, config, mock_api_client):
        """finishedAt is included in data for terminal status SUCCESS."""
        mock_api_client.api_patch.return_value = {}

        loop = _make_loop(config, mock_api_client)
        loop.update_job("job-001", "SUCCESS")

        args = mock_api_client.api_patch.call_args[0]
        assert "finishedAt" in args[1]

    def test_update_job_sets_finished_at_on_failed(self, config, mock_api_client):
        """finishedAt is included in data for terminal status FAILED."""
        mock_api_client.api_patch.return_value = {}

        loop = _make_loop(config, mock_api_client)
        loop.update_job("job-001", "FAILED")

        args = mock_api_client.api_patch.call_args[0]
        assert "finishedAt" in args[1]

    def test_update_job_sets_finished_at_on_cancelled(self, config, mock_api_client):
        """finishedAt is included in data for terminal status CANCELLED."""
        mock_api_client.api_patch.return_value = {}

        loop = _make_loop(config, mock_api_client)
        loop.update_job("job-001", "CANCELLED")

        args = mock_api_client.api_patch.call_args[0]
        assert "finishedAt" in args[1]

    def test_update_job_non_terminal_has_no_finished_at(self, config, mock_api_client):
        """Non-terminal status (BUILDING) does not include finishedAt."""
        mock_api_client.api_patch.return_value = {}

        loop = _make_loop(config, mock_api_client)
        loop.update_job("job-001", "BUILDING")

        args = mock_api_client.api_patch.call_args[0]
        assert "finishedAt" not in args[1]

    def test_update_job_includes_version_string(self, config, mock_api_client):
        """version_string kwarg is forwarded as 'versionString' in the payload."""
        mock_api_client.api_patch.return_value = {}

        loop = _make_loop(config, mock_api_client)
        loop.update_job("job-001", "SUCCESS", version_string="0.8.3")

        args = mock_api_client.api_patch.call_args[0]
        assert args[1]["versionString"] == "0.8.3"

    @pytest.mark.parametrize("status", ["SUCCESS", "FAILED", "CANCELLED"])
    def test_update_job_terminal_statuses_all_set_finished_at(self, config, mock_api_client, status):
        """All three terminal statuses include finishedAt."""
        mock_api_client.api_patch.return_value = {}
        loop = _make_loop(config, mock_api_client)
        loop.update_job("job-001", status)
        args = mock_api_client.api_patch.call_args[0]
        assert "finishedAt" in args[1]

    # TODO: test_update_job_returns_true_on_api_success
    # TODO: test_update_job_returns_false_when_api_returns_none
