"""Tests for RecipeStage — build recipe resolution."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.worker.executor import BuildJob
from src.worker.pipeline import BuildContext
from src.worker.stages.recipe import RecipeStage


@pytest.fixture
def recipe_stage():
    return RecipeStage()


@pytest.fixture
def ctx(tmp_path, sample_job, config, mock_api_client):
    work_dir = tmp_path / "work"
    work_dir.mkdir()
    output_dir = work_dir / "artifacts"
    output_dir.mkdir()
    primary_dir = work_dir / "alpha_fw"
    primary_dir.mkdir()
    return BuildContext(
        job=sample_job,
        config=config,
        client=mock_api_client,
        work_dir=work_dir,
        output_dir=output_dir,
        primary_dir=primary_dir,
        primary_slug="alpha_fw",
    )


class TestRecipePriority:
    """Test recipe resolution priority order."""

    def test_pinned_recipe_takes_priority(self, ctx, recipe_stage, mock_api_client):
        """Pinned recipe version is used when available."""
        ctx.job.recipe_version_id = "rv-001"
        mock_api_client.api_get.return_value = {
            "data": {"content": "#!/bin/bash\necho pinned"}
        }

        result = recipe_stage.execute(ctx)

        assert result.success
        assert ctx.recipe_path.read_text().startswith("#!/bin/bash")
        assert "pinned" in ctx.recipe_path.read_text()

    def test_stage_recipe_when_no_pinned(self, ctx, recipe_stage, mock_api_client):
        """Stage recipe is used when no pinned version exists."""
        ctx.job.recipe_version_id = None
        ctx.job.stage = 3
        mock_api_client.api_get.return_value = {
            "data": {"content": "#!/bin/bash\necho stage3"}
        }

        result = recipe_stage.execute(ctx)

        assert result.success
        assert "stage3" in ctx.recipe_path.read_text()

    def test_repo_script_when_no_api_recipe(self, ctx, recipe_stage, mock_api_client):
        """Falls back to repo's build.sh when API has no recipe."""
        ctx.job.recipe_version_id = None
        ctx.job.stage = None
        mock_api_client.api_get.return_value = None

        scripts_dir = ctx.primary_dir / "scripts"
        scripts_dir.mkdir()
        (scripts_dir / "build.sh").write_text("#!/bin/bash\necho repo")

        result = recipe_stage.execute(ctx)

        assert result.success
        assert "repo" in ctx.recipe_path.read_text()

    def test_build_all_sh_fallback(self, ctx, recipe_stage, mock_api_client):
        """Falls back to build_all.sh when scripts/build.sh is missing."""
        ctx.job.recipe_version_id = None
        ctx.job.stage = None
        mock_api_client.api_get.return_value = None

        (ctx.primary_dir / "build_all.sh").write_text("#!/bin/bash\necho all")

        result = recipe_stage.execute(ctx)

        assert result.success
        assert "all" in ctx.recipe_path.read_text()

    def test_no_recipe_fails(self, ctx, recipe_stage, mock_api_client):
        """Fails when no recipe is found anywhere."""
        ctx.job.recipe_version_id = None
        ctx.job.stage = None
        mock_api_client.api_get.return_value = None

        result = recipe_stage.execute(ctx)

        assert not result.success
        assert "no build recipe" in result.error.lower()


class TestSDKPathPatching:
    """Test that SDK source paths are patched in recipes."""

    def test_sdk_path_patched(self, ctx, recipe_stage, mock_api_client):
        """Recipe SDK path is updated for DinD workspace."""
        ctx.job.recipe_version_id = "rv-001"
        mock_api_client.api_get.return_value = {
            "data": {"content": "#!/bin/bash\nsource /app/sdk/concord-build.sh\necho build"}
        }
        # Create SDK in workspace
        sdk_dir = ctx.work_dir / "sdk"
        sdk_dir.mkdir()

        result = recipe_stage.execute(ctx)

        assert result.success
        content = ctx.recipe_path.read_text()
        assert "/app/sdk/concord-build.sh" not in content
        assert f"/workspace/{ctx.job.id}/sdk/concord-build.sh" in content
