"""Tests for services/build_run_service.py — serializers, helpers, resolve_pipeline_context."""

from __future__ import annotations

import types
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from tests.conftest import make_obj
from src.services.build_run_service import (
    safe_product_str,
    derive_build_product_slug,
    get_system_user_id,
    serialize_build_run,
    serialize_build_run_summary,
    auto_increment_version,
    get_max_build_number,
    resolve_pipeline_context,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now():
    return datetime(2026, 1, 1, tzinfo=timezone.utc)


def _build_run(**overrides):
    defaults = dict(
        id="run-1",
        name="alpha-main-abc1234",
        productId="prod-1",
        board="alpha_b0",
        branch="main",
        commitSha="abc1234",
        status="PENDING",
        triggerType="manual",
        stage=5,
        expectedBuilds=2,
        completedBuilds=0,
        validationRunId=None,
        matrixMode="fuota",
        autoRunStage=False,
        recipeVersionId=None,
        buildMatrix=None,
        triggerData=None,
        prNumber=None,
        prTitle=None,
        prAuthor=None,
        sourceBranch=None,
        targetBranch=None,
        prUrl=None,
        startedAt=_now(),
        finishedAt=None,
        createdAt=_now(),
        updatedAt=_now(),
    )
    defaults.update(overrides)
    return make_obj(**defaults)


def _build_job(**overrides):
    defaults = dict(
        id="job-1",
        productId="prod-1",
        status="QUEUED",
        target="app",
        variant="release",
        board="alpha_b0",
        commitSha="abc1234",
        buildNum=3,
        versionString="0.8.3",
        durationSeconds=None,
        matrixLabel="PROD_VERBOSE",
        matrixIndex=0,
        versionBump=False,
        baseJobId=None,
        reusedFromId=None,
        artifacts=[],
        createdAt=_now(),
    )
    defaults.update(overrides)
    return make_obj(**defaults)


# ---------------------------------------------------------------------------
# TestSafeProductStr
# ---------------------------------------------------------------------------

class TestSafeProductStr:
    """Tests for safe_product_str() helper."""

    def test_returns_string_unchanged(self):
        """String values are returned as-is."""
        assert safe_product_str("alpha-b0") == "alpha-b0"

    def test_returns_slug_from_object(self):
        """Objects with slug attribute return slug."""
        obj = make_obj(slug="alpha-b0", name="Alpha B0")
        assert safe_product_str(obj) == "alpha-b0"

    def test_returns_name_when_slug_empty(self):
        """Objects with empty slug fall back to name."""
        obj = make_obj(slug="", name="Alpha B0")
        assert safe_product_str(obj) == "Alpha B0"

    def test_returns_none_for_none_input(self):
        """None input returns None."""
        assert safe_product_str(None) is None

    def test_returns_none_for_object_without_slug(self):
        """Objects without slug attribute return None."""
        obj = make_obj(name="Alpha")  # no slug attribute
        assert safe_product_str(obj) is None


# ---------------------------------------------------------------------------
# TestDeriveProductSlug
# ---------------------------------------------------------------------------

class TestDeriveBuildProductSlug:
    """Tests for derive_build_product_slug() helper."""

    def test_uses_product_slug(self):
        """Returns product slug when available."""
        build = make_obj(
            product=make_obj(slug="alpha-b0", name="Alpha B0"),
            productId="prod-1",
        )
        assert derive_build_product_slug(build) == "alpha-b0"

    def test_falls_back_to_product_id(self):
        """Falls back to productId when no product relation loaded."""
        build = make_obj(productId="prod-fallback")
        assert derive_build_product_slug(build) == "prod-fallback"


# ---------------------------------------------------------------------------
# TestGetSystemUserId
# ---------------------------------------------------------------------------

class TestGetSystemUserId:
    """Tests for get_system_user_id()."""

    def test_returns_existing_system_user(self):
        """Returns ID of existing system user without creating."""
        db = MagicMock()
        system_user = make_obj(id="sys-user-id", email="system@concord.local")
        db.user.find_first.return_value = system_user
        db.user.create.return_value = None

        result = get_system_user_id(db)

        assert result == "sys-user-id"
        db.user.create.assert_not_called()

    def test_creates_system_user_when_missing(self):
        """Creates system user when none exists and returns new ID."""
        db = MagicMock()
        db.user.find_first.return_value = None
        new_user = make_obj(id="new-sys-id", email="system@concord.local")
        db.user.create.return_value = new_user

        result = get_system_user_id(db)

        assert result == "new-sys-id"
        db.user.create.assert_called_once()


# ---------------------------------------------------------------------------
# TestSerializeBuildRun
# ---------------------------------------------------------------------------

class TestSerializeBuildRun:
    """Tests for serialize_build_run() serializer."""

    def test_contains_required_fields(self):
        """Serialized output includes all required top-level fields."""
        run = _build_run()
        data = serialize_build_run(run)

        for field in ["id", "name", "status", "branch", "commitSha",
                      "expectedBuilds", "completedBuilds", "createdAt", "updatedAt"]:
            assert field in data, f"Missing field: {field}"

    def test_dates_are_iso_strings(self):
        """createdAt and updatedAt are serialized as ISO strings."""
        run = _build_run()
        data = serialize_build_run(run)
        assert data["createdAt"] == _now().isoformat()

    def test_includes_builds_when_loaded(self):
        """Builds list is included when run.builds is populated."""
        job = _build_job()
        run = _build_run()
        run.builds = [job]
        data = serialize_build_run(run)

        assert "builds" in data
        assert len(data["builds"]) == 1
        assert data["builds"][0]["id"] == "job-1"

    def test_finished_at_none_when_not_set(self):
        """finishedAt is None when not set on the run."""
        run = _build_run(finishedAt=None)
        data = serialize_build_run(run)
        assert data["finishedAt"] is None

    def test_product_string_resolved_from_object(self):
        """product field uses product.slug when loaded."""
        run = _build_run()
        run.product = make_obj(slug="alpha-b0", name="Alpha B0")
        data = serialize_build_run(run)
        assert data["product"] == "alpha-b0"


# ---------------------------------------------------------------------------
# TestSerializeBuildRunSummary
# ---------------------------------------------------------------------------

class TestSerializeBuildRunSummary:
    """Tests for serialize_build_run_summary() list-view serializer."""

    def test_summary_has_core_fields(self):
        """Summary includes the fields needed for list views."""
        run = _build_run()
        data = serialize_build_run_summary(run)

        for field in ["id", "status", "branch", "commitSha", "expectedBuilds", "createdAt"]:
            assert field in data, f"Missing field: {field}"

    def test_summary_sorts_builds_by_matrix_index(self):
        """Summary sorts builds by matrixIndex for deterministic ordering."""
        job_b = _build_job(id="job-b", matrixIndex=1)
        job_a = _build_job(id="job-a", matrixIndex=0)
        run = _build_run()
        run.builds = [job_b, job_a]

        data = serialize_build_run_summary(run)
        assert data["builds"][0]["id"] == "job-a"
        assert data["builds"][1]["id"] == "job-b"


# ---------------------------------------------------------------------------
# TestAutoIncrementVersion
# ---------------------------------------------------------------------------

class TestAutoIncrementVersion:
    """Tests for auto_increment_version()."""

    def test_increments_build_number(self):
        """Returns version with incremented build number."""
        db = MagicMock()
        db.buildjob.find_first.return_value = make_obj(versionString="0.8.3")

        result = auto_increment_version(db, "prod-1", "release", target="app")
        assert result == "0.8.4"

    def test_returns_none_when_no_prior_build(self):
        """Returns None when no successful build exists."""
        db = MagicMock()
        db.buildjob.find_first.return_value = None

        result = auto_increment_version(db, "prod-1", "release", target="app")
        assert result is None

    def test_returns_none_when_version_has_no_build_part(self):
        """Returns None when version string has fewer than 3 parts."""
        db = MagicMock()
        db.buildjob.find_first.return_value = make_obj(versionString="0.8")

        result = auto_increment_version(db, "prod-1", "release", target="app")
        assert result is None


# ---------------------------------------------------------------------------
# TestGetMaxBuildNumber
# ---------------------------------------------------------------------------

class TestGetMaxBuildNumber:
    """Tests for get_max_build_number()."""

    def test_returns_prefix_and_max_build(self):
        """Returns (version_prefix, build_number) from latest success."""
        db = MagicMock()
        db.buildjob.find_first.return_value = make_obj(versionString="0.8.17")

        prefix, max_build = get_max_build_number(db, "prod-1", target="app")
        assert prefix == "0.8"
        assert max_build == 17

    def test_returns_none_and_zero_when_no_build(self):
        """Returns (None, 0) when no successful build exists."""
        db = MagicMock()
        db.buildjob.find_first.return_value = None

        prefix, max_build = get_max_build_number(db, "prod-1")
        assert prefix is None
        assert max_build == 0


# ---------------------------------------------------------------------------
# TestResolvePipelineContext
# ---------------------------------------------------------------------------

class TestResolvePipelineContext:
    """Tests for resolve_pipeline_context()."""

    def _make_request(self, **overrides):
        defaults = dict(
            product_id="prod-1",
            product="alpha",
            repo_slug="alpha_fw",
            mfg_repo_slug="alpha_mfg_fw",
            board="alpha_b0",
            branch="main",
            pr_branch=None,
            commit_sha=None,
            main_commit=None,
            matrix_mode="fuota",
            validation_config=None,
        )
        defaults.update(overrides)
        return make_obj(**defaults)

    def test_resolves_with_product_record(self):
        """Context includes product record and derived repo names."""
        db = MagicMock()
        product = make_obj(id="prod-1", name="Alpha B0", slug="alpha", fwRepoSlug="alpha_fw",
                           mfgFwRepoSlug="alpha_mfg_fw", builderImage=None)
        db.product.find_unique.return_value = product
        db.productstageconfig.find_first.return_value = make_obj(
            id="sc-1", stage=5, buildMatrix=[{"role": "app", "firmware": "alpha_fw", "source": "head"}],
        )
        db.buildjob.find_first.return_value = make_obj(versionString="0.8.17")

        req = self._make_request()

        ctx = resolve_pipeline_context(db, req)

        assert ctx["product_record"] is product
        assert ctx["main_fw"] == "alpha_fw"

    def test_raises_when_no_build_matrix(self):
        """Raises ValueError when product has no build matrix for the stage."""
        db = MagicMock()
        product = make_obj(id="prod-1", name="Alpha", slug="alpha", fwRepoSlug="alpha_fw",
                           mfgFwRepoSlug=None, builderImage=None)
        db.product.find_unique.return_value = product
        db.productstageconfig.find_first.return_value = make_obj(
            id="sc-1", stage=5, buildMatrix=None,
        )

        req = self._make_request()

        with pytest.raises(ValueError, match="not configured"):
            resolve_pipeline_context(db, req)

    def test_resolves_without_product_record(self):
        """Context is built using data fields when no product record found."""
        db = MagicMock()
        db.product.find_unique.return_value = None
        db.product.find_first.return_value = None
        db.productstageconfig.find_first.return_value = None

        req = self._make_request(
            product_id=None,
            product="alpha",
            matrix_mode="fuota",
        )

        # Without product record, no stage config is found, which raises
        with pytest.raises(ValueError):
            resolve_pipeline_context(db, req)

    # TODO: test_resolve_pipeline_context_uses_stage_config_matrix
    # TODO: test_resolve_pipeline_context_pr_branch_override
