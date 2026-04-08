"""Extended tests for services/build_run_service.py — coverage for uncovered paths.

Targets: generate_matrix_build_specs, create_build_jobs, check_pipeline_completion,
_find_available_fixture, _analyze_unavailability, _queue_validation.
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch, call

import pytest

from tests.conftest import make_obj


def _now():
    return datetime(2026, 1, 1, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# generate_matrix_build_specs
# ---------------------------------------------------------------------------

class TestGenerateMatrixBuildSpecs:
    """Tests for generate_matrix_build_specs()."""

    def test_head_app_generates_four_sub_builds(self):
        """Head source app builds produce 4 sub-builds with sequential versions."""
        from src.services.build_run_service import generate_matrix_build_specs

        db = MagicMock()
        db.buildjob.find_first.return_value = make_obj(versionString="0.8.10")

        product = make_obj(id="prod-1")
        matrix = [{"role": "app", "firmware": "alpha_fw", "source": "head"}]

        specs = generate_matrix_build_specs(
            matrix=matrix,
            product_record=product,
            repo_base="alpha",
            board="alpha_b0",
            branch="main",
            commit_sha="abc123",
            db=db,
        )

        assert len(specs) == 4
        labels = [s["matrixLabel"] for s in specs]
        assert "PROD_VERBOSE" in labels
        assert "PROD_VERBOSE_BUMP" in labels
        assert "PROD_QUIET" in labels
        assert "PROD_QUIET_BUMP" in labels

        # Versions should be sequential from max+1
        versions = [s["versionOverride"] for s in specs]
        assert versions == ["0.8.11", "0.8.12", "0.8.13", "0.8.14"]

    def test_head_app_no_prefix_falls_through(self):
        """Head app build with no prior builds falls through to normal path."""
        from src.services.build_run_service import generate_matrix_build_specs

        db = MagicMock()
        db.buildjob.find_first.return_value = None  # No prior builds

        product = make_obj(id="prod-1")
        matrix = [{"role": "app", "firmware": "alpha_fw", "source": "head"}]

        specs = generate_matrix_build_specs(
            matrix=matrix,
            product_record=product,
            repo_base="alpha",
            board="alpha_b0",
            branch="main",
            commit_sha="abc123",
            db=db,
        )

        # Falls through to single variant path
        assert len(specs) == 1
        assert specs[0]["matrixLabel"] == "APP_RELEASE"

    def test_head_mfg_build(self):
        """Head source mfg builds use role as label."""
        from src.services.build_run_service import generate_matrix_build_specs

        db = MagicMock()
        db.buildjob.find_first.return_value = make_obj(versionString="0.5.3")

        product = make_obj(id="prod-1")
        matrix = [{"role": "comms_mfg", "firmware": "alpha_mfg_fw", "source": "head"}]

        specs = generate_matrix_build_specs(
            matrix=matrix,
            product_record=product,
            repo_base="alpha",
            board="alpha_b0",
            branch="main",
            commit_sha="abc123",
            db=db,
        )

        assert len(specs) == 1
        assert specs[0]["target"] == "mfg"
        assert specs[0]["matrixLabel"] == "COMMS_MFG"

    def test_latest_source_builds(self):
        """Latest source entries produce specs with source=latest."""
        from src.services.build_run_service import generate_matrix_build_specs

        db = MagicMock()
        product = make_obj(id="prod-1")
        matrix = [{"role": "app", "firmware": "alpha_fw", "source": "latest"}]

        specs = generate_matrix_build_specs(
            matrix=matrix,
            product_record=product,
            repo_base="alpha",
            board="alpha_b0",
            branch="main",
            commit_sha="abc123",
            db=db,
        )

        assert len(specs) == 1
        assert specs[0]["source"] == "latest"
        assert specs[0]["commitSha"] is None

    def test_latest_prev_source(self):
        """latest_prev source entries produce specs with source=latest_prev."""
        from src.services.build_run_service import generate_matrix_build_specs

        db = MagicMock()
        product = make_obj(id="prod-1")
        matrix = [{"role": "app", "firmware": "alpha_fw", "source": "latest_prev"}]

        specs = generate_matrix_build_specs(
            matrix=matrix,
            product_record=product,
            repo_base="alpha",
            board="alpha_b0",
            branch="main",
            commit_sha="abc123",
            db=db,
        )

        assert len(specs) == 1
        assert specs[0]["source"] == "latest_prev"

    def test_multiple_matrix_entries(self):
        """Multiple matrix entries produce indexed specs."""
        from src.services.build_run_service import generate_matrix_build_specs

        db = MagicMock()
        db.buildjob.find_first.return_value = None

        product = make_obj(id="prod-1")
        matrix = [
            {"role": "app", "firmware": "alpha_fw", "source": "latest"},
            {"role": "comms", "firmware": "alpha_mfg_fw", "source": "head"},
        ]

        specs = generate_matrix_build_specs(
            matrix=matrix,
            product_record=product,
            repo_base="alpha",
            board="alpha_b0",
            branch="main",
            commit_sha="abc123",
            db=db,
        )

        indices = [s["matrixIndex"] for s in specs]
        # All unique and sequential
        assert len(set(indices)) == len(indices)

    def test_no_product_record(self):
        """Works with product_record=None (no auto-versioning)."""
        from src.services.build_run_service import generate_matrix_build_specs

        db = MagicMock()
        matrix = [{"role": "app", "firmware": "alpha_fw", "source": "head"}]

        specs = generate_matrix_build_specs(
            matrix=matrix,
            product_record=None,
            repo_base="alpha",
            board="alpha_b0",
            branch="main",
            commit_sha="abc123",
            db=db,
        )

        assert len(specs) == 1
        assert specs[0].get("versionOverride") is None


# ---------------------------------------------------------------------------
# create_build_jobs
# ---------------------------------------------------------------------------

class TestCreateBuildJobs:
    """Tests for create_build_jobs()."""

    def test_creates_queued_builds(self):
        """Creates BuildJob records for head source specs."""
        from src.services.build_run_service import create_build_jobs

        db = MagicMock()
        build_obj = make_obj(id="build-1")
        db.buildjob.create.return_value = build_obj

        pipeline = make_obj(id="run-1")
        product = make_obj(id="prod-1")
        data = make_obj(branch="main", trigger_type="manual")

        specs = [{
            "board": "alpha_b0",
            "target": "app",
            "variant": "release",
            "branch": "main",
            "commitSha": "abc123",
            "status": "QUEUED",
            "matrixLabel": "APP_RELEASE",
            "matrixIndex": 0,
            "versionBump": False,
            "source": "head",
            "firmware": "alpha_fw",
        }]

        builds = create_build_jobs(db, pipeline, specs, data, product)

        assert len(builds) == 1
        db.buildjob.create.assert_called_once()

    def test_cached_latest_build(self):
        """Latest source specs that find a cache hit create CACHED status builds."""
        from src.services.build_run_service import create_build_jobs

        db = MagicMock()
        cached = make_obj(id="cached-1", commitSha="old123", versionString="0.8.5", artifacts=[])
        db.buildjob.find_many.return_value = [cached]
        db.buildjob.create.return_value = make_obj(id="build-1")

        pipeline = make_obj(id="run-1")
        product = make_obj(id="prod-1")
        data = make_obj(branch="main", trigger_type="manual")

        specs = [{
            "board": "alpha_b0",
            "target": "app",
            "variant": "release",
            "branch": "main",
            "commitSha": None,
            "status": "QUEUED",
            "matrixLabel": "APP_RELEASE",
            "matrixIndex": 0,
            "versionBump": False,
            "source": "latest",
            "firmware": "alpha_fw",
        }]

        builds = create_build_jobs(db, pipeline, specs, data, product)

        assert len(builds) == 1
        create_call = db.buildjob.create.call_args
        assert create_call[1]["data"]["status"] == "CACHED"
        assert create_call[1]["data"]["reusedFromId"] == "cached-1"

    def test_version_override_sets_config_flags(self):
        """Specs with versionOverride set configFlags and webhookData."""
        from src.services.build_run_service import create_build_jobs

        db = MagicMock()
        db.buildjob.create.return_value = make_obj(id="build-1")

        pipeline = make_obj(id="run-1")
        product = make_obj(id="prod-1")
        data = make_obj(branch="main", trigger_type="manual")

        specs = [{
            "board": "alpha_b0",
            "target": "app",
            "variant": "release",
            "branch": "main",
            "commitSha": "abc123",
            "status": "QUEUED",
            "matrixLabel": "PROD_VERBOSE",
            "matrixIndex": 0,
            "versionBump": False,
            "source": "head",
            "firmware": "alpha_fw",
            "versionOverride": "0.8.11",
        }]

        builds = create_build_jobs(db, pipeline, specs, data, product)

        assert len(builds) == 1
        create_call = db.buildjob.create.call_args[1]["data"]
        # configFlags should include versionOverride
        assert create_call["configFlags"] is not None

    def test_base_label_linking(self):
        """Specs with baseLabel are linked to their base build in second pass."""
        from src.services.build_run_service import create_build_jobs

        db = MagicMock()
        build_a = make_obj(id="build-a")
        build_b = make_obj(id="build-b")
        db.buildjob.create.side_effect = [build_a, build_b]

        pipeline = make_obj(id="run-1")
        product = make_obj(id="prod-1")
        data = make_obj(branch="main", trigger_type="manual")

        specs = [
            {
                "board": "alpha_b0", "target": "app", "variant": "release",
                "branch": "main", "commitSha": "abc123", "status": "QUEUED",
                "matrixLabel": "BASE", "matrixIndex": 0, "versionBump": False,
                "source": "head", "firmware": "alpha_fw",
            },
            {
                "board": "alpha_b0", "target": "app", "variant": "release",
                "branch": "main", "commitSha": "abc123", "status": "QUEUED",
                "matrixLabel": "BUMP", "matrixIndex": 1, "versionBump": True,
                "source": "head", "firmware": "alpha_fw",
                "baseLabel": "BASE",
            },
        ]

        builds = create_build_jobs(db, pipeline, specs, data, product)

        assert len(builds) == 2
        # Second build should be updated with baseJobId
        db.buildjob.update.assert_called_once()
        update_call = db.buildjob.update.call_args
        assert update_call[1]["data"]["baseJobId"] == "build-a"


# ---------------------------------------------------------------------------
# check_pipeline_completion
# ---------------------------------------------------------------------------

class TestCheckPipelineCompletion:
    """Tests for check_pipeline_completion()."""

    @patch("src.services.build_run_service.get_db_client")
    def test_returns_none_for_missing_pipeline(self, mock_get_db):
        """Returns None when pipeline not found."""
        from src.services.build_run_service import check_pipeline_completion

        db = MagicMock()
        mock_get_db.return_value = db
        db.buildrun.find_unique.return_value = None

        result = check_pipeline_completion("run-missing")
        assert result is None

    @patch("src.services.build_run_service.get_db_client")
    def test_returns_none_for_already_finished(self, mock_get_db):
        """Returns None when pipeline is already in a terminal state."""
        from src.services.build_run_service import check_pipeline_completion

        db = MagicMock()
        mock_get_db.return_value = db
        db.buildrun.find_unique.return_value = make_obj(
            id="run-1", status="SUCCESS", builds=[], completedBuilds=0,
        )

        result = check_pipeline_completion("run-1")
        assert result is None

    @patch("src.services.build_run_service.get_db_client")
    def test_returns_none_for_empty_builds(self, mock_get_db):
        """Returns None when pipeline has no builds."""
        from src.services.build_run_service import check_pipeline_completion

        db = MagicMock()
        mock_get_db.return_value = db
        db.buildrun.find_unique.return_value = make_obj(
            id="run-1", status="PENDING", builds=[], completedBuilds=0,
        )

        result = check_pipeline_completion("run-1")
        assert result is None

    @patch("src.services.build_run_service.get_db_client")
    def test_returns_none_when_incomplete(self, mock_get_db):
        """Returns None when not all builds are done yet."""
        from src.services.build_run_service import check_pipeline_completion

        db = MagicMock()
        mock_get_db.return_value = db
        db.buildrun.find_unique.return_value = make_obj(
            id="run-1", status="BUILDING", completedBuilds=0,
            builds=[
                make_obj(status="SUCCESS"),
                make_obj(status="BUILDING"),
            ],
        )

        result = check_pipeline_completion("run-1")
        assert result is None

    @patch("src.services.build_run_service.get_db_client")
    def test_all_success_sets_success(self, mock_get_db):
        """Sets pipeline to SUCCESS when all builds succeed and autoValidate=False."""
        from src.services.build_run_service import check_pipeline_completion

        db = MagicMock()
        mock_get_db.return_value = db

        builds = [make_obj(status="SUCCESS", versionString="0.8.1", variant="release")]
        pipeline = make_obj(
            id="run-1", status="PENDING", completedBuilds=0,
            builds=builds, autoValidate=False, stage=None, productId=None,
        )
        db.buildrun.find_unique.return_value = pipeline

        with patch("src.services.artifact_validator.validate_pipeline_artifacts",
                   return_value={"valid": True, "missing": []}), \
             patch("src.services.build_promotion.promote_build_run_to_firmware",
                   return_value=[{"id": "fs-1"}]), \
             patch("src.services.build_promotion.create_asset_set_from_build_run",
                   return_value={"assetSetId": "as-1", "assetCount": 1}):
            result = check_pipeline_completion("run-1")

        assert result == "SUCCESS"

    @patch("src.services.build_run_service.get_db_client")
    def test_failed_build_cancels_siblings(self, mock_get_db):
        """Failed builds trigger cancellation of pending siblings."""
        from src.services.build_run_service import check_pipeline_completion

        db = MagicMock()
        mock_get_db.return_value = db

        pending_build = make_obj(id="b-2", status="QUEUED")
        builds = [
            make_obj(id="b-1", status="FAILED"),
            pending_build,
        ]
        pipeline = make_obj(
            id="run-1", status="BUILDING", completedBuilds=0,
            builds=builds, autoValidate=False, stage=None, productId=None,
        )
        db.buildrun.find_unique.return_value = pipeline

        result = check_pipeline_completion("run-1")

        assert result == "BUILD_FAILED"
        # Pending build should be cancelled
        db.buildjob.update.assert_called()

    @patch("src.services.build_run_service.get_db_client")
    def test_exception_returns_none(self, mock_get_db):
        """Returns None on unexpected exceptions."""
        from src.services.build_run_service import check_pipeline_completion

        db = MagicMock()
        mock_get_db.return_value = db
        db.buildrun.find_unique.side_effect = Exception("DB error")

        result = check_pipeline_completion("run-1")
        assert result is None


# ---------------------------------------------------------------------------
# _find_available_fixture
# ---------------------------------------------------------------------------

class TestFindAvailableFixture:
    """Tests for _find_available_fixture()."""

    def test_finds_available_fixture(self):
        """Returns fixture with online node and configured slot."""
        from src.services.build_run_service import _find_available_fixture

        db = MagicMock()
        node = make_obj(status="ONLINE", ipAddress="10.4.45.33")
        slot = make_obj(active=True, dutSnr="0964", dutDeviceId="dev-1", node=node)
        fixture = make_obj(
            id="fix-1", name="Bench-33", status="AVAILABLE",
            slots=[slot], design=None,
        )
        db.fixture.find_many.return_value = [fixture]

        f, s, addr, all_fixtures = _find_available_fixture(db, "prod-1")

        assert f is fixture
        assert s is slot
        assert addr == "10.4.45.33"

    def test_skips_locked_fixtures(self):
        """Skips fixtures that are not AVAILABLE."""
        from src.services.build_run_service import _find_available_fixture

        db = MagicMock()
        fixture = make_obj(
            id="fix-1", name="Bench-33", status="LOCKED",
            slots=[], design=None,
        )
        db.fixture.find_many.return_value = [fixture]

        f, s, addr, all_fixtures = _find_available_fixture(db, "prod-1")

        assert f is None
        assert s is None

    def test_skips_offline_nodes(self):
        """Skips slots with offline nodes."""
        from src.services.build_run_service import _find_available_fixture

        db = MagicMock()
        node = make_obj(status="OFFLINE", ipAddress="10.4.45.33")
        slot = make_obj(active=True, dutSnr="0964", dutDeviceId="dev-1", node=node)
        fixture = make_obj(
            id="fix-1", name="Bench-33", status="AVAILABLE",
            slots=[slot], design=None,
        )
        db.fixture.find_many.return_value = [fixture]

        f, s, addr, all_fixtures = _find_available_fixture(db, "prod-1")

        assert f is None

    def test_skips_unconfigured_slots(self):
        """Skips slots without dutSnr or dutDeviceId."""
        from src.services.build_run_service import _find_available_fixture

        db = MagicMock()
        slot = make_obj(active=True, dutSnr=None, dutDeviceId=None, node=None)
        fixture = make_obj(
            id="fix-1", name="Bench-33", status="AVAILABLE",
            slots=[slot], design=None,
        )
        db.fixture.find_many.return_value = [fixture]

        f, s, addr, all_fixtures = _find_available_fixture(db, "prod-1")

        assert f is None


# ---------------------------------------------------------------------------
# _analyze_unavailability
# ---------------------------------------------------------------------------

class TestAnalyzeUnavailability:
    """Tests for _analyze_unavailability()."""

    def test_categorizes_locked_fixtures(self):
        """Locked fixtures appear in the locked list."""
        from src.services.build_run_service import _analyze_unavailability

        db = MagicMock()
        fixtures = [
            make_obj(name="Bench-1", status="LOCKED", slots=[]),
        ]

        result = _analyze_unavailability(db, fixtures)

        assert "Bench-1" in result["locked"]

    def test_categorizes_offline_nodes(self):
        """Available fixtures with offline nodes appear in offline list."""
        from src.services.build_run_service import _analyze_unavailability

        db = MagicMock()
        node = make_obj(status="OFFLINE")
        slot = make_obj(active=True, dutSnr="0964", node=node)
        fixtures = [
            make_obj(name="Bench-2", status="AVAILABLE", slots=[slot]),
        ]

        result = _analyze_unavailability(db, fixtures)

        assert "Bench-2" in result["offline"]

    def test_categorizes_unconfigured(self):
        """Available fixtures with no configured slots appear in unconfigured."""
        from src.services.build_run_service import _analyze_unavailability

        db = MagicMock()
        slot = make_obj(active=False, dutSnr=None)
        fixtures = [
            make_obj(name="Bench-3", status="AVAILABLE", slots=[slot]),
        ]

        result = _analyze_unavailability(db, fixtures)

        assert "Bench-3" in result["unconfigured"]


# ---------------------------------------------------------------------------
# _queue_validation
# ---------------------------------------------------------------------------

class TestQueueValidation:
    """Tests for _queue_validation()."""

    def test_creates_queue_entry(self):
        """Creates a new queue entry when none exists."""
        from src.services.build_run_service import _queue_validation

        db = MagicMock()
        db.validationqueueentry.find_first.return_value = None
        db.validationqueueentry.create.return_value = make_obj(id="q-1")

        unavailability = {"locked": ["Bench-1"], "offline": [], "unconfigured": []}
        result = _queue_validation(db, "run-1", unavailability)

        assert result["queued"] is True
        assert result["entryId"] == "q-1"
        db.validationqueueentry.create.assert_called_once()

    def test_returns_existing_entry(self):
        """Returns existing queue entry without creating new one."""
        from src.services.build_run_service import _queue_validation

        db = MagicMock()
        db.validationqueueentry.find_first.return_value = make_obj(id="q-existing")

        unavailability = {"locked": ["Bench-1"], "offline": [], "unconfigured": []}
        result = _queue_validation(db, "run-1", unavailability)

        assert result["queued"] is True
        assert result["entryId"] == "q-existing"
        db.validationqueueentry.create.assert_not_called()

    def test_reason_includes_all_categories(self):
        """Reason string includes all unavailability categories."""
        from src.services.build_run_service import _queue_validation

        db = MagicMock()
        db.validationqueueentry.find_first.return_value = None
        db.validationqueueentry.create.return_value = make_obj(id="q-2")

        unavailability = {
            "locked": ["B1"],
            "offline": ["B2"],
            "unconfigured": ["B3"],
        }
        result = _queue_validation(db, "run-1", unavailability)

        create_call = db.validationqueueentry.create.call_args[1]["data"]
        assert "locked" in create_call["reason"]
        assert "offline" in create_call["reason"]
        assert "unconfigured" in create_call["reason"]


# ---------------------------------------------------------------------------
# create_build_run_record
# ---------------------------------------------------------------------------

class TestCreateBuildRunRecord:
    """Tests for create_build_run_record()."""

    @patch("src.services.build_run_service.log_audit")
    @patch("src.services.build_run_service.create_build_jobs")
    def test_creates_record_and_jobs(self, mock_create_jobs, mock_audit):
        """Creates a BuildRun record and its build jobs."""
        from src.services.build_run_service import create_build_run_record

        db = MagicMock()
        pipeline = make_obj(id="run-1")
        db.buildrun.create.return_value = pipeline
        db.buildrun.find_unique.return_value = pipeline

        build = make_obj(id="build-1")
        mock_create_jobs.return_value = [build]

        product = make_obj(id="prod-1", name="Alpha")
        stage_config = make_obj(id="sc-1", stage=5)

        ctx = {
            "product_record": product,
            "product_base": "alpha",
            "repo_base": "alpha",
            "main_fw": "alpha_fw",
            "mfg_fw": "alpha_mfg_fw",
            "stage_config": stage_config,
            "stage_config_matrix": [{"role": "app"}],
            "build_specs": [{"matrixLabel": "APP"}],
        }

        data = make_obj(
            name=None, board="alpha_b0", branch="main", commit_sha="abc123",
            trigger_type="manual", matrix_mode="fuota", auto_validate=False,
            pr_branch=None, main_commit=None, repo_slug="alpha_fw",
            mfg_repo_slug=None, validation_config=None,
        )

        result_pipeline, result_builds = create_build_run_record(db, data, ctx)

        db.buildrun.create.assert_called_once()
        mock_create_jobs.assert_called_once()
        mock_audit.assert_called_once()
