"""Tests for services/retention.py — cleanup and storage usage functions."""

from __future__ import annotations

import logging

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, call, patch

import pytest

from tests.conftest import make_obj
from src.services.retention import (
    cleanup_old_validation_runs,
    cleanup_stuck_uploading_test_packages,
    get_storage_usage,
    DEFAULT_RETENTION_DAYS,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now():
    return datetime.now(timezone.utc)


def _old_run(id: str, days_ago: int = 70):
    finished = _now() - timedelta(days=days_ago)
    return make_obj(
        id=id,
        completedAt=finished,
        targets=[],
    )


def _minio_obj(name: str, size: int = 1024, is_dir: bool = False):
    obj = MagicMock()
    obj.object_name = name
    obj.size = size
    obj.is_dir = is_dir
    return obj


@pytest.fixture
def mock_storage():
    return MagicMock()


@pytest.fixture
def mock_db_and_storage(mock_storage):
    """Patch both the DB and storage clients used by retention module."""
    db = MagicMock()
    with patch("src.services.retention.get_db_client", return_value=db):
        with patch("src.services.retention.get_storage_client", return_value=mock_storage):
            with patch("src.services.retention.get_bucket_name", return_value="test-bucket"):
                yield db, mock_storage


# ---------------------------------------------------------------------------
# TestCleanupOldValidationRuns
# ---------------------------------------------------------------------------

class TestCleanupOldValidationRuns:
    """Tests for cleanup_old_validation_runs()."""

    def test_returns_zero_when_no_old_runs(self, mock_db_and_storage):
        """Returns zero counts when no runs are older than retention period."""
        db, storage = mock_db_and_storage
        db.testrun.find_many.return_value = []

        result = cleanup_old_validation_runs()

        assert result["runs_deleted"] == 0
        assert result["objects_deleted"] == 0
        db.testrun.delete.assert_not_called()

    def test_deletes_single_old_run(self, mock_db_and_storage):
        """Deletes a single run older than retention period and its objects."""
        db, storage = mock_db_and_storage
        run = _old_run("run-old", days_ago=70)
        db.testrun.find_many.return_value = [run]

        # Two MinIO objects for this run
        storage.list_objects.return_value = [
            _minio_obj("validation/runs/run-old/output.log"),
            _minio_obj("validation/runs/run-old/report.jsonl"),
        ]

        result = cleanup_old_validation_runs()

        assert result["runs_deleted"] == 1
        assert result["objects_deleted"] == 2
        db.testrun.delete.assert_called_once_with(where={"id": "run-old"})
        assert storage.remove_object.call_count == 2

    def test_deletes_multiple_old_runs(self, mock_db_and_storage):
        """Deletes all runs older than retention and counts totals correctly."""
        db, storage = mock_db_and_storage
        runs = [_old_run(f"run-{i}", days_ago=90) for i in range(3)]
        db.testrun.find_many.return_value = runs

        # Each run has 1 object
        storage.list_objects.side_effect = [
            [_minio_obj(f"validation/runs/run-{i}/test.log")] for i in range(3)
        ]

        result = cleanup_old_validation_runs()

        assert result["runs_deleted"] == 3
        assert result["objects_deleted"] == 3

    def test_skips_directory_objects(self, mock_db_and_storage):
        """Directory objects are skipped (not counted as deleted)."""
        db, storage = mock_db_and_storage
        run = _old_run("run-dir-test")
        db.testrun.find_many.return_value = [run]

        storage.list_objects.return_value = [
            _minio_obj("validation/runs/run-dir-test/", is_dir=True),
            _minio_obj("validation/runs/run-dir-test/output.log"),
        ]

        result = cleanup_old_validation_runs()

        assert result["objects_deleted"] == 1  # only the file, not the dir

    def test_continues_after_minio_error(self, mock_db_and_storage):
        """Storage error for one run does not abort processing of others."""
        db, storage = mock_db_and_storage
        runs = [
            _old_run("run-ok", days_ago=90),
            _old_run("run-fail", days_ago=90),
        ]
        db.testrun.find_many.return_value = runs

        # First run: storage error; second run: 1 object
        storage.list_objects.side_effect = [
            Exception("MinIO unavailable"),
            [_minio_obj("validation/runs/run-fail/test.log")],
        ]

        result = cleanup_old_validation_runs()

        # Both DB deletes attempted
        assert result["runs_deleted"] == 2
        # Only second run's object deleted
        assert result["objects_deleted"] == 1
        # Error recorded for storage failure on first run
        assert "errors" in result

    def test_continues_after_db_delete_error(self, mock_db_and_storage):
        """DB delete error for one run is recorded and processing continues."""
        db, storage = mock_db_and_storage
        runs = [
            _old_run("run-fail-db", days_ago=90),
            _old_run("run-ok", days_ago=90),
        ]
        db.testrun.find_many.return_value = runs
        storage.list_objects.return_value = []

        # First delete fails, second succeeds
        db.testrun.delete.side_effect = [Exception("FK violation"), None]

        result = cleanup_old_validation_runs()

        assert result["runs_deleted"] == 1  # only second succeeded
        assert "errors" in result
        assert len(result["errors"]) >= 1

    def test_summary_includes_cutoff_date(self, mock_db_and_storage):
        """Return summary includes retention_days and cutoff_date when runs exist."""
        db, storage = mock_db_and_storage
        run = _old_run("run-dated", days_ago=90)
        db.testrun.find_many.return_value = [run]
        storage.list_objects.return_value = []

        result = cleanup_old_validation_runs(retention_days=30)

        assert result["retention_days"] == 30
        assert "cutoff_date" in result

    def test_uses_default_retention_days(self, mock_db_and_storage):
        """Default retention period is DEFAULT_RETENTION_DAYS (60) in the return."""
        db, storage = mock_db_and_storage
        run = _old_run("run-default")
        db.testrun.find_many.return_value = [run]
        storage.list_objects.return_value = []

        result = cleanup_old_validation_runs()

        assert result["retention_days"] == DEFAULT_RETENTION_DAYS

    def test_query_uses_lt_cutoff_for_completedAt(self, mock_db_and_storage):
        """DB query uses completedAt < cutoff to find old runs."""
        db, storage = mock_db_and_storage
        db.testrun.find_many.return_value = []

        cleanup_old_validation_runs(retention_days=60)

        call_args = db.testrun.find_many.call_args[1]
        assert "completedAt" in call_args["where"]
        assert "lt" in call_args["where"]["completedAt"]


# ---------------------------------------------------------------------------
# TestGetStorageUsage
# ---------------------------------------------------------------------------

class TestGetStorageUsage:
    """Tests for get_storage_usage()."""

    def test_empty_storage_returns_zeros(self):
        """Returns zero totals when no objects exist."""
        mock_storage = MagicMock()
        mock_storage.list_objects.return_value = []

        with patch("src.services.retention.get_storage_client", return_value=mock_storage):
            with patch("src.services.retention.get_bucket_name", return_value="test-bucket"):
                result = get_storage_usage()

        assert result["total_size_bytes"] == 0
        assert result["total_objects"] == 0
        assert result["runs_count"] == 0

    def test_aggregates_objects_by_run_id(self):
        """Groups objects by run_id extracted from path."""
        mock_storage = MagicMock()
        mock_storage.list_objects.return_value = [
            _minio_obj("validation/runs/run-a/output.log", size=1000),
            _minio_obj("validation/runs/run-a/report.jsonl", size=500),
            _minio_obj("validation/runs/run-b/output.log", size=2000),
        ]

        with patch("src.services.retention.get_storage_client", return_value=mock_storage):
            with patch("src.services.retention.get_bucket_name", return_value="test-bucket"):
                result = get_storage_usage()

        assert result["total_objects"] == 3
        assert result["total_size_bytes"] == 3500
        assert result["runs_count"] == 2
        assert result["runs"]["run-a"]["objects"] == 2
        assert result["runs"]["run-b"]["size"] == 2000

    def test_returns_error_on_storage_failure(self):
        """Returns error dict when storage client fails."""
        mock_storage = MagicMock()
        mock_storage.list_objects.side_effect = Exception("connection refused")

        with patch("src.services.retention.get_storage_client", return_value=mock_storage):
            with patch("src.services.retention.get_bucket_name", return_value="test-bucket"):
                result = get_storage_usage()

        assert "error" in result

    def test_skips_directory_entries(self):
        """Directory entries do not contribute to object count or size."""
        mock_storage = MagicMock()
        mock_storage.list_objects.return_value = [
            _minio_obj("validation/runs/run-a/", size=0, is_dir=True),
            _minio_obj("validation/runs/run-a/test.log", size=1024),
        ]

        with patch("src.services.retention.get_storage_client", return_value=mock_storage):
            with patch("src.services.retention.get_bucket_name", return_value="test-bucket"):
                result = get_storage_usage()

        assert result["total_objects"] == 1
        assert result["total_size_bytes"] == 1024

    def test_total_size_mb_is_rounded(self):
        """total_size_mb is rounded to 2 decimal places."""
        mock_storage = MagicMock()
        mock_storage.list_objects.return_value = [
            _minio_obj("validation/runs/run-x/f.log", size=1048576),  # exactly 1 MB
        ]

        with patch("src.services.retention.get_storage_client", return_value=mock_storage):
            with patch("src.services.retention.get_bucket_name", return_value="test-bucket"):
                result = get_storage_usage()

        assert result["total_size_mb"] == 1.0

    # TODO: test_storage_usage_handles_none_size_objects
    # TODO: test_cleanup_does_not_delete_runs_newer_than_cutoff


# ---------------------------------------------------------------------------
# TestCleanupStuckUploadingTestPackages
# ---------------------------------------------------------------------------

class TestCleanupStuckUploadingTestPackages:
    """Tests for ``cleanup_stuck_uploading_test_packages``."""

    def test_deletes_old_uploading_placeholder(self, mock_db_and_storage):
        db, _ = mock_db_and_storage
        old = make_obj(
            id="tp-stuck-1", version="dev-x-1",
            createdAt=datetime.now(timezone.utc) - timedelta(hours=2),
        )
        db.testpackage.find_many.return_value = [old]

        result = cleanup_stuck_uploading_test_packages(age_minutes=60)

        assert result["deleted"] == 1
        db.testpackage.delete.assert_called_once_with(where={"id": "tp-stuck-1"})

    def test_dry_run_does_not_delete(self, mock_db_and_storage):
        db, _ = mock_db_and_storage
        old = make_obj(
            id="tp-stuck-2", version="dev-y-1",
            createdAt=datetime.now(timezone.utc) - timedelta(hours=2),
        )
        db.testpackage.find_many.return_value = [old]

        result = cleanup_stuck_uploading_test_packages(age_minutes=60, dry_run=True)

        assert result["deleted"] == 1
        assert result["dry_run"] is True
        db.testpackage.delete.assert_not_called()

    def test_query_only_targets_uploading_status(self, mock_db_and_storage):
        db, _ = mock_db_and_storage
        db.testpackage.find_many.return_value = []

        cleanup_stuck_uploading_test_packages(age_minutes=60)

        where = db.testpackage.find_many.call_args.kwargs.get("where") or {}
        assert where.get("status") == "UPLOADING"


# ---------------------------------------------------------------------------
# Retention summary log line — format is load-bearing for Loki dashboards
# ---------------------------------------------------------------------------


class TestRetentionSummaryEmit:
    """Asserts the ``concord_retention_summary`` log line shape stays stable."""

    def test_validation_runs_emits_summary(self, mock_db_and_storage, caplog):
        db, _ = mock_db_and_storage
        db.testrun.find_many.return_value = []

        with caplog.at_level(logging.INFO, logger="src.services.retention"):
            cleanup_old_validation_runs()

        msgs = [r.getMessage() for r in caplog.records]
        summary = [m for m in msgs if "concord_retention_summary" in m]
        assert summary, f"missing summary line. records: {msgs!r}"
        assert any("scope=validation_runs" in m for m in summary)

    def test_stuck_uploads_emits_summary(self, mock_db_and_storage, caplog):
        db, _ = mock_db_and_storage
        db.testpackage.find_many.return_value = []

        with caplog.at_level(logging.INFO, logger="src.services.retention"):
            cleanup_stuck_uploading_test_packages(age_minutes=60)

        msgs = [r.getMessage() for r in caplog.records]
        summary = [m for m in msgs if "concord_retention_summary" in m]
        assert summary
        assert any("scope=stuck_uploads" in m for m in summary)
