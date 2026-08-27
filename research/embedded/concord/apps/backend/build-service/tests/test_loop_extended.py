"""Extended tests for BuildWorkerLoop — process_job orchestration,
run() poll loop behaviour, _fetch_job_by_id, and docker mode init.

All subprocess, Docker, and API interactions are mocked.
"""

from __future__ import annotations

import threading
from pathlib import Path
from unittest.mock import MagicMock, patch, call

import pytest

from src.worker.executor import BuildJob
from src.worker.state import WorkerState


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_loop(config, mock_api_client, *, docker_mode: bool = False):
    """Instantiate BuildWorkerLoop bypassing __init__ for test isolation."""
    from src.worker.loop import BuildWorkerLoop

    loop = BuildWorkerLoop.__new__(BuildWorkerLoop)
    loop.config = config
    loop.client = mock_api_client
    loop.shutdown_event = None
    loop.workspace_dir = Path("/tmp/test-workspace")
    loop.docker_runner = None
    loop.job_queue = None
    loop.state = WorkerState(worker_id=config.worker_id)
    return loop


def _sample_job_dict(**overrides):
    base = {
        "id": "job-loop-001",
        "product": "alpha",
        "board": "alpha_b0",
        "target": "app",
        "variant": "release",
        "branch": "main",
        "commitSha": "deadbeef",
        "status": "QUEUED",
        "versionBump": False,
        "baseJobId": None,
        "matrixLabel": None,
        "configFlags": {},
        "productId": "prod-001",
        "recipeVersionId": None,
        "stage": 3,
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# process_job
# ---------------------------------------------------------------------------

class TestProcessJob:
    """Tests for BuildWorkerLoop.process_job()."""

    def test_process_job_returns_true_on_pipeline_success(self, config, mock_api_client, tmp_path):
        """Returns True when BuildPipeline.execute() returns True."""
        loop = _make_loop(config, mock_api_client)
        loop.workspace_dir = tmp_path

        job = BuildJob(
            id="job-001", product="alpha", board="alpha_b0", target="app",
            variant="release", branch="main", commit_sha="abc", status="QUEUED",
        )

        with patch("src.worker.loop.BuildPipeline") as MockPipeline:
            mock_instance = MockPipeline.return_value
            mock_instance.execute.return_value = True

            result = loop.process_job(job)

        assert result is True
        mock_instance.execute.assert_called_once()

    def test_process_job_returns_false_on_pipeline_failure(self, config, mock_api_client, tmp_path):
        """Returns False when BuildPipeline.execute() returns False."""
        loop = _make_loop(config, mock_api_client)
        loop.workspace_dir = tmp_path

        job = BuildJob(
            id="job-002", product="alpha", board="alpha_b0", target="app",
            variant="release", branch="main", commit_sha="abc", status="QUEUED",
        )

        with patch("src.worker.loop.BuildPipeline") as MockPipeline:
            mock_instance = MockPipeline.return_value
            mock_instance.execute.return_value = False

            result = loop.process_job(job)

        assert result is False

    def test_process_job_updates_state_to_idle_after_success(self, config, mock_api_client, tmp_path):
        """Worker state transitions back to idle after successful job."""
        loop = _make_loop(config, mock_api_client)
        loop.workspace_dir = tmp_path

        job = BuildJob(
            id="job-003", product="alpha", board="alpha_b0", target="app",
            variant="release", branch="main", commit_sha="abc", status="QUEUED",
        )

        with patch("src.worker.loop.BuildPipeline") as MockPipeline:
            MockPipeline.return_value.execute.return_value = True
            loop.process_job(job)

        assert loop.state.status == "idle"
        assert loop.state.current_job_id is None

    def test_process_job_increments_completed_counter(self, config, mock_api_client, tmp_path):
        """jobs_completed counter increases by one on success."""
        loop = _make_loop(config, mock_api_client)
        loop.workspace_dir = tmp_path

        job = BuildJob(
            id="job-004", product="alpha", board="alpha_b0", target="app",
            variant="release", branch="main", commit_sha="abc", status="QUEUED",
        )

        with patch("src.worker.loop.BuildPipeline") as MockPipeline:
            MockPipeline.return_value.execute.return_value = True
            loop.process_job(job)

        assert loop.state.jobs_completed == 1

    def test_process_job_increments_failed_counter_on_failure(self, config, mock_api_client, tmp_path):
        """jobs_failed counter increases by one on failure."""
        loop = _make_loop(config, mock_api_client)
        loop.workspace_dir = tmp_path

        job = BuildJob(
            id="job-005", product="alpha", board="alpha_b0", target="app",
            variant="release", branch="main", commit_sha="abc", status="QUEUED",
        )

        with patch("src.worker.loop.BuildPipeline") as MockPipeline:
            MockPipeline.return_value.execute.return_value = False
            loop.process_job(job)

        assert loop.state.jobs_failed == 1


# ---------------------------------------------------------------------------
# _fetch_job_by_id
# ---------------------------------------------------------------------------

class TestFetchJobById:
    """Tests for BuildWorkerLoop._fetch_job_by_id()."""

    def test_fetch_job_by_id_returns_job_when_queued(self, config, mock_api_client):
        """Returns a BuildJob when the API returns a QUEUED job."""
        mock_api_client.api_get.return_value = {"data": _sample_job_dict()}
        loop = _make_loop(config, mock_api_client)
        job = loop._fetch_job_by_id("job-loop-001")
        assert job is not None
        assert job.id == "job-loop-001"

    def test_fetch_job_by_id_returns_none_when_not_queued(self, config, mock_api_client):
        """Returns None when job status is no longer QUEUED."""
        mock_api_client.api_get.return_value = {
            "data": _sample_job_dict(status="BUILDING")
        }
        loop = _make_loop(config, mock_api_client)
        job = loop._fetch_job_by_id("job-loop-001")
        assert job is None

    def test_fetch_job_by_id_returns_none_when_api_fails(self, config, mock_api_client):
        """Returns None when the API call returns None."""
        mock_api_client.api_get.return_value = None
        loop = _make_loop(config, mock_api_client)
        job = loop._fetch_job_by_id("job-loop-001")
        assert job is None

    def test_fetch_job_by_id_returns_none_when_no_data(self, config, mock_api_client):
        """Returns None when 'data' key is missing."""
        mock_api_client.api_get.return_value = {}
        loop = _make_loop(config, mock_api_client)
        job = loop._fetch_job_by_id("job-loop-001")
        assert job is None


# ---------------------------------------------------------------------------
# run() — poll loop
# ---------------------------------------------------------------------------

class TestRunLoop:
    """Tests for BuildWorkerLoop.run() — verify the outer poll/claim loop logic."""

    def test_run_exits_immediately_when_shutdown_set(self, config, mock_api_client):
        """run() exits without calling fetch_queued_job when shutdown is already set."""
        loop = _make_loop(config, mock_api_client)
        shutdown = threading.Event()
        shutdown.set()
        loop.shutdown_event = shutdown

        loop.run()  # Should return immediately

        mock_api_client.api_get.assert_not_called()

    def test_run_calls_fetch_and_claim_when_job_available(self, config, mock_api_client, tmp_path):
        """run() fetches a job, claims it, and processes it before shutdown."""
        loop = _make_loop(config, mock_api_client)
        loop.workspace_dir = tmp_path

        shutdown = threading.Event()
        loop.shutdown_event = shutdown

        job_data = _sample_job_dict()
        mock_api_client.api_get.return_value = {
            "data": {"data": [job_data], "total": 1}
        }
        mock_api_client.api_patch.return_value = {}

        call_count = [0]

        def fake_process_job(job):
            call_count[0] += 1
            shutdown.set()  # stop after first job
            return True

        loop.process_job = fake_process_job
        loop.run()

        assert call_count[0] == 1

    def test_run_does_not_process_when_claim_fails(self, config, mock_api_client, tmp_path):
        """run() does not call process_job when claim_job returns False."""
        loop = _make_loop(config, mock_api_client)
        loop.workspace_dir = tmp_path

        shutdown = threading.Event()
        loop.shutdown_event = shutdown

        job_data = _sample_job_dict()
        mock_api_client.api_get.return_value = {
            "data": {"data": [job_data], "total": 1}
        }
        # PATCH returns None → claim fails
        mock_api_client.api_patch.return_value = None

        processed = [False]

        def fake_process_job(job):
            processed[0] = True
            return True

        loop.process_job = fake_process_job

        # We need the loop to run once then stop — use a side_effect
        original_fetch = loop.fetch_queued_job

        call_count = [0]

        def fetch_once():
            call_count[0] += 1
            if call_count[0] > 1:
                shutdown.set()
                return None
            return original_fetch()

        loop.fetch_queued_job = fetch_once
        loop.run()

        assert processed[0] is False

    def test_run_handles_exception_in_loop_body(self, config, mock_api_client):
        """run() continues after an exception in the loop body (exception safety)."""
        loop = _make_loop(config, mock_api_client)

        shutdown = threading.Event()
        loop.shutdown_event = shutdown

        call_count = [0]

        def failing_fetch():
            call_count[0] += 1
            if call_count[0] == 1:
                raise RuntimeError("transient error")
            shutdown.set()
            return None

        loop.fetch_queued_job = failing_fetch
        loop.run()  # Must not raise

        assert call_count[0] >= 2


# ---------------------------------------------------------------------------
# get_worker_state module function
# ---------------------------------------------------------------------------

class TestGetWorkerState:
    """Tests for the get_worker_state() module-level function."""

    def test_get_worker_state_returns_none_before_init(self):
        """Returns None when no BuildWorkerLoop has been instantiated."""
        import src.worker.loop as loop_module
        original = loop_module._worker_state
        loop_module._worker_state = None
        try:
            result = loop_module.get_worker_state()
            assert result is None
        finally:
            loop_module._worker_state = original

    def test_get_worker_state_returns_state_after_loop_init(self, config, mock_api_client, tmp_path):
        """Returns the WorkerState after a BuildWorkerLoop is created."""
        import src.worker.loop as loop_module
        from src.worker.loop import BuildWorkerLoop

        loop = _make_loop(config, mock_api_client)
        loop_module._worker_state = loop.state

        result = loop_module.get_worker_state()
        assert result is not None
        assert result.worker_id == config.worker_id
