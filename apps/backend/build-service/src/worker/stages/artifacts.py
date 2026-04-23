"""ArtifactStage — collects, verifies, and uploads build artifacts.

Handles artifact collection (hex, cfw, build.json), manifest generation,
firmware validation, and multipart upload to MinIO via the API.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import List, Optional

from src.worker.executor import BuildExecutor
from src.worker.pipeline import BuildContext, StageResult

log = logging.getLogger("build-service")


class ArtifactStage:
    """Collect, verify, generate manifest, and upload build artifacts."""

    name = "artifacts"

    def execute(self, ctx: BuildContext) -> StageResult:
        """Collect, verify, and upload build artifacts.

        Execution order:
        1. Collect final hex/cfw/log files from the output directory.
        2. Fetch the product's buildConfig from the API (if not already cached).
        3. Generate a ``build.json`` manifest when target metadata is available.
        4. Validate artifact integrity via FirmwarePackageValidator.
        5. Upload all artifacts with structured metadata to the Concord API.

        Args:
            ctx: Mutable build context shared across all pipeline stages.

        Returns:
            StageResult.ok() on success, or StageResult.fail(msg) if artifact
            verification fails.
        """
        executor = BuildExecutor(ctx.client)

        # 1. Collect artifacts (final hex/cfw only)
        artifacts = executor.collect_artifacts(ctx.output_dir)
        log_file = ctx.output_dir / "build.log"
        if log_file.exists():
            artifacts.append(log_file)

        # 2. Fetch build config for manifest generation
        product_base = ctx.job.product.lower().replace("_fw", "").replace("_mfg", "")
        product_id = ctx.job.product_id or ctx.webhook_data.get("productId")

        if not ctx.build_config and product_id:
            product_data = ctx.client.get_product(product_id)
            if product_data:
                ctx.build_config = product_data.get("buildConfig")

        # 3. Generate build.json manifest
        if ctx.build_config and ctx.build_config.get("targets"):
            keys_dir = Path(f"/keys/{product_base}")
            manifest_path = executor.write_manifest(
                build_config=ctx.build_config,
                output_dir=ctx.output_dir,
                product=product_base,
                board=ctx.job.board,
                version=ctx.version_string or "0.0.0",
                variant=ctx.job.variant or "release",
                commit_sha=ctx.job.commit_sha,
                branch=ctx.job.branch,
                key_dir=keys_dir if keys_dir.is_dir() else None,
            )
            if manifest_path and manifest_path not in artifacts:
                artifacts.append(manifest_path)
        else:
            log.info("No buildConfig available — skipping manifest generation")

        # 4. Verify artifacts
        valid, verify_msg = executor.verify_artifacts(
            ctx.output_dir, ctx.job.version_override)
        if not valid:
            log.error("Artifact verification failed: %s", verify_msg)
            # Upload log for debugging even on verification failure
            if log_file.exists():
                ctx.client.upload_file(
                    f"/v2/builds/{ctx.job.id}/artifacts", log_file, "build.log")
            return StageResult.fail(f"Verification failed: {verify_msg}")

        # 5. Upload artifacts with metadata
        artifact_count = executor.upload_artifacts(
            ctx.job.id, artifacts, build_config=ctx.build_config)
        log.info("Uploaded %d artifacts", artifact_count)

        ctx.artifacts = artifacts
        return StageResult.ok()
