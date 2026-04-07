"""RecipeStage — resolves the build recipe (build.sh script).

Priority order:
  1. Pinned recipe version (by recipeVersionId)
  2. Stage-specific recipe from API
  3. Repo's own build script (scripts/build.sh, build_all.sh, build.sh)
"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

from src.worker.pipeline import BuildContext, StageResult

log = logging.getLogger("build-service")


class RecipeStage:
    """Resolve and prepare the build recipe."""

    name = "recipe"

    def execute(self, ctx: BuildContext) -> StageResult:
        scripts_dir = ctx.work_dir / "scripts"
        scripts_dir.mkdir(parents=True, exist_ok=True)
        recipe_path = scripts_dir / "build.sh"

        product_id = ctx.job.product_id or ctx.webhook_data.get("productId")

        # 1. Try pinned recipe version
        if ctx.job.recipe_version_id and product_id:
            content = self._fetch_pinned_recipe(ctx, product_id)
            if content:
                recipe_path.write_text(content)
                recipe_path.chmod(0o755)
                ctx.recipe_path = recipe_path
                log.info("Build recipe loaded from pinned version %s",
                         ctx.job.recipe_version_id)
                self._patch_sdk_path(ctx, recipe_path)
                return StageResult.ok()

        # 2. Try stage-specific recipe from API
        if ctx.job.stage and product_id:
            content = self._fetch_stage_recipe(ctx, product_id)
            if content:
                recipe_path.write_text(content)
                recipe_path.chmod(0o755)
                ctx.recipe_path = recipe_path
                log.info("Build recipe loaded from API (stage %s)", ctx.job.stage)
                self._patch_sdk_path(ctx, recipe_path)
                return StageResult.ok()

        # 3. Fall back to repo's own build script
        if ctx.primary_dir:
            for candidate in [
                ctx.primary_dir / "scripts" / "build.sh",
                ctx.primary_dir / "build_all.sh",
                ctx.primary_dir / "build.sh",
            ]:
                if candidate.exists():
                    shutil.copy2(candidate, recipe_path)
                    recipe_path.chmod(0o755)
                    ctx.recipe_path = recipe_path
                    log.info("Using repo build script: %s", candidate.name)
                    self._patch_sdk_path(ctx, recipe_path)
                    return StageResult.ok()

        return StageResult.fail(
            "No build recipe found — upload one via Products → Build Config")

    def _fetch_pinned_recipe(self, ctx: BuildContext, product_id: str) -> str | None:
        """Fetch a specific recipe version from the API."""
        result = ctx.client.api_get(
            f"/v2/products/{product_id}/recipe/versions/by-id/{ctx.job.recipe_version_id}")
        if result and result.get("data"):
            return result["data"].get("content")
        return None

    def _fetch_stage_recipe(self, ctx: BuildContext, product_id: str) -> str | None:
        """Fetch the recipe for a specific stage from the API."""
        result = ctx.client.api_get(
            f"/v2/products/{product_id}/recipe?stage={ctx.job.stage}")
        if result and result.get("data"):
            return result["data"].get("content")
        return None

    def _patch_sdk_path(self, ctx: BuildContext, recipe_path: Path):
        """Update SDK source path in recipe for DinD workspace-relative access."""
        sdk_dest = ctx.work_dir / "sdk"
        if sdk_dest.is_dir() and recipe_path.exists():
            content = recipe_path.read_text()
            content = content.replace(
                "source /app/sdk/concord-build.sh",
                f"source /workspace/{ctx.job.id}/sdk/concord-build.sh",
            )
            recipe_path.write_text(content)
