"""Build worker — poll loop and job orchestration."""

import logging
import time
from pathlib import Path
from typing import Any, Dict, Optional

from src.clients.concord import ConcordClient
from src.config import BuildServiceConfig
from src.worker.executor import BuildJob, _extract_version_override
from src.worker.pipeline import BuildContext, BuildPipeline
from src.worker.stages.clone import CloneStage
from src.worker.stages.recipe import RecipeStage
from src.worker.stages.signing import SigningStage
from src.worker.stages.build import BuildStage
from src.worker.stages.artifacts import ArtifactStage
from src.worker.queue import JobQueue
from src.worker.state import WorkerState

log = logging.getLogger("build-service")

# Module-level worker state — shared with Flask API endpoints
_worker_state: Optional[WorkerState] = None


def get_worker_state() -> Optional[WorkerState]:
    """Get the global worker state (used by API endpoints)."""
    return _worker_state


class BuildWorkerLoop:
    """Firmware build worker that processes jobs from the Concord API.

    Each worker instance handles jobs for a specific NCS version.
    Multiple workers with different NCS versions can run in parallel.

    Repo configs are fetched from the API at startup from the Product model
    in DB. New products are discovered automatically.
    """

    def __init__(self, config: BuildServiceConfig, client: ConcordClient,
                 shutdown_event=None, job_queue: Optional[JobQueue] = None):
        global _worker_state

        self.config = config
        self.client = client
        self.shutdown_event = shutdown_event
        self.job_queue = job_queue
        self.workspace_dir = Path(config.workspace_dir)
        self.workspace_dir.mkdir(parents=True, exist_ok=True)

        # Docker build runner (if builder_mode == "docker")
        self.docker_runner = None
        if config.builder_mode == "docker":
            from src.worker.docker_runner import DockerBuildRunner
            self.docker_runner = DockerBuildRunner(
                workspace_volume=config.workspace_volume,
                ccache_volume=config.ccache_volume,
                builder_network=config.builder_network,
                builder_timeout=config.builder_timeout,
                default_image=config.default_builder_image,
            )
            log.info("Docker build mode enabled (default image: %s)", config.default_builder_image)

        # In-memory worker state (replaces broken local Prisma DB)
        self.state = WorkerState(worker_id=config.worker_id)
        _worker_state = self.state

    def fetch_queued_job(self) -> Optional[BuildJob]:
        """Fetch the next QUEUED build job matching this worker's NCS version."""
        result = self.client.api_get("/v2/builds?status=QUEUED&limit=20")
        if not result or not result.get("data"):
            return None

        # API returns { "data": { "data": [...], "total": N } } envelope
        inner = result["data"]
        jobs = inner.get("data", inner) if isinstance(inner, dict) else inner
        if not jobs:
            return None

        for j in jobs:
            # In docker mode, any NCS version is supported — skip version check
            return BuildJob(
                id=j["id"],
                product=j["product"],
                board=j["board"],
                target=j["target"],
                variant=j["variant"],
                branch=j["branch"],
                commit_sha=j["commitSha"] or "",
                status=j["status"],
                version_bump=j.get("versionBump", False),
                base_job_id=j.get("baseJobId"),
                matrix_label=j.get("matrixLabel"),
                version_override=_extract_version_override(j),
                config_flags=j.get("configFlags") or {},
                product_id=j.get("productId"),
                recipe_version_id=j.get("recipeVersionId"),
                stage=j.get("stage"),
            )

        return None

    def claim_job(self, job_id: str) -> bool:
        """Claim a job by setting status to CLONING (first phase of processing)."""
        result = self.client.api_patch(f"/v2/builds/{job_id}", {
            "status": "CLONING",
            "workerId": self.config.worker_id,
            "startedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        })
        if result is not None and not result.get("errors"):
            return True
        return False

    def update_job(self, job_id: str, status: str, error: Optional[str] = None,
                   version_string: Optional[str] = None, duration: Optional[int] = None) -> bool:
        """Update job status."""
        data: Dict[str, Any] = {"status": status}
        if error:
            data["errorMessage"] = error[:2000]
        if version_string:
            data["versionString"] = version_string
        if duration is not None:
            data["durationSeconds"] = duration
        if status in ("SUCCESS", "FAILED", "CANCELLED"):
            data["finishedAt"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

        result = self.client.api_patch(f"/v2/builds/{job_id}", data)
        return result is not None

    def process_job(self, job: BuildJob) -> bool:
        """Process a single build job via the stage pipeline.

        The pipeline executes: Clone → Recipe → Signing → Build → Artifacts.
        Each stage is independently testable. The pipeline handles workspace
        setup/cleanup and failure reporting.
        """
        self.state.start_job(job.id, product=job.product)

        work_dir = self.workspace_dir / job.id
        output_dir = work_dir / "artifacts"

        ctx = BuildContext(
            job=job,
            config=self.config,
            client=self.client,
            work_dir=work_dir,
            output_dir=output_dir,
            docker_runner=self.docker_runner,
        )

        pipeline = BuildPipeline(
            stages=[
                CloneStage(),
                RecipeStage(),
                SigningStage(),
                BuildStage(),
                ArtifactStage(),
            ],
            client=self.client,
        )

        success = pipeline.execute(ctx)
        self.state.finish_job(success)
        return success

    def run(self):
        """Main worker loop.

        If a job queue is provided (push mode), the worker waits for
        notifications with a fallback poll every poll_interval seconds.
        If no queue is provided, falls back to pure polling (legacy mode).
        """
        ncs_info = f", mode={self.config.builder_mode}"
        mode = "push+poll" if self.job_queue else "poll"
        log.info("Build worker starting (id=%s, poll=%ds, delivery=%s%s)",
                 self.config.worker_id, self.config.poll_interval, mode, ncs_info)

        while not (self.shutdown_event and self.shutdown_event.is_set()):
            try:
                job = None

                # Push mode: wait for notification with fallback poll
                if self.job_queue:
                    notified_id = self.job_queue.dequeue(timeout=float(self.config.poll_interval))
                    if notified_id:
                        log.info("Received job notification: %s", notified_id[:8])
                        # Fetch full job details from API
                        job = self._fetch_job_by_id(notified_id)
                    else:
                        # Timeout — fallback poll for any missed notifications
                        job = self.fetch_queued_job()
                else:
                    # Legacy poll mode
                    job = self.fetch_queued_job()

                if job:
                    if self.claim_job(job.id):
                        self.process_job(job)
                        # Clear from seen set after processing
                        if self.job_queue:
                            self.job_queue.clear_seen(job.id)
                    else:
                        log.debug("Failed to claim job %s (maybe taken by another worker)",
                                  job.id[:8])
                else:
                    log.debug("No jobs in queue")

            except Exception as e:
                log.exception("Worker loop error: %s", e)

                # Don't spin on errors — brief backoff
                if self.shutdown_event:
                    self.shutdown_event.wait(timeout=5)
                else:
                    time.sleep(5)

    def _fetch_job_by_id(self, job_id: str) -> Optional[BuildJob]:
        """Fetch a specific job by ID from the API."""
        result = self.client.api_get(f"/v2/builds/{job_id}")
        if not result or not result.get("data"):
            log.warning("Notified job %s not found in API", job_id[:8])
            return None

        j = result["data"]
        if j.get("status") != "QUEUED":
            log.debug("Job %s is no longer QUEUED (status=%s), skipping",
                      job_id[:8], j.get("status"))
            return None

        return BuildJob(
            id=j["id"],
            product=j["product"],
            board=j["board"],
            target=j["target"],
            variant=j["variant"],
            branch=j["branch"],
            commit_sha=j.get("commitSha") or "",
            status=j["status"],
            version_bump=j.get("versionBump", False),
            base_job_id=j.get("baseJobId"),
            matrix_label=j.get("matrixLabel"),
            version_override=_extract_version_override(j),
            config_flags=j.get("configFlags") or {},
            product_id=j.get("productId"),
            recipe_version_id=j.get("recipeVersionId"),
            stage=j.get("stage"),
        )
