"""Extended tests for build_run_service.py — check_build_run_completion, trigger_build_run_validation, fixture helpers."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch, call

import pytest

from tests.conftest import make_obj


def _now():
    return datetime(2026, 1, 1, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# check_build_run_completion
# ---------------------------------------------------------------------------

class TestCheckBuildRunCompletion:
    """Tests for check_build_run_completion()."""

    @patch("src.services.builds.run_service.get_db_client")
    def test_build_run_not_found_returns_none(self, mock_get_db):
        from src.services.builds.run_service import check_build_run_completion
        db = MagicMock()
        mock_get_db.return_value = db
        db.buildrun.find_unique.return_value = None
        assert check_build_run_completion("run-1") is None

    @patch("src.services.builds.run_service.get_db_client")
    def test_already_complete_returns_none(self, mock_get_db):
        from src.services.builds.run_service import check_build_run_completion
        db = MagicMock()
        mock_get_db.return_value = db
        db.buildrun.find_unique.return_value = make_obj(
            id="run-1", status="SUCCESS", builds=[], product=None,
        )
        assert check_build_run_completion("run-1") is None

    @patch("src.services.builds.run_service.get_db_client")
    def test_no_builds_returns_none(self, mock_get_db):
        from src.services.builds.run_service import check_build_run_completion
        db = MagicMock()
        mock_get_db.return_value = db
        db.buildrun.find_unique.return_value = make_obj(
            id="run-1", status="BUILDING", builds=[], product=None,
        )
        assert check_build_run_completion("run-1") is None

    @patch("src.services.builds.run_service.get_db_client")
    def test_pending_builds_returns_none(self, mock_get_db):
        from src.services.builds.run_service import check_build_run_completion
        db = MagicMock()
        mock_get_db.return_value = db
        builds = [
            make_obj(id="b-1", status="SUCCESS"),
            make_obj(id="b-2", status="QUEUED"),
        ]
        db.buildrun.find_unique.return_value = make_obj(
            id="run-1", status="BUILDING", builds=builds,
            completedBuilds=1, product=None,
        )
        assert check_build_run_completion("run-1") is None

    @patch("src.services.builds.run_service.get_db_client")
    def test_all_success_no_autovalidate(self, mock_get_db):
        from src.services.builds.run_service import check_build_run_completion
        db = MagicMock()
        mock_get_db.return_value = db

        builds = [
            make_obj(id="b-1", status="SUCCESS"),
            make_obj(id="b-2", status="CACHED"),
        ]
        db.buildrun.find_unique.return_value = make_obj(
            id="run-1", status="BUILDING", builds=builds,
            completedBuilds=1, autoRunStage=False, productId="prod-1",
            stage=None, product=None,
        )

        with patch("src.services.builds.run_service.validate_build_run_artifacts", return_value={"valid": True, "builds": [], "missing": []}), \
             patch("src.services.builds.promotion.promote_build_run_to_firmware", return_value=[]), \
             patch("src.services.builds.promotion.create_asset_set_from_build_run", return_value=None):
            result = check_build_run_completion("run-1")

        assert result == "SUCCESS"

    @patch("src.services.builds.run_service.get_db_client")
    def test_failed_build_cancels_pending(self, mock_get_db):
        from src.services.builds.run_service import check_build_run_completion
        db = MagicMock()
        mock_get_db.return_value = db

        builds = [
            make_obj(id="b-1", status="FAILED"),
            make_obj(id="b-2", status="QUEUED"),
            make_obj(id="b-3", status="BUILDING"),
        ]
        db.buildrun.find_unique.return_value = make_obj(
            id="run-1", status="BUILDING", builds=builds,
            completedBuilds=0, autoRunStage=False, productId=None,
            stage=None, product=None,
        )

        result = check_build_run_completion("run-1")
        assert result == "BUILD_FAILED"
        # Pending builds should be cancelled
        assert db.buildjob.update.call_count == 2  # b-2 and b-3

    @patch("src.services.builds.run_service.get_db_client")
    def test_artifact_validation_failure(self, mock_get_db):
        from src.services.builds.run_service import check_build_run_completion
        db = MagicMock()
        mock_get_db.return_value = db

        builds = [make_obj(id="b-1", status="SUCCESS")]
        db.buildrun.find_unique.return_value = make_obj(
            id="run-1", status="BUILDING", builds=builds,
            completedBuilds=0, autoRunStage=False, productId="prod-1",
            stage=None, product=None,
        )

        with patch("src.services.builds.run_service.validate_build_run_artifacts", return_value={
            "valid": False,
            "builds": [],
            "missing": [{"label": "APP", "role": "app", "artifactType": "plaintextHex"}],
        }):
            result = check_build_run_completion("run-1")
        assert result == "BUILD_FAILED"

    @patch("src.services.builds.run_service.get_db_client")
    def test_exception_returns_none(self, mock_get_db):
        from src.services.builds.run_service import check_build_run_completion
        db = MagicMock()
        mock_get_db.return_value = db
        db.buildrun.find_unique.side_effect = Exception("db error")

        result = check_build_run_completion("run-1")
        assert result is None


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

def _ready_node(deploy_name: str = "mtib-deploy-1"):
    return make_obj(
        id="node-1",
        disabled=False,
        ipAddress="192.168.1.100",
        hostname="verdin",
        metadata={"deployment_name": deploy_name},
    )


def _ready_mtib_status(deploy_name: str = "mtib-deploy-1") -> dict:
    """Build a mtib_status_map that reports the deployment as READY."""
    return {
        deploy_name: {
            "name": deploy_name,
            "replicas": 1,
            "readyReplicas": 1,
            "pods": [{"ready": True}],
        },
    }


class TestFindAvailableFixture:
    @patch("src.api.v2.fixtures.fixtures._probe_slots_concurrent", return_value={"slot-1": True})
    @patch("src.services.builds.run_service._get_mtib_status_map")
    def test_finds_available_fixture(self, mock_status, mock_probe):
        from src.services.builds.run_service import _find_available_fixture
        db = MagicMock()
        mock_status.return_value = _ready_mtib_status()
        slot = make_obj(
            id="slot-1", nodeId="node-1", active=True,
            dutSnr="0964", dutDeviceId="dev-1", node=_ready_node(),
        )
        fixture = make_obj(
            id="fix-1", name="Bench 1", lockState="FREE",
            slots=[slot], stationId="st-1", design=None,
        )
        db.fixture.find_many.return_value = [fixture]

        f, s, addr, all_f = _find_available_fixture(db, "prod-1")
        assert f == fixture
        assert s == slot
        assert addr == "192.168.1.100"

    @patch("src.services.builds.run_service._get_mtib_status_map", return_value={})
    def test_skips_locked_fixtures(self, _mock_status):
        from src.services.builds.run_service import _find_available_fixture
        db = MagicMock()
        fixture = make_obj(
            id="fix-1", name="Bench 1", lockState="IN_USE",
            slots=[], stationId="st-1",
        )
        db.fixture.find_many.return_value = [fixture]

        f, s, addr, all_f = _find_available_fixture(db, "prod-1")
        assert f is None

    @patch("src.services.builds.run_service._get_mtib_status_map", return_value={})
    def test_skips_offline_nodes(self, _mock_status):
        from src.services.builds.run_service import _find_available_fixture
        db = MagicMock()
        # No deployment in mtib_status_map → state is NOT_DEPLOYED → skipped.
        node = make_obj(id="node-1", disabled=False, ipAddress="192.168.1.100", metadata={})
        slot = make_obj(
            id="slot-1", nodeId="node-1", active=True,
            dutSnr="0964", dutDeviceId="dev-1", node=node,
        )
        fixture = make_obj(
            id="fix-1", name="Bench 1", lockState="FREE",
            slots=[slot], stationId="st-1",
        )
        db.fixture.find_many.return_value = [fixture]

        f, s, addr, all_f = _find_available_fixture(db, "prod-1")
        assert f is None

    @patch("src.api.v2.fixtures.fixtures._probe_slots_concurrent", return_value={"slot-1": True})
    @patch("src.services.builds.run_service._get_mtib_status_map")
    def test_skips_slots_without_dut(self, mock_status, _mock_probe):
        from src.services.builds.run_service import _find_available_fixture
        db = MagicMock()
        mock_status.return_value = _ready_mtib_status()
        slot = make_obj(
            id="slot-1", nodeId="node-1", active=True,
            dutSnr=None, dutDeviceId=None, node=_ready_node(),
        )
        fixture = make_obj(
            id="fix-1", name="Bench 1", lockState="FREE",
            slots=[slot], stationId="st-1",
        )
        db.fixture.find_many.return_value = [fixture]

        f, s, addr, all_f = _find_available_fixture(db, "prod-1")
        assert f is None


class TestAnalyzeUnavailability:
    def test_categorizes_fixtures(self):
        from src.services.builds.run_service import _analyze_unavailability
        db = MagicMock()

        locked = make_obj(name="Bench-1", lockState="IN_USE", slots=[])
        node_offline = make_obj(status="OFFLINE")
        slot_configured = make_obj(active=True, dutSnr="0964", node=node_offline)
        available_offline = make_obj(name="Bench-2", lockState="FREE", slots=[slot_configured])
        unconfigured = make_obj(name="Bench-3", lockState="FREE", slots=[])

        result = _analyze_unavailability(db, [locked, available_offline, unconfigured])
        assert "Bench-1" in result["locked"]
        assert "Bench-2" in result["offline"]
        assert "Bench-3" in result["unconfigured"]


class TestQueueValidation:
    def test_creates_new_entry(self):
        from src.services.builds.run_service import _queue_validation
        db = MagicMock()
        db.validationqueueentry.find_first.return_value = None
        entry = make_obj(id="q-1")
        db.validationqueueentry.create.return_value = entry

        with patch("src.services.builds.run_service.log_audit"):
            result = _queue_validation(db, "run-1", {"locked": ["Bench-1"], "offline": [], "unconfigured": []})

        assert result["queued"] is True
        assert result["entryId"] == "q-1"

    def test_returns_existing_entry(self):
        from src.services.builds.run_service import _queue_validation
        db = MagicMock()
        db.validationqueueentry.find_first.return_value = make_obj(id="q-existing")

        result = _queue_validation(db, "run-1", {"locked": ["Bench-1"], "offline": [], "unconfigured": []})
        assert result["queued"] is True
        assert result["entryId"] == "q-existing"
        db.validationqueueentry.create.assert_not_called()


# ---------------------------------------------------------------------------
# Fixture configuration check
# ---------------------------------------------------------------------------

class TestFixtureHelpers:
    def test_has_configured_slot(self):
        from src.services.builds.run_service import _has_configured_slot
        assert _has_configured_slot(make_obj(slots=[make_obj(active=True, dutSnr="0964")])) is True
        assert _has_configured_slot(make_obj(slots=[make_obj(active=True, dutSnr=None)])) is False
        assert _has_configured_slot(make_obj(slots=[])) is False
