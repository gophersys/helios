"""Tests for services/build_trigger.py — trigger_stage_build and helpers."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from tests.conftest import make_obj
from src.services.build_trigger import (
    _extract_trigger_context,
    _resolve_recipe_version,
    trigger_stage_build,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now():
    return datetime(2026, 1, 1, tzinfo=timezone.utc)


def _product(**overrides):
    defaults = dict(
        id="prod-1",
        name="Alpha B0",
        slug="alpha-b0",
        fwRepoSlug="alpha_fw",
        mfgFwRepoSlug="alpha_mfg_fw",
        builderImage=None,
        boards=[],
    )
    defaults.update(overrides)
    return make_obj(**defaults)


def _stage_config(**overrides):
    defaults = dict(
        id="sc-1",
        productId="prod-1",
        stage=5,
        name="FUOTA",
        watchBranch="main",
        boardRevisionId="rev-1",
        boardRevision=make_obj(id="rev-1", version="B0", ckBoardsName="alpha_b0"),
        signingKey=None,
        signingKeyId=None,
        recipeVersionId=None,
    )
    defaults.update(overrides)
    return make_obj(**defaults)


# ---------------------------------------------------------------------------
# TestExtractTriggerContext
# ---------------------------------------------------------------------------

class TestExtractTriggerContext:
    """Tests for _extract_trigger_context() helper."""

    def test_manual_trigger_when_no_metadata(self):
        """No metadata produces manual trigger type."""
        ctx = _extract_trigger_context(None, "main")
        assert ctx["trigger_type"] == "manual"
        assert ctx["commit_sha"] is None

    def test_pr_trigger_when_pr_id_present(self):
        """Metadata with pr_id produces pr_push trigger type."""
        metadata = {
            "pr_id": 42,
            "pr_title": "Fix thing",
            "pr_author": "mateo",
            "source_branch": "feature/x",
            "target_branch": "main",
            "pr_url": "https://bitbucket.org/pr/42",
            "source_commit": "deadbeef",
        }
        ctx = _extract_trigger_context(metadata, "main")
        assert ctx["trigger_type"] == "pr_push"
        assert ctx["pr_number"] == 42
        assert ctx["pr_title"] == "Fix thing"
        assert ctx["commit_sha"] == "deadbeef"
        assert ctx["source_branch"] == "feature/x"

    def test_auto_trigger_from_auto_progress(self):
        """source=auto_progress produces auto trigger type."""
        ctx = _extract_trigger_context({"source": "auto_progress"}, "main")
        assert ctx["trigger_type"] == "auto"

    def test_schedule_trigger(self):
        """source=schedule produces schedule trigger type."""
        ctx = _extract_trigger_context({"source": "schedule"}, "main")
        assert ctx["trigger_type"] == "schedule"

    def test_branch_defaults_to_provided_value(self):
        """Branch defaults to the passed default_branch when no override in metadata."""
        ctx = _extract_trigger_context({}, "develop")
        assert ctx["branch"] == "develop"

    @pytest.mark.parametrize("source", ["webhook", "poller"])
    def test_webhook_poller_produce_pr_push(self, source):
        """source=webhook or poller produce pr_push trigger type."""
        ctx = _extract_trigger_context({"source": source}, "main")
        assert ctx["trigger_type"] == "pr_push"


# ---------------------------------------------------------------------------
# TestResolveRecipeVersion
# ---------------------------------------------------------------------------

class TestResolveRecipeVersion:
    """Tests for _resolve_recipe_version()."""

    def test_returns_pinned_recipe_version(self):
        """Returns stage config's recipeVersionId when pinned."""
        db = MagicMock()
        stage_config = make_obj(recipeVersionId="rv-pinned")

        result = _resolve_recipe_version(db, "prod-1", stage_config)

        assert result == "rv-pinned"
        db.recipeversion.find_first.assert_not_called()

    def test_returns_latest_published_recipe(self):
        """Returns latest published recipe when no pinned version."""
        db = MagicMock()
        stage_config = make_obj(recipeVersionId=None)
        latest = make_obj(id="rv-latest", version=3, status="published")
        db.recipeversion.find_first.return_value = latest

        result = _resolve_recipe_version(db, "prod-1", stage_config)

        assert result == "rv-latest"

    def test_returns_none_when_no_recipe_exists(self):
        """Returns None when no published recipe found."""
        db = MagicMock()
        stage_config = make_obj(recipeVersionId=None)
        db.recipeversion.find_first.return_value = None

        result = _resolve_recipe_version(db, "prod-1", stage_config)

        assert result is None


# ---------------------------------------------------------------------------
# TestTriggerStageBuild
# ---------------------------------------------------------------------------

class TestTriggerStageBuild:
    """Tests for trigger_stage_build() — integration of DB + build run creation."""

    @patch("src.services.build_trigger.get_db_client")
    def test_returns_none_when_product_not_found(self, mock_get_db):
        """Returns None when product_id references no product."""
        db = MagicMock()
        mock_get_db.return_value = db
        db.product.find_unique.return_value = None

        result = trigger_stage_build("bad-product-id", "sc-1")

        assert result is None

    @patch("src.services.build_trigger.get_db_client")
    def test_returns_none_when_stage_config_not_found(self, mock_get_db):
        """Returns None when stage_config_id references no stage config."""
        db = MagicMock()
        mock_get_db.return_value = db
        db.product.find_unique.return_value = _product()
        db.productstageconfig.find_unique.return_value = None

        result = trigger_stage_build("prod-1", "bad-sc-id")

        assert result is None

    @patch("src.services.build_trigger.get_db_client")
    def test_returns_none_when_stage_config_has_no_revision(self, mock_get_db):
        """Returns None when stage config lacks a board revision."""
        db = MagicMock()
        mock_get_db.return_value = db
        db.product.find_unique.return_value = _product()
        db.productstageconfig.find_unique.return_value = make_obj(
            id="sc-1", stage=5, name="FUOTA",
            watchBranch="main",
            boardRevisionId=None,
            boardRevision=None,
            signingKey=None,
            recipeVersionId=None,
        )

        result = trigger_stage_build("prod-1", "sc-1")

        assert result is None

    @patch("src.services.build_trigger.get_db_client")
    def test_returns_none_when_product_has_no_fw_repo(self, mock_get_db):
        """Returns None when product has no fwRepoSlug."""
        db = MagicMock()
        mock_get_db.return_value = db
        db.product.find_unique.return_value = _product(fwRepoSlug=None)
        db.productstageconfig.find_unique.return_value = _stage_config()
        db.stagebuildmatrix.find_many.return_value = []

        from corekinect.stages import StageBuildDef, Stage
        with patch("src.services.build_trigger.get_stage_build_defs", return_value=[
            StageBuildDef(label="MFG_APP_DEBUG", fw_type="app", variant="debug")
        ]):
            result = trigger_stage_build("prod-1", "sc-1")

        assert result is None

    @patch("src.services.build_trigger.get_db_client")
    def test_deduplicates_active_run_for_same_commit(self, mock_get_db):
        """Returns existing BuildRun ID when same commit already in progress."""
        db = MagicMock()
        mock_get_db.return_value = db
        db.product.find_unique.return_value = _product()
        db.productstageconfig.find_unique.return_value = _stage_config()
        db.stagebuildmatrix.find_many.return_value = []
        db.recipeversion.find_first.return_value = None

        existing_run = make_obj(id="run-existing", status="BUILDING")
        db.buildrun.find_first.return_value = existing_run

        from corekinect.stages import StageBuildDef
        with patch("src.services.build_trigger.get_stage_build_defs", return_value=[
            StageBuildDef(label="PROD_VERBOSE", fw_type="app", variant="release")
        ]):
            result = trigger_stage_build(
                "prod-1", "sc-1",
                event_metadata={"source_commit": "abc1234", "pr_id": 7, "source_branch": "feat/x"},
            )

        assert result is not None
        assert result.get("buildRunId") == "run-existing"
        assert result.get("deduplicated") is True

    @patch("src.services.build_trigger.get_db_client")
    def test_creates_build_run_on_success(self, mock_get_db):
        """Creates BuildRun and jobs when all inputs valid."""
        db = MagicMock()
        mock_get_db.return_value = db

        product = _product()
        stage_cfg = _stage_config()
        db.product.find_unique.return_value = product
        db.productstageconfig.find_unique.return_value = stage_cfg
        db.stagebuildmatrix.find_many.return_value = []
        db.recipeversion.find_first.return_value = None
        db.buildrun.find_first.return_value = None  # no dedup match

        build_run = make_obj(
            id="run-new", name="alpha-main-abc1234", status="BUILDING",
            startedAt=_now(), finishedAt=None,
            createdAt=_now(), updatedAt=_now(),
        )
        db.buildrun.create.return_value = build_run

        # Each job create returns a mock
        db.buildjob.create.return_value = make_obj(id="job-1", matrixLabel="PROD_VERBOSE")
        db.buildjob.find_first.return_value = None  # no cached build

        from corekinect.stages import StageBuildDef

        with patch("src.services.build_trigger.get_stage_build_defs", return_value=[
            StageBuildDef(label="PROD_VERBOSE", fw_type="app", variant="release"),
        ]):
            with patch("src.api.v2.builds.build_cache.compute_build_fingerprint", return_value="fp-1"):
                with patch("src.api.v2.builds.build_cache.find_cached_build", return_value=None):
                    with patch("src.services.build_trigger.log_audit"):
                        result = trigger_stage_build("prod-1", "sc-1")

        assert result is not None
        assert result["buildRunId"] == "run-new"
        assert result["jobCount"] == 1

    # TODO: test_cancel_stale_runs_called_for_pr_pushes
    # TODO: test_trigger_uses_db_matrix_when_entries_exist
    # TODO: test_trigger_uses_mfg_repo_for_mfg_fw_type
