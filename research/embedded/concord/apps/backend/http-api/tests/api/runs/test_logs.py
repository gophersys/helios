"""Tests for runs/logs.py -- log buffer, chunk ingest, download, manifest."""
from __future__ import annotations

import base64
import json
import threading
from unittest.mock import MagicMock, patch

import pytest

from tests.conftest import make_obj

# Import buffer internals for unit tests
from src.api.v2.runs.logs import (
    _buffer_key,
    _log_buffers,
    _log_lock,
    _flush_log_buffers,
    flush_log_buffers_for_run,
    _generate_manifest,
)


# ---------------------------------------------------------------------------
# Unit tests for buffer helpers
# ---------------------------------------------------------------------------

class TestBufferKey:
    def test_format(self):
        assert _buffer_key("run-1", "stdout.log") == "run-1/stdout.log"


class TestFlushLogBuffers:
    def test_empty_buffers_noop(self):
        with _log_lock:
            _log_buffers.clear()
        import api.v2.runs.logs as logs_mod
        logs_mod._flush_timer = None
        _flush_log_buffers()  # Should not raise

    @patch("src.api.v2.runs.logs.get_storage_client")
    @patch("src.api.v2.runs.logs.get_bucket_name", return_value="test-bucket")
    def test_flush_writes_to_storage(self, mock_bucket, mock_storage):
        storage = MagicMock()
        resp_obj = MagicMock()
        resp_obj.read.return_value = b"existing"
        storage.get_object.return_value = resp_obj
        mock_storage.return_value = storage

        import api.v2.runs.logs as logs_mod
        logs_mod._flush_timer = None
        with _log_lock:
            _log_buffers.clear()
            _log_buffers["run-1/stdout.log"] = bytearray(b"new data")

        _flush_log_buffers()

        storage.put_object.assert_called_once()
        call_args = storage.put_object.call_args
        assert call_args[0][0] == "test-bucket"

    @patch("src.api.v2.runs.logs.get_storage_client")
    @patch("src.api.v2.runs.logs.get_bucket_name")
    def test_flush_restores_on_storage_error(self, mock_bucket, mock_storage):
        mock_storage.side_effect = Exception("connection failed")

        import api.v2.runs.logs as logs_mod
        logs_mod._flush_timer = None
        with _log_lock:
            _log_buffers.clear()
            _log_buffers["run-1/test.log"] = bytearray(b"data")

        _flush_log_buffers()

        # Data should be restored so it isn't lost
        with _log_lock:
            assert "run-1/test.log" in _log_buffers


class TestFlushLogBuffersForRun:
    @patch("api.v2.runs.logs.get_storage_client")
    @patch("api.v2.runs.logs.get_bucket_name", return_value="test-bucket")
    def test_flushes_only_matching_run(self, mock_bucket, mock_storage):
        storage = MagicMock()
        resp_obj = MagicMock()
        resp_obj.read.return_value = b""
        storage.get_object.return_value = resp_obj
        mock_storage.return_value = storage

        with _log_lock:
            _log_buffers.clear()
            _log_buffers["run-1/stdout.log"] = bytearray(b"run1 data")
            _log_buffers["run-2/stdout.log"] = bytearray(b"run2 data")

        flush_log_buffers_for_run("run-1")

        with _log_lock:
            assert "run-2/stdout.log" in _log_buffers
            assert "run-1/stdout.log" not in _log_buffers

    def test_no_matching_buffers_noop(self):
        with _log_lock:
            _log_buffers.clear()
        flush_log_buffers_for_run("nonexistent")  # Should not raise

    @patch("api.v2.runs.logs.get_storage_client")
    @patch("api.v2.runs.logs.get_bucket_name")
    def test_storage_error_does_not_crash(self, mock_bucket, mock_storage):
        mock_storage.side_effect = Exception("down")
        with _log_lock:
            _log_buffers.clear()
            _log_buffers["run-1/x.log"] = bytearray(b"data")
        flush_log_buffers_for_run("run-1")
        # Should not raise


# ---------------------------------------------------------------------------
# _generate_manifest
# ---------------------------------------------------------------------------

class TestGenerateManifest:
    def test_generates_manifest_without_target(self, mock_db):
        mock_db.runtarget.find_first.return_value = None
        run = make_obj(
            name="Test", status="COMPLETED", productId="p-1",
            config={"stage": 4}, startedAt=None, completedAt=None,
            passedCount=3, failedCount=1, completedCount=4,
        )
        result = _generate_manifest(run, "run-1")
        assert result["runId"] == "run-1"
        assert result["target"] is None
        assert result["executions"] == []

    def test_generates_manifest_with_target_and_executions(self, mock_db):
        target = make_obj(id="t-1", serialNumber="0964", status="COMPLETED")
        mock_db.runtarget.find_first.return_value = target

        ex = make_obj(
            id="ex-1", name="test_boot", module="boot", status="PASSED",
        )
        mock_db.testexecution.find_many.return_value = [ex]

        run = make_obj(
            name="Test", status="COMPLETED", productId="p-1",
            config=None, startedAt=None, completedAt=None,
            passedCount=1, failedCount=0, completedCount=1,
        )

        result = _generate_manifest(run, "run-1")
        assert result["target"]["id"] == "t-1"
        assert len(result["executions"]) == 1
        assert result["executions"][0]["name"] == "test_boot"


# ---------------------------------------------------------------------------
# Route-level tests -- log chunk ingest
# ---------------------------------------------------------------------------

class TestReportLogChunk:
    @patch("api.v2.runs.logs._schedule_flush")
    @patch("api.v2.runs.ws.emit_to_run")
    def test_valid_chunk_returns_200(self, mock_emit, mock_flush, authed_client, mock_db):
        mock_db.testrun.find_unique.return_value = make_obj(id="run-1")
        chunk_data = base64.b64encode(b"log line\n").decode()
        resp = authed_client.post("/v2/runs/run-1/report/log-chunk", json={
            "file": "stdout.log",
            "data": chunk_data,
            "offset": 0,
        })
        assert resp.status_code == 200

    def test_run_not_found_returns_404(self, authed_client, mock_db):
        mock_db.testrun.find_unique.return_value = None
        resp = authed_client.post("/v2/runs/run-1/report/log-chunk", json={
            "file": "stdout.log",
            "data": base64.b64encode(b"x").decode(),
            "offset": 0,
        })
        assert resp.status_code == 404

    def test_missing_file_returns_400(self, authed_client, mock_db):
        resp = authed_client.post("/v2/runs/run-1/report/log-chunk", json={
            "data": base64.b64encode(b"x").decode(),
            "offset": 0,
        })
        assert resp.status_code == 400

    def test_missing_data_returns_400(self, authed_client, mock_db):
        resp = authed_client.post("/v2/runs/run-1/report/log-chunk", json={
            "file": "stdout.log",
            "offset": 0,
        })
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Route-level tests -- get log file
# ---------------------------------------------------------------------------

class TestGetLogFile:
    @patch("api.v2.runs.logs.get_storage_client")
    @patch("api.v2.runs.logs.get_bucket_name", return_value="test-bucket")
    def test_run_not_found_returns_404(self, mock_bucket, mock_storage, authed_client, mock_db):
        mock_db.testrun.find_unique.return_value = None
        resp = authed_client.get("/v2/runs/run-1/logs/stdout.log")
        assert resp.status_code == 404

    @patch("api.v2.runs.logs.get_storage_client")
    @patch("api.v2.runs.logs.get_bucket_name", return_value="test-bucket")
    def test_file_not_found_returns_404(self, mock_bucket, mock_storage, authed_client, mock_db):
        mock_db.testrun.find_unique.return_value = make_obj(id="run-1")
        storage = MagicMock()
        storage.stat_object.side_effect = Exception("not found")
        mock_storage.return_value = storage
        resp = authed_client.get("/v2/runs/run-1/logs/stdout.log")
        assert resp.status_code == 404

    @patch("api.v2.runs.logs.get_storage_client")
    @patch("api.v2.runs.logs.get_bucket_name", return_value="test-bucket")
    def test_returns_file_content(self, mock_bucket, mock_storage, authed_client, mock_db):
        mock_db.testrun.find_unique.return_value = make_obj(id="run-1")
        storage = MagicMock()
        storage.stat_object.return_value = MagicMock(size=11)
        resp_obj = MagicMock()
        resp_obj.read.return_value = b"hello world"
        storage.get_object.return_value = resp_obj
        mock_storage.return_value = storage

        resp = authed_client.get("/v2/runs/run-1/logs/stdout.log")
        assert resp.status_code == 200
        assert resp.data == b"hello world"
        assert resp.headers["X-Offset"] == "0"
        assert resp.headers["X-Total-Size"] == "11"

    @patch("api.v2.runs.logs.get_storage_client")
    @patch("api.v2.runs.logs.get_bucket_name", return_value="test-bucket")
    def test_offset_beyond_size_returns_empty(self, mock_bucket, mock_storage, authed_client, mock_db):
        mock_db.testrun.find_unique.return_value = make_obj(id="run-1")
        storage = MagicMock()
        storage.stat_object.return_value = MagicMock(size=5)
        mock_storage.return_value = storage

        resp = authed_client.get("/v2/runs/run-1/logs/stdout.log?offset=100")
        assert resp.status_code == 200
        assert resp.data == b""
        assert resp.headers["X-Offset"] == "5"

    @patch("api.v2.runs.logs.get_storage_client")
    @patch("api.v2.runs.logs.get_bucket_name", return_value="test-bucket")
    def test_offset_reads_partial(self, mock_bucket, mock_storage, authed_client, mock_db):
        mock_db.testrun.find_unique.return_value = make_obj(id="run-1")
        storage = MagicMock()
        storage.stat_object.return_value = MagicMock(size=20)
        resp_obj = MagicMock()
        resp_obj.read.return_value = b"partial data"
        storage.get_object.return_value = resp_obj
        mock_storage.return_value = storage

        resp = authed_client.get("/v2/runs/run-1/logs/stdout.log?offset=5")
        assert resp.status_code == 200
        assert resp.headers["X-Offset"] == "5"


# ---------------------------------------------------------------------------
# Route-level tests -- download run as ZIP
# ---------------------------------------------------------------------------

class TestDownloadRun:
    @patch("api.v2.runs.logs.get_storage_client")
    @patch("api.v2.runs.logs.get_bucket_name", return_value="test-bucket")
    def test_run_not_found_returns_404(self, mock_bucket, mock_storage, authed_client, mock_db):
        mock_db.testrun.find_unique.return_value = None
        resp = authed_client.get("/v2/runs/run-1/download")
        assert resp.status_code == 404

    @patch("api.v2.runs.logs.get_storage_client")
    @patch("api.v2.runs.logs.get_bucket_name", return_value="test-bucket")
    def test_existing_zip_returns_url(self, mock_bucket, mock_storage, authed_client, mock_db):
        mock_db.testrun.find_unique.return_value = make_obj(id="run-1")
        storage = MagicMock()
        storage.stat_object.return_value = True  # ZIP exists
        storage.presigned_get_object.return_value = "https://s3/run.zip"
        mock_storage.return_value = storage

        resp = authed_client.get("/v2/runs/run-1/download")
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert data["url"] == "https://s3/run.zip"

    @patch("api.v2.runs.logs.get_storage_client")
    @patch("api.v2.runs.logs.get_bucket_name", return_value="test-bucket")
    def test_no_artifacts_returns_404(self, mock_bucket, mock_storage, authed_client, mock_db):
        mock_db.testrun.find_unique.return_value = make_obj(id="run-1")
        storage = MagicMock()
        storage.stat_object.side_effect = Exception("not found")
        storage.list_objects.return_value = []
        mock_storage.return_value = storage

        resp = authed_client.get("/v2/runs/run-1/download")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Route-level tests -- manifest
# ---------------------------------------------------------------------------

class TestGetManifest:
    @patch("api.v2.runs.logs.get_storage_client")
    @patch("api.v2.runs.logs.get_bucket_name", return_value="test-bucket")
    def test_run_not_found_returns_404(self, mock_bucket, mock_storage, authed_client, mock_db):
        mock_db.testrun.find_unique.return_value = None
        resp = authed_client.get("/v2/runs/run-1/manifest")
        assert resp.status_code == 404

    @patch("api.v2.runs.logs.get_storage_client")
    @patch("api.v2.runs.logs.get_bucket_name", return_value="test-bucket")
    def test_stored_manifest_returned(self, mock_bucket, mock_storage, authed_client, mock_db):
        mock_db.testrun.find_unique.return_value = make_obj(id="run-1")
        storage = MagicMock()
        storage.stat_object.return_value = True
        resp_obj = MagicMock()
        resp_obj.read.return_value = b'{"runId": "run-1", "status": "COMPLETED"}'
        storage.get_object.return_value = resp_obj
        mock_storage.return_value = storage

        resp = authed_client.get("/v2/runs/run-1/manifest")
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert data["runId"] == "run-1"

    @patch("api.v2.runs.logs.get_storage_client")
    @patch("api.v2.runs.logs.get_bucket_name", return_value="test-bucket")
    def test_generates_manifest_when_not_stored(self, mock_bucket, mock_storage, authed_client, mock_db):
        run = make_obj(
            id="run-1", name="Test", status="COMPLETED", productId="p-1",
            config=None, startedAt=None, completedAt=None,
            passedCount=1, failedCount=0, completedCount=1,
        )
        mock_db.testrun.find_unique.return_value = run
        mock_db.runtarget.find_first.return_value = None

        storage = MagicMock()
        storage.stat_object.side_effect = Exception("not found")
        mock_storage.return_value = storage

        resp = authed_client.get("/v2/runs/run-1/manifest")
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert data["runId"] == "run-1"
