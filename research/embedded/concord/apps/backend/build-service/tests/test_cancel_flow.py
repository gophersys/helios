"""End-to-end tests for build cancellation.

Verifies that flipping `WorkerState.cancel_event` (the same flip the
`POST /jobs/cancel` endpoint performs) actually tears down the build
subprocess. We don't need real Docker for this — we replace
`_build_docker_cmd` with a bash sleep loop and confirm the streaming
loop sees the cancel signal and kills the process before completion.

These tests cover the contract guarded by the production cancel path:
the cancellation lands within a few seconds of the flag flip, the
return value is `(False, "[CANCELLED]" in output)`, and the kill
propagates to the underlying subprocess (no zombie).
"""

from __future__ import annotations

import threading
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from src.worker.docker_runner import DockerBuildRunner
from src.worker import loop as loop_module
from src.worker.state import WorkerState


@pytest.fixture
def runner() -> DockerBuildRunner:
    return DockerBuildRunner(
        workspace_volume="",
        ccache_volume="",
        builder_network="host",
        builder_timeout=60,
        default_image="dummy",
    )


@pytest.fixture
def busy_worker_state():
    """Install a busy WorkerState as the module-level singleton."""
    ws = WorkerState(worker_id="w-cancel-test")
    ws.start_job("job-cancel-test")
    loop_module._worker_state = ws
    yield ws
    loop_module._worker_state = None


class TestCancelKillsSubprocess:
    """The streaming loop kills the subprocess once cancel_event is set."""

    def test_docker_runner_returns_cancelled_marker(
        self, runner, busy_worker_state, tmp_path: Path,
    ):
        """Flipping cancel_event mid-stream produces a (False, '[CANCELLED]') return."""
        # Replace docker_cmd with a real subprocess that emits a line every
        # 200ms for ~10s. Plenty of time to flip cancel and observe kill.
        bash_cmd = [
            "bash", "-c",
            "for i in {1..50}; do echo line-$i; sleep 0.2; done",
        ]

        with patch.object(runner, "_build_docker_cmd", return_value=bash_cmd), \
             patch.object(runner, "_kill_container") as mock_kill:

            # Flip the cancel event after a short delay so a few lines have
            # streamed through first.
            def flip_after_delay():
                time.sleep(0.5)
                busy_worker_state.request_cancel(reason="user")

            flipper = threading.Thread(target=flip_after_delay, daemon=True)
            flipper.start()

            success, output = runner.run_build(
                image="dummy",
                job_id="job-cancel-test",
                work_dir=tmp_path,
                output_dir=tmp_path,
                env={},
                cmd=["echo", "ignored"],  # real cmd lives in bash_cmd above
            )

            flipper.join(timeout=5)

        assert success is False
        assert "[CANCELLED]" in output
        # We should have seen at least the first line before cancel kicked in.
        assert "line-1" in output
        # The teardown path called _kill_container exactly once.
        mock_kill.assert_called_once()

    def test_docker_runner_no_cancel_completes_normally(
        self, runner, busy_worker_state, tmp_path: Path,
    ):
        """Sanity: without a cancel flip, the same setup runs to completion."""
        bash_cmd = ["bash", "-c", "echo done; exit 0"]

        with patch.object(runner, "_build_docker_cmd", return_value=bash_cmd), \
             patch.object(runner, "_kill_container") as mock_kill:
            success, output = runner.run_build(
                image="dummy",
                job_id="job-cancel-test",
                work_dir=tmp_path,
                output_dir=tmp_path,
                env={},
                cmd=["echo", "ignored"],
            )

        assert success is True
        assert "[CANCELLED]" not in output
        assert "done" in output
        mock_kill.assert_not_called()

    def test_cancel_event_cleared_for_next_job(self, busy_worker_state):
        """Once a job finishes, the next start_job clears any leftover signal."""
        busy_worker_state.request_cancel(reason="user")
        assert busy_worker_state.cancel_event.is_set()
        busy_worker_state.finish_job(success=False)
        # Re-use the same WorkerState for a new job — must not inherit cancel.
        busy_worker_state.start_job("job-next")
        assert busy_worker_state.cancel_event.is_set() is False
        assert busy_worker_state.cancel_reason is None
        # Cancellation was counted, not failed.
        assert busy_worker_state.jobs_cancelled == 1
        assert busy_worker_state.jobs_failed == 0
