"""WorkerState — in-memory worker state tracking.

Replaces the broken local Prisma DB with a simple dataclass.
The HTTP-API is the single source of truth for all build state.
This module tracks only what the worker needs locally: current job,
status, and basic counters for the /health and /status endpoints.
"""

from __future__ import annotations

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
    uptime_start: float = field(default_factory=time.time)

    def start_job(self, job_id: str, product: str = ""):
        """Mark a job as in progress."""
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
        """Mark current job as finished."""
        if success:
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

    @property
    def uptime_seconds(self) -> int:
        return int(time.time() - self.uptime_start)

    @property
    def is_busy(self) -> bool:
        return self.current_job_id is not None

    def to_dict(self) -> dict:
        """Serialize for API responses."""
        return {
            "workerId": self.worker_id,
            "status": self.status,
            "currentJobId": self.current_job_id,
            "currentJobProduct": self.current_job_product,
            "currentStep": self.current_step,
            "jobsCompleted": self.jobs_completed,
            "jobsFailed": self.jobs_failed,
            "uptimeSeconds": self.uptime_seconds,
        }
