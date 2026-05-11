"""WorkerState — in-memory worker state tracking.

Replaces the broken local Prisma DB with a simple dataclass.
The HTTP-API is the single source of truth for all build state.
This module tracks only what the worker needs locally: current job,
status, basic counters for the /health and /status endpoints, and a
thread-safe cancellation signal flipped by the /jobs/cancel endpoint
and observed by the build subprocess streaming loops.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class WorkerState:
    """In-memory state for the build worker."""

    worker_id: str
    status: str = "idle"  # idle, building, draining, offline

    # Current job tracking
    current_job_id: Optional[str] = None
    current_step: Optional[str] = None
    current_step_started_at: Optional[float] = None
    current_job_product: Optional[str] = None

    # Counters
    jobs_completed: int = 0
    jobs_failed: int = 0
    jobs_cancelled: int = 0
    uptime_start: float = field(default_factory=time.time)

    # Cancellation signal. The /jobs/cancel HTTP handler runs in a Flask
    # worker thread; the build runs in the main thread. `threading.Event`
    # is the right primitive — flipped by request_cancel(), read by the
    # subprocess streaming loops in executor.py and docker_runner.py.
    cancel_event: threading.Event = field(default_factory=threading.Event)
    cancel_reason: Optional[str] = None  # "user" | "shutdown" | None

    def start_job(self, job_id: str, product: str = ""):
        """Mark a job as in progress. Always clears any leftover cancel signal."""
        self.clear_cancel()
        self.status = "building"
        self.current_job_id = job_id
        self.current_job_product = product
        self.current_step = "starting"
        self.current_step_started_at = time.time()

    def update_step(self, step: str):
        """Update the current build step."""
        self.current_step = step
        self.current_step_started_at = time.time()

    def finish_job(self, success: bool):
        """Mark current job as finished.

        Counts the outcome based on whether cancellation was active:
        - cancellation took it → jobs_cancelled
        - success            → jobs_completed
        - other failure      → jobs_failed
        """
        if self.cancel_event.is_set():
            self.jobs_cancelled += 1
        elif success:
            self.jobs_completed += 1
        else:
            self.jobs_failed += 1
        self.status = "idle"
        self.current_job_id = None
        self.current_job_product = None
        self.current_step = None
        self.current_step_started_at = None

    def set_draining(self):
        """Set worker to draining mode (finish current job, then stop)."""
        self.status = "draining"

    def request_cancel(self, reason: str = "user") -> bool:
        """Signal the in-flight build to cancel.

        Returns True if the request was accepted (a job was running), False
        if there was nothing to cancel. Idempotent — repeated calls are no-ops.
        """
        if not self.is_busy:
            return False
        self.cancel_reason = reason
        self.cancel_event.set()
        return True

    def clear_cancel(self):
        """Reset the cancellation signal. Called at the start of every job."""
        self.cancel_event.clear()
        self.cancel_reason = None

    @property
    def cancel_requested(self) -> bool:
        """Convenience for callers that don't want to import threading."""
        return self.cancel_event.is_set()

    @property
    def uptime_seconds(self) -> int:
        """Elapsed seconds since this worker instance started."""
        return int(time.time() - self.uptime_start)

    @property
    def is_busy(self) -> bool:
        """True when a job is currently being processed."""
        return self.current_job_id is not None

    def to_dict(self) -> dict:
        """Serialize for API responses."""
        return {
            "workerId": self.worker_id,
            "status": self.status,
            "currentJobId": self.current_job_id,
            "currentJobProduct": self.current_job_product,
            "currentStep": self.current_step,
            "cancelRequested": self.cancel_requested,
            "cancelReason": self.cancel_reason,
            "jobsCompleted": self.jobs_completed,
            "jobsFailed": self.jobs_failed,
            "jobsCancelled": self.jobs_cancelled,
            "uptimeSeconds": self.uptime_seconds,
        }
