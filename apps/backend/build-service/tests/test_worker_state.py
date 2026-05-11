"""Tests for WorkerState — in-memory worker state tracking."""

from __future__ import annotations

import time

import pytest

from src.worker.state import WorkerState


class TestWorkerState:
    def test_initial_state(self):
        ws = WorkerState(worker_id="w1")
        assert ws.status == "idle"
        assert ws.current_job_id is None
        assert ws.is_busy is False
        assert ws.jobs_completed == 0
        assert ws.jobs_failed == 0

    def test_start_job(self):
        ws = WorkerState(worker_id="w1")
        ws.start_job("job-123", product="alpha")
        assert ws.status == "building"
        assert ws.current_job_id == "job-123"
        assert ws.current_job_product == "alpha"
        assert ws.current_step == "starting"
        assert ws.is_busy is True

    def test_update_step(self):
        ws = WorkerState(worker_id="w1")
        ws.start_job("job-123")
        ws.update_step("cloning")
        assert ws.current_step == "cloning"

    def test_finish_job_success(self):
        ws = WorkerState(worker_id="w1")
        ws.start_job("job-123")
        ws.finish_job(success=True)
        assert ws.status == "idle"
        assert ws.current_job_id is None
        assert ws.is_busy is False
        assert ws.jobs_completed == 1
        assert ws.jobs_failed == 0

    def test_finish_job_failure(self):
        ws = WorkerState(worker_id="w1")
        ws.start_job("job-123")
        ws.finish_job(success=False)
        assert ws.status == "idle"
        assert ws.jobs_completed == 0
        assert ws.jobs_failed == 1

    def test_multiple_jobs(self):
        ws = WorkerState(worker_id="w1")
        ws.start_job("j1")
        ws.finish_job(True)
        ws.start_job("j2")
        ws.finish_job(False)
        ws.start_job("j3")
        ws.finish_job(True)
        assert ws.jobs_completed == 2
        assert ws.jobs_failed == 1

    def test_draining(self):
        ws = WorkerState(worker_id="w1")
        ws.set_draining()
        assert ws.status == "draining"

    def test_to_dict(self):
        ws = WorkerState(worker_id="w1")
        ws.start_job("job-456", product="sigma")
        ws.update_step("building")
        d = ws.to_dict()
        assert d["workerId"] == "w1"
        assert d["status"] == "building"
        assert d["currentJobId"] == "job-456"
        assert d["currentJobProduct"] == "sigma"
        assert d["currentStep"] == "building"
        assert d["uptimeSeconds"] >= 0

    def test_uptime(self):
        ws = WorkerState(worker_id="w1")
        assert ws.uptime_seconds >= 0


class TestCancelSignal:
    """Tests for the cancel_event / request_cancel / clear_cancel flow."""

    def test_no_cancel_when_idle(self):
        ws = WorkerState(worker_id="w1")
        assert ws.cancel_requested is False
        # request_cancel on an idle worker returns False and does NOT flip
        # the event — there's nothing to cancel.
        assert ws.request_cancel(reason="user") is False
        assert ws.cancel_requested is False
        assert ws.cancel_reason is None

    def test_request_cancel_when_busy(self):
        ws = WorkerState(worker_id="w1")
        ws.start_job("job-1")
        assert ws.request_cancel(reason="user") is True
        assert ws.cancel_requested is True
        assert ws.cancel_event.is_set()
        assert ws.cancel_reason == "user"

    def test_start_job_clears_stale_cancel(self):
        """A new job must not inherit the previous job's cancel signal."""
        ws = WorkerState(worker_id="w1")
        ws.start_job("job-1")
        ws.request_cancel(reason="user")
        assert ws.cancel_requested is True
        # Even without an explicit finish_job, starting a new one resets.
        ws.start_job("job-2")
        assert ws.cancel_requested is False
        assert ws.cancel_reason is None

    def test_clear_cancel_is_idempotent(self):
        ws = WorkerState(worker_id="w1")
        ws.clear_cancel()
        ws.clear_cancel()
        assert ws.cancel_requested is False

    def test_finish_job_counts_cancelled_separately(self):
        """Cancellation should not pollute jobs_failed."""
        ws = WorkerState(worker_id="w1")
        ws.start_job("job-1")
        ws.request_cancel()
        # The runner returns success=False on cancel; finish_job should
        # bucket this into jobs_cancelled, not jobs_failed.
        ws.finish_job(success=False)
        assert ws.jobs_cancelled == 1
        assert ws.jobs_failed == 0
        assert ws.jobs_completed == 0

    def test_request_cancel_with_custom_reason(self):
        ws = WorkerState(worker_id="w1")
        ws.start_job("job-1")
        ws.request_cancel(reason="shutdown")
        assert ws.cancel_reason == "shutdown"

    def test_to_dict_exposes_cancel_state(self):
        ws = WorkerState(worker_id="w1")
        ws.start_job("job-1")
        ws.request_cancel(reason="user")
        d = ws.to_dict()
        assert d["cancelRequested"] is True
        assert d["cancelReason"] == "user"
        assert d["jobsCancelled"] == 0  # only counted after finish_job
