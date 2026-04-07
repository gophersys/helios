"""BuildStage — resolves builder image and executes the build.

Handles devcontainer.json parsing, Docker container spawning,
build script execution, and real-time log streaming.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, Optional

from src.worker.executor import BuildExecutor
from src.worker.git_ops import GitOps
from src.worker.pipeline import BuildContext, StageResult

log = logging.getLogger("build-service")


class BuildStage:
    """Resolve builder image, fetch product targets, execute build."""

    name = "build"

    def execute(self, ctx: BuildContext) -> StageResult:
        # 1. Fetch product targets for SDK env vars
        self._fetch_product_targets(ctx)

        # 2. Resolve builder image from devcontainer.json
        if ctx.docker_runner:
            image = self._resolve_builder_image(ctx)
            if not image:
                return StageResult.fail("No builder image available")

            if not ctx.docker_runner.ensure_image(image):
                return StageResult.fail(f"Failed to pull builder image: {image}")

            ctx.builder_image = image

            # Store builder info in config_flags for UI
            if not ctx.job.config_flags:
                ctx.job.config_flags = {}
            ctx.job.config_flags["_builder_image"] = image
            ctx.job.config_flags["_primary_slug"] = ctx.primary_slug
            ctx.client.api_patch(f"/v2/builds/{ctx.job.id}", {
                "configFlags": ctx.job.config_flags,
            })
            log.info("Builder image: %s", image)

        # 3. Update status to BUILDING
        ctx.client.api_patch(f"/v2/builds/{ctx.job.id}", {"status": "BUILDING"})

        # 4. Execute build
        executor = BuildExecutor(ctx.client)
        success, log_output = executor.run_build(
            ctx.job, ctx.work_dir, ctx.output_dir,
            docker_runner=ctx.docker_runner,
            builder_image=ctx.builder_image,
        )
        ctx.log_output = log_output or ""

        # Write build log
        log_file = ctx.output_dir / "build.log"
        if ctx.log_output:
            log_file.write_text(ctx.log_output)
            log.info("Build output: %d lines, %d chars",
                     ctx.log_output.count('\n'), len(ctx.log_output))
            for line in ctx.log_output.strip().split('\n')[-20:]:
                log.info("  | %s", line)

        if not success:
            return StageResult.fail(ctx.log_output[-4000:] if len(ctx.log_output) > 4000 else ctx.log_output)

        # 5. Extract version from build output
        ctx.version_string = self._extract_version(ctx.log_output)

        return StageResult.ok()

    def _fetch_product_targets(self, ctx: BuildContext):
        """Fetch product target metadata for SDK env vars."""
        product_id = ctx.job.product_id or ctx.webhook_data.get("productId")
        if not product_id:
            return

        prod_result = ctx.client.api_get(f"/v2/products/{product_id}")
        if not prod_result or not prod_result.get("data"):
            return

        prod_data = prod_result["data"]
        ctx.build_config = prod_data.get("buildConfig")

        # Extract targets matching this job's board
        targets = []
        for board in (prod_data.get("boards") or []):
            for rev in (board.get("revisions") or []):
                if rev.get("ckBoardsName") == ctx.job.board:
                    for t in (rev.get("targets") or []):
                        targets.append({
                            "role": t.get("role", ""),
                            "appId": t.get("appId", 0),
                            "processor": t.get("processor") or t.get("soc", ""),
                        })

        targets_json = json.dumps(targets) if targets else "[]"
        if targets:
            log.info("Product targets for %s: %s", ctx.job.board, targets_json)
        else:
            log.warning("No targets found for board %s", ctx.job.board)

        if not ctx.job.config_flags:
            ctx.job.config_flags = {}
        ctx.job.config_flags["_targets_json"] = targets_json

    def _resolve_builder_image(self, ctx: BuildContext) -> Optional[str]:
        """Resolve the Docker builder image from devcontainer.json or default."""
        if ctx.primary_dir:
            image = GitOps.get_builder_image(ctx.primary_dir)
            if image:
                return image
        return ctx.config.default_builder_image

    def _extract_version(self, log_output: str) -> Optional[str]:
        """Extract firmware version from build script output."""
        if not log_output:
            return None

        # Prefer explicit "Resolved version:" marker from SDK
        match = re.search(r"Resolved version:\s*(\d+\.\d+\.\d+)", log_output)
        if match:
            return match.group(1)

        # Fallback: last X.Y.Z occurrence in output
        all_versions = re.findall(r"(\d+\.\d+\.\d+)", log_output)
        return all_versions[-1] if all_versions else None
