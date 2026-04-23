"""Tests for heartbeat-based build recovery."""

from datetime import datetime, timezone, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from src.services.builds.recovery import (
    recover_stale_builds,
    CLONING_TIMEOUT_MINUTES,
    HEARTBEAT_STALE_MINUTES,
    BUILDING_FALLBACK_TIMEOUT_MINUTES,
    MAX_RECOVERY_ATTEMPTS,
    _get_recovery_count,
)


def _make_build(
    id="build-001",
    status="BUILDING",
    started_minutes_ago=15,
    heartbeat_minutes_ago=None,
    webhook_data=None,
    build_run_id=None,
):
    """Create a mock build job."""
    now = datetime.now(timezone.utc)
    return SimpleNamespace(
        id=id,
        status=status,
        startedAt=now - timedelta(minutes=started_minutes_ago),
        lastHeartbeat=(
            now - timedelta(minutes=heartbeat_minutes_ago)
            if heartbeat_minutes_ago is not None
            else None
        ),
        webhookData=webhook_data or {},
        buildRunId=build_run_id,
    )


class TestGetRecoveryCount:
    def test_returns_zero_when_no_webhook_data(self):
        build = _make_build(webhook_data=None)
        build.webhookData = None
        # When webhookData is not a dict, returns 0
        assert _get_recovery_count(build) == 0

    def test_returns_zero_when_no_recovery_count(self):
        build = _make_build(webhook_data={})
        assert _get_recovery_count(build) == 0

    def test_returns_existing_count(self):
        build = _make_build(webhook_data={"recoveryCount": 2})
        assert _get_recovery_count(build) == 2


class TestHeartbeatRecovery:
    """Test that BUILDING builds use heartbeat-based staleness detection."""

    @patch("src.services.builds.recovery.get_db_client")
    def test_stale_heartbeat_triggers_recovery(self, mock_get_db):
        """A BUILDING build with a stale heartbeat (>5 min) should be recovered."""
        db = MagicMock()
        mock_get_db.return_value = db

        stale_build = _make_build(
            status="BUILDING",
            started_minutes_ago=8,
            heartbeat_minutes_ago=6,  # > HEARTBEAT_STALE_MINUTES (5)
        )

        # Cloning query returns nothing, heartbeat query returns our build, legacy returns nothing
        db.buildjob.find_many.side_effect = [[], [stale_build], []]

        count = recover_stale_builds()

        assert count == 1
        db.buildjob.update.assert_called_once()
        update_data = db.buildjob.update.call_args[1]["data"]
        assert update_data["status"] == "QUEUED"
        assert update_data["startedAt"] is None
        assert update_data["lastHeartbeat"] is None

    @patch("src.services.builds.recovery.get_db_client")
    def test_fresh_heartbeat_not_recovered(self, mock_get_db):
        """A BUILDING build with a recent heartbeat should NOT be recovered."""
        db = MagicMock()
        mock_get_db.return_value = db

        # All three queries return empty — fresh heartbeat won't match stale query
        db.buildjob.find_many.side_effect = [[], [], []]

        count = recover_stale_builds()

        assert count == 0
        db.buildjob.update.assert_not_called()

    @patch("src.services.builds.recovery.get_db_client")
    def test_no_heartbeat_fallback_to_started_at(self, mock_get_db):
        """Legacy build with no heartbeat and old startedAt should be recovered."""
        db = MagicMock()
        mock_get_db.return_value = db

        legacy_build = _make_build(
            status="BUILDING",
            started_minutes_ago=35,  # > BUILDING_FALLBACK_TIMEOUT_MINUTES (30)
            heartbeat_minutes_ago=None,
        )

        # Cloning=empty, heartbeat=empty, legacy=our build
        db.buildjob.find_many.side_effect = [[], [], [legacy_build]]

        count = recover_stale_builds()

        assert count == 1
        update_data = db.buildjob.update.call_args[1]["data"]
        assert update_data["status"] == "QUEUED"

    @patch("src.services.builds.recovery.get_db_client")
    def test_no_heartbeat_recent_start_not_recovered(self, mock_get_db):
        """Legacy build with no heartbeat but recent startedAt should NOT be recovered."""
        db = MagicMock()
        mock_get_db.return_value = db

        # Started 10 min ago, no heartbeat — within 30-min fallback window
        db.buildjob.find_many.side_effect = [[], [], []]

        count = recover_stale_builds()

        assert count == 0


class TestCloningRecovery:
    """CLONING timeout remains startedAt-based (no heartbeat during clone)."""

    @patch("src.services.builds.recovery.get_db_client")
    def test_stale_cloning_recovered(self, mock_get_db):
        db = MagicMock()
        mock_get_db.return_value = db

        stale = _make_build(status="CLONING", started_minutes_ago=6)
        db.buildjob.find_many.side_effect = [[stale], [], []]

        count = recover_stale_builds()

        assert count == 1
        update_data = db.buildjob.update.call_args[1]["data"]
        assert update_data["status"] == "QUEUED"


class TestMaxRecoveryAttempts:
    """Builds that exceed MAX_RECOVERY_ATTEMPTS are marked FAILED."""

    @patch("src.services.builds.recovery.get_db_client")
    def test_exceeds_max_attempts_marked_failed(self, mock_get_db):
        db = MagicMock()
        mock_get_db.return_value = db

        build = _make_build(
            status="BUILDING",
            started_minutes_ago=35,
            heartbeat_minutes_ago=None,
            webhook_data={"recoveryCount": MAX_RECOVERY_ATTEMPTS},
        )
        db.buildjob.find_many.side_effect = [[], [], [build]]

        count = recover_stale_builds()

        assert count == 1
        update_data = db.buildjob.update.call_args[1]["data"]
        assert update_data["status"] == "FAILED"
        assert update_data["lastHeartbeat"] is None
        assert "Permanently failed" in update_data["errorMessage"]

    @patch("src.services.builds.recovery.get_db_client")
    def test_under_max_attempts_recovered_to_queued(self, mock_get_db):
        db = MagicMock()
        mock_get_db.return_value = db

        build = _make_build(
            status="BUILDING",
            started_minutes_ago=35,
            heartbeat_minutes_ago=None,
            webhook_data={"recoveryCount": 1},
        )
        db.buildjob.find_many.side_effect = [[], [], [build]]

        count = recover_stale_builds()

        assert count == 1
        update_data = db.buildjob.update.call_args[1]["data"]
        assert update_data["status"] == "QUEUED"


class TestMixedRecovery:
    """Multiple stale builds across different categories."""

    @patch("src.services.builds.recovery.get_db_client")
    def test_mixed_cloning_and_building(self, mock_get_db):
        db = MagicMock()
        mock_get_db.return_value = db

        cloning = _make_build(id="clone-1", status="CLONING", started_minutes_ago=7)
        heartbeat_stale = _make_build(
            id="build-1", status="BUILDING",
            started_minutes_ago=10, heartbeat_minutes_ago=6,
        )
        legacy = _make_build(
            id="build-2", status="BUILDING",
            started_minutes_ago=40, heartbeat_minutes_ago=None,
        )

        db.buildjob.find_many.side_effect = [
            [cloning],          # stale cloning
            [heartbeat_stale],  # stale heartbeat
            [legacy],           # stale legacy
        ]

        count = recover_stale_builds()

        assert count == 3
        assert db.buildjob.update.call_count == 3
