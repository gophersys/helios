"""CloneStage — clones primary and secondary firmware repos.

Extracts repo resolution, git cloning, NCS detection, overlay fetching,
and SDK copying from the monolithic process_job method.
"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from src.worker.pipeline import BuildContext, StageResult

log = logging.getLogger("build-service")

# SDK source directory (copied into workspace for DinD builds)
SDK_SOURCE = Path("/app/sdk")


class CloneStage:
    """Clone primary + secondary repos, fetch overlays, copy SDK."""

    name = "clone"

    def execute(self, ctx: BuildContext) -> StageResult:
        """Clone firmware repositories and prepare the workspace.

        Execution order:
        1. Resolve primary and secondary repo slugs from job and webhook data.
        2. Fetch optional build overlays from the API (non-fatal).
        3. Clone the primary repo; fail the stage if this clone fails.
        4. Detect the NCS version from devcontainer.json (informational).
        5. Clone the secondary repo (non-fatal if unavailable).
        6. Copy the Concord Build SDK into the workspace for DinD access.

        Args:
            ctx: Mutable build context shared across all pipeline stages.

        Returns:
            StageResult.ok() on success, or StageResult.fail(msg) if the
            primary repository clone fails.
        """
        primary, secondary = self._resolve_repos(ctx)

        # 1. Fetch overlays (optional, non-fatal)
        self._fetch_overlays(ctx)

        # 2. Clone PRIMARY repo
        ctx.primary_slug = primary["slug"]
        ctx.primary_dir = ctx.work_dir / primary["slug"]
        log.info("Cloning PRIMARY %s (branch=%s, commit=%s)...",
                 primary["slug"], primary["branch"],
                 (primary["commit"] or "latest")[:8])
        ctx.client.heartbeat(ctx.job.id)

        if not self._clone_repo(
            primary["slug"], ctx.primary_dir, primary["commit"],
            primary["branch"], ctx.client, ctx.job.id
        ):
            return StageResult.fail(
                f"Failed to clone {primary['slug']} (branch={primary['branch']})")

        # 2.5. NCS version detection (informational)
        ncs_version = self._detect_ncs_version(ctx.primary_dir)
        if ncs_version:
            log.info("Detected NCS version: %s", ncs_version)

        # 3. Clone SECONDARY repo (non-fatal)
        ctx.secondary_slug = secondary["slug"]
        ctx.secondary_dir = ctx.work_dir / secondary["slug"]
        log.info("Cloning SECONDARY %s (branch=%s)...",
                 secondary["slug"], secondary["branch"])
        ctx.client.heartbeat(ctx.job.id)

        if not self._clone_repo(
            secondary["slug"], ctx.secondary_dir, secondary["commit"],
            secondary["branch"], ctx.client, ctx.job.id
        ):
            log.warning("Failed to clone %s — secondary repo unavailable",
                        secondary["slug"])

        # 4. Copy SDK into workspace (needed for DinD)
        self._copy_sdk(ctx)

        return StageResult.ok()

    def _resolve_repos(self, ctx: BuildContext) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """Determine primary and secondary repos from the job + webhook data."""
        job = ctx.job
        wd = ctx.webhook_data

        fw_slug = wd.get("fwRepoSlug") or f"{job.product.lower()}_fw"
        mfg_slug = wd.get("mfgRepoSlug") or f"{job.product.lower()}_mfg_fw"

        if job.target == "mfg":
            primary = {
                "slug": mfg_slug,
                "branch": "main",
                "commit": None,
            }
            secondary = {
                "slug": fw_slug,
                "branch": job.branch,
                "commit": job.commit_sha,
            }
        else:
            primary = {
                "slug": fw_slug,
                "branch": job.branch,
                "commit": job.commit_sha,
            }
            secondary = {
                "slug": mfg_slug,
                "branch": "main",
                "commit": None,
            }

        return primary, secondary

    def _clone_repo(self, slug: str, dest: Path, commit: Optional[str],
                    branch: str, client: Any, job_id: str) -> bool:
        """Clone a repo via GitOps. Delegated to allow mocking in tests."""
        from src.worker.git_ops import GitOps
        git_ops = GitOps(ssh_key_path="", api_client=client)
        return git_ops.clone_repo(slug, dest, commit, branch=branch, job_id=job_id)

    def _fetch_overlays(self, ctx: BuildContext):
        """Fetch optional build overlays from the API."""
        try:
            from src.worker.git_ops import GitOps
            git_ops = GitOps(ssh_key_path="", api_client=ctx.client)
            overlays_dir = ctx.work_dir / "overlays"
            git_ops.fetch_overlays(ctx.job.product, overlays_dir)
        except Exception as e:
            log.debug("No overlays available: %s", e)

    def _detect_ncs_version(self, repo_dir: Path) -> Optional[str]:
        """Detect NCS version from the repo's devcontainer.json."""
        try:
            from src.worker.docker_runner import DockerBuildRunner
            image = DockerBuildRunner.extract_builder_image(repo_dir)
            if not image:
                return None
            return DockerBuildRunner.extract_ncs_version(image)
        except Exception:
            return None

    def _copy_sdk(self, ctx: BuildContext):
        """Copy the Concord Build SDK into the workspace for DinD access."""
        sdk_dest = ctx.work_dir / "sdk"
        if SDK_SOURCE.is_dir() and not sdk_dest.exists():
            shutil.copytree(SDK_SOURCE, sdk_dest)
            log.info("Copied Concord Build SDK to workspace")

            # Update recipe references from /app/sdk → workspace-relative path
            # (done by RecipeStage after recipe is loaded)
