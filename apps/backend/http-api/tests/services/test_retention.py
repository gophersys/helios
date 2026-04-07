"""Tests for services/retention.py — cleanup and storage usage functions."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, call, patch

import pytest

from tests.conftest import make_obj
from src.services.retention import (
    cleanup_old_validation_runs,
    get_storage_usage,
    DEFAULT_RETENTION_DAYS,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now():
    return datetime.now(timezone.utc)


def _old_session(id: str, days_ago: int = 70):
    finished = _now() - timedelta(days=days_ago)
    return make_obj(
        id=id,
        finishedAt=finished,
        testExecutions=[],
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
        db.session.find_many.return_value = []

        result = cleanup_old_validation_runs()

        assert result["runs_deleted"] == 0
        assert result["objects_deleted"] == 0
        db.session.delete.assert_not_called()

    def test_deletes_single_old_run(self, mock_db_and_storage):
        """Deletes a single run older than retention period and its objects."""
        db, storage = mock_db_and_storage
        run = _old_session("run-old", days_ago=70)
        db.session.find_many.return_value = [run]

        # Two MinIO objects for this run
        storage.list_objects.return_value = [
            _minio_obj("validation/runs/run-old/output.log"),
            _minio_obj("validation/runs/run-old/report.jsonl"),
        ]

        result = cleanup_old_validation_runs()

        assert result["runs_deleted"] == 1
        assert result["objects_deleted"] == 2
        db.session.delete.assert_called_once_with(where={"id": "run-old"})
        assert storage.remove_object.call_count == 2

    def test_deletes_multiple_old_runs(self, mock_db_and_storage):
        """Deletes all runs older than retention and counts totals correctly."""
        db, storage = mock_db_and_storage
        runs = [_old_session(f"run-{i}", days_ago=90) for i in range(3)]
        db.session.find_many.return_value = runs

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
        run = _old_session("run-dir-test")
        db.session.find_many.return_value = [run]

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
            _old_session("run-ok", days_ago=90),
            _old_session("run-fail", days_ago=90),
        ]
        db.session.find_many.return_value = runs

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
            _old_session("run-fail-db", days_ago=90),
            _old_session("run-ok", days_ago=90),
        ]
        db.session.find_many.return_value = runs
        storage.list_objects.return_value = []

        # First delete fails, second succeeds
        db.session.delete.side_effect = [Exception("FK violation"), None]

        result = cleanup_old_validation_runs()

        assert result["runs_deleted"] == 1  # only second succeeded
        assert "errors" in result
        assert len(result["errors"]) >= 1

    def test_summary_includes_cutoff_date(self, mock_db_and_storage):
        """Return summary includes retention_days and cutoff_date when runs exist."""
        db, storage = mock_db_and_storage
        run = _old_session("run-dated", days_ago=90)
        db.session.find_many.return_value = [run]
        storage.list_objects.return_value = []

        result = cleanup_old_validation_runs(retention_days=30)

        assert result["retention_days"] == 30
        assert "cutoff_date" in result

    def test_uses_default_retention_days(self, mock_db_and_storage):
        """Default retention period is DEFAULT_RETENTION_DAYS (60) in the return."""
        db, storage = mock_db_and_storage
        run = _old_session("run-default")
        db.session.find_many.return_value = [run]
        storage.list_objects.return_value = []

        result = cleanup_old_validation_runs()

        assert result["retention_days"] == DEFAULT_RETENTION_DAYS

    def test_query_uses_lt_cutoff_for_finishedAt(self, mock_db_and_storage):
        """DB query uses finishedAt < cutoff to find old runs."""
        db, storage = mock_db_and_storage
        db.session.find_many.return_value = []

        cleanup_old_validation_runs(retention_days=60)

        call_args = db.session.find_many.call_args[1]
        assert "finishedAt" in call_args["where"]
        assert "lt" in call_args["where"]["finishedAt"]


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
