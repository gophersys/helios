"""Tests for queue_scheduler — concurrency limits, priority ordering, reconciliation."""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch, call

import pytest

from services.queue_scheduler import (
    _schedule_builds,
    _schedule_validation,
    _reconcile_stuck_jobs,
    get_manufacturing_active_count,
    wake_scheduler,
    _wake_event,
)


def make_obj(**kwargs):
    return SimpleNamespace(**kwargs)


@pytest.fixture(autouse=True)
def _clear_wake():
    """Clear wake event before each test."""
    _wake_event.clear()


class TestScheduleBuilds:
    @patch("services.queue_scheduler.get_db_client")
    @patch("services.queue_scheduler._notify_build_service")
    def test_respects_concurrency_limit(self, mock_notify, mock_db):
        db = MagicMock()
        mock_db.return_value = db
        # 3 active builds, limit is 4 → 1 slot available
        db.buildjob.count.side_effect = [3, 5]  # active, queued
        result = _schedule_builds(max_concurrent=4)
        assert result == 1  # min(5 queued, 1 available)

    @patch("services.queue_scheduler.get_db_client")
    @patch("services.queue_scheduler._notify_build_service")
    def test_blocks_when_at_limit(self, mock_notify, mock_db):
        db = MagicMock()
        mock_db.return_value = db
        db.buildjob.count.return_value = 4  # active == limit
        result = _schedule_builds(max_concurrent=4)
        assert result == 0
        mock_notify.assert_not_called()

    @patch("services.queue_scheduler.get_db_client")
    @patch("services.queue_scheduler._notify_build_service")
    def test_no_queued_jobs(self, mock_notify, mock_db):
        db = MagicMock()
        mock_db.return_value = db
        db.buildjob.count.side_effect = [0, 0]  # 0 active, 0 queued
        result = _schedule_builds(max_concurrent=4)
        assert result == 0

    @patch("services.queue_scheduler.get_db_client")
    @patch("services.queue_scheduler._notify_build_service")
    def test_notifies_build_service(self, mock_notify, mock_db):
        db = MagicMock()
        mock_db.return_value = db
        db.buildjob.count.side_effect = [0, 3]  # 0 active, 3 queued
        _schedule_builds(max_concurrent=4)
        mock_notify.assert_called_once_with(db, 3)


class TestScheduleValidation:
    @patch("services.queue_scheduler.get_db_client")
    def test_blocks_when_at_limit(self, mock_db):
        db = MagicMock()
        mock_db.return_value = db
        db.validationqueueentry.count.return_value = 8  # at limit
        result = _schedule_validation(max_concurrent=8)
        assert result == []

    @patch("services.queue_scheduler.get_db_client")
    @patch("services.queue_scheduler._run_validation_scheduler")
    def test_delegates_to_schedule_queue(self, mock_sq, mock_db):
        db = MagicMock()
        mock_db.return_value = db
        db.validationqueueentry.count.return_value = 2  # 2 active, limit 8
        mock_sq.return_value = [{"entryId": "e1", "fixtureId": "f1"}]
        result = _schedule_validation(max_concurrent=8)
        mock_sq.assert_called_once_with(6)
        assert len(result) == 1

    @patch("services.queue_scheduler.get_db_client")
    @patch("services.queue_scheduler._run_validation_scheduler")
    def test_passes_available_slots(self, mock_sq, mock_db):
        db = MagicMock()
        mock_db.return_value = db
        db.validationqueueentry.count.return_value = 5  # 5 active
        mock_sq.return_value = []
        _schedule_validation(max_concurrent=8)
        mock_sq.assert_called_once_with(3)


class TestReconcileStuckJobs:
    @patch("services.queue_scheduler._try_cancel_job")
    @patch("services.queue_scheduler.get_db_client")
    def test_fails_stuck_validation_entries(self, mock_db, mock_cancel):
        db = MagicMock()
        mock_db.return_value = db

        old_time = datetime.now(timezone.utc) - timedelta(minutes=120)
        stuck_entry = make_obj(
            id="entry-stuck-001",
            status="RUNNING",
            startedAt=old_time,
            fixtureId="fixture-001",
            jobName="val-job-001",
        )
        db.validationqueueentry.find_many.return_value = [stuck_entry]
        db.manufacturingsession.find_many.return_value = []

        reconciled = _reconcile_stuck_jobs(
            validation_timeout_min=60,
            manufacturing_timeout_min=120,
        )

        assert reconciled == 1
        # Entry should be marked FAILED
        db.validationqueueentry.update.assert_called_once()
        update_data = db.validationqueueentry.update.call_args.kwargs["data"]
        assert update_data["status"] == "FAILED"
        assert "Timed out" in update_data["errorMessage"]
        # Fixture should be freed
        db.fixture.update.assert_called_once()
        fixture_data = db.fixture.update.call_args.kwargs["data"]
        assert fixture_data["status"] == "AVAILABLE"
        assert fixture_data["lockedBy"] is None

    @patch("services.queue_scheduler._try_cancel_job")
    @patch("services.queue_scheduler.get_db_client")
    def test_cancels_job_for_stuck_entry(self, mock_db, mock_cancel):
        db = MagicMock()
        mock_db.return_value = db

        old_time = datetime.now(timezone.utc) - timedelta(minutes=120)
        stuck_entry = make_obj(
            id="entry-002",
            status="RUNNING",
            startedAt=old_time,
            fixtureId="f-002",
            jobName="k8s-job-name",
        )
        db.validationqueueentry.find_many.return_value = [stuck_entry]
        db.manufacturingsession.find_many.return_value = []

        _reconcile_stuck_jobs(validation_timeout_min=60, manufacturing_timeout_min=120)
        mock_cancel.assert_called_once_with("k8s-job-name")

    @patch("services.queue_scheduler.get_db_client")
    def test_warns_on_stuck_manufacturing(self, mock_db):
        db = MagicMock()
        mock_db.return_value = db
        db.validationqueueentry.find_many.return_value = []

        old_time = datetime.now(timezone.utc) - timedelta(minutes=180)
        stuck_session = make_obj(
            id="session-old-001",
            status="ACTIVE",
            createdAt=old_time,
        )
        db.manufacturingsession.find_many.return_value = [stuck_session]

        # Should not crash, just log warning. No session update.
        reconciled = _reconcile_stuck_jobs(
            validation_timeout_min=60,
            manufacturing_timeout_min=120,
        )
        assert reconciled == 0  # Mfg sessions are warn-only, not auto-failed

    @patch("services.queue_scheduler.get_db_client")
    def test_no_stuck_jobs(self, mock_db):
        db = MagicMock()
        mock_db.return_value = db
        db.validationqueueentry.find_many.return_value = []
        db.manufacturingsession.find_many.return_value = []
        reconciled = _reconcile_stuck_jobs(
            validation_timeout_min=60,
            manufacturing_timeout_min=120,
        )
        assert reconciled == 0


class TestManufacturingGate:
    @patch("services.queue_scheduler.get_db_client")
    def test_counts_active_sessions(self, mock_db):
        db = MagicMock()
        mock_db.return_value = db
        db.manufacturingsession.count.return_value = 3
        assert get_manufacturing_active_count() == 3


class TestWakeScheduler:
    def test_wake_sets_event(self):
        assert not _wake_event.is_set()
        wake_scheduler()
        assert _wake_event.is_set()
