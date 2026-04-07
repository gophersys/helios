"""Build pipeline — orchestrates a sequence of stages to process a build job.

Replaces the monolithic process_job method with a composable pipeline of
independently testable stages.
"""

from __future__ import annotations

import logging
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol

from src.clients.concord import ConcordClient
from src.config import BuildServiceConfig
from src.worker.executor import BuildJob

log = logging.getLogger("build-service")


@dataclass
class BuildContext:
    """Mutable context threaded through all pipeline stages.

    Each stage reads what it needs and writes its outputs here so the
    next stage can pick them up.
    """
    job: BuildJob
    config: BuildServiceConfig
    client: ConcordClient
    work_dir: Path
    output_dir: Path
    docker_runner: Any = None  # Optional[DockerBuildRunner]

    # Accumulated state — populated by stages as they execute
    webhook_data: Dict[str, Any] = field(default_factory=dict)
    primary_dir: Optional[Path] = None
    primary_slug: Optional[str] = None
    secondary_dir: Optional[Path] = None
    secondary_slug: Optional[str] = None
    builder_image: Optional[str] = None
    recipe_path: Optional[Path] = None
    version_string: Optional[str] = None
    build_config: Optional[Dict[str, Any]] = None
    signing_key_deployed: bool = False
    log_output: str = ""
    artifacts: List[Path] = field(default_factory=list)


@dataclass
class StageResult:
    """Result of executing a pipeline stage."""
    success: bool
    error: Optional[str] = None

    @classmethod
    def ok(cls) -> StageResult:
        """Return a successful StageResult with no error message."""
        return cls(success=True)

    @classmethod
    def fail(cls, error: str) -> StageResult:
        """Return a failed StageResult with a descriptive error message.

        Args:
            error: Human-readable description of why the stage failed.

        Returns:
            A StageResult with ``success=False`` and the supplied error string.
        """
        return cls(success=False, error=error)


class Stage(Protocol):
    """Protocol for pipeline stages."""
    name: str

    def execute(self, ctx: BuildContext) -> StageResult:
        """Execute the stage. Returns StageResult."""
        ...


class BuildPipeline:
    """Executes a sequence of stages to process a build job.

    If any stage fails, the pipeline stops, reports the error, and
    cleans up the workspace.
    """

    def __init__(self, stages: List[Stage], client: ConcordClient):
        self.stages = stages
        self.client = client

    def execute(self, ctx: BuildContext) -> bool:
        """Run all stages in order. Returns True if build succeeded."""
        start_time = time.time()

        log.info("=" * 60)
        log.info("Processing job %s: %s/%s (%s)",
                 ctx.job.id[:8], ctx.job.product, ctx.job.variant, ctx.job.branch)

        try:
            # Prepare workspace
            if ctx.work_dir.exists():
                shutil.rmtree(ctx.work_dir)
            ctx.work_dir.mkdir(parents=True)
            ctx.output_dir.mkdir(parents=True)

            # Fetch webhook data once for all stages
            try:
                result = self.client.api_get(f"/v2/builds/{ctx.job.id}")
                if result and result.get("data"):
                    ctx.webhook_data = result["data"].get("webhookData") or {}
            except Exception:
                pass

            # Execute stages
            for i, stage in enumerate(self.stages):
                log.info("[%s] Starting %s...", ctx.job.id[:8], stage.name)
                pct = int((i / len(self.stages)) * 100) if self.stages else 0
                self.client.report_progress(ctx.job.id, step=stage.name, progress=pct,
                                            message=f"Starting {stage.name}...")
                result = stage.execute(ctx)

                if not result.success:
                    duration = int(time.time() - start_time)
                    log.error("[%s] Stage '%s' failed: %s",
                              ctx.job.id[:8], stage.name, result.error)
                    self._report_failure(ctx, result.error, duration)
                    return False

            # All stages passed
            duration = int(time.time() - start_time)
            self._report_success(ctx, duration)
            log.info("Build %s completed in %ds", ctx.job.id[:8], duration)
            return True

        except Exception as e:
            log.exception("Unexpected error processing job %s", ctx.job.id[:8])
            self._report_failure(ctx, str(e), int(time.time() - start_time))
            return False

        finally:
            try:
                if ctx.work_dir.exists():
                    shutil.rmtree(ctx.work_dir)
            except Exception:
                pass

    def _report_failure(self, ctx: BuildContext, error: str, duration: int):
        """Report build failure to the API."""
        error_summary = error[-4000:] if len(error) > 4000 else error
        data: Dict[str, Any] = {
            "status": "FAILED",
            "errorMessage": error_summary[:2000],
            "finishedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "durationSeconds": duration,
        }
        self.client.api_patch(f"/v2/builds/{ctx.job.id}", data)

        # Upload build log if available
        log_file = ctx.output_dir / "build.log"
        if ctx.log_output:
            try:
                log_file.write_text(ctx.log_output)
                self.client.upload_file(
                    f"/v2/builds/{ctx.job.id}/artifacts", log_file, "build.log")
            except Exception:
                pass

    def _report_success(self, ctx: BuildContext, duration: int):
        """Report build success to the API."""
        data: Dict[str, Any] = {
            "status": "SUCCESS",
            "finishedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "durationSeconds": duration,
        }
        if ctx.version_string:
            data["versionString"] = ctx.version_string
        self.client.api_patch(f"/v2/builds/{ctx.job.id}", data)
