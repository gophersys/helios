"""Tests for api/v2/sessions/logs.py — log buffer, chunk upload, download, manifest."""

from __future__ import annotations

import base64
import json
import threading
from unittest.mock import MagicMock, patch

import pytest

from tests.conftest import make_obj

# Import buffer internals for unit tests
from src.api.v2.sessions.logs import (
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
        # Reset the global timer
        import api.v2.sessions.logs as logs_mod
        logs_mod._flush_timer = None
        _flush_log_buffers()  # Should not raise

    @patch("src.api.v2.sessions.logs.get_storage_client")
    @patch("src.api.v2.sessions.logs.get_bucket_name", return_value="test-bucket")
    def test_flush_writes_to_storage(self, mock_bucket, mock_storage):
        storage = MagicMock()
        resp_obj = MagicMock()
        resp_obj.read.return_value = b"existing"
        storage.get_object.return_value = resp_obj
        mock_storage.return_value = storage

        import api.v2.sessions.logs as logs_mod
        logs_mod._flush_timer = None
        with _log_lock:
            _log_buffers.clear()
            _log_buffers["run-1/stdout.log"] = bytearray(b"new data")

        _flush_log_buffers()

        storage.put_object.assert_called_once()
        call_args = storage.put_object.call_args
        assert call_args[0][0] == "test-bucket"

    @patch("src.api.v2.sessions.logs.get_storage_client")
    @patch("src.api.v2.sessions.logs.get_bucket_name")
    def test_flush_restores_on_storage_error(self, mock_bucket, mock_storage):
        mock_storage.side_effect = Exception("connection failed")

        import api.v2.sessions.logs as logs_mod
        logs_mod._flush_timer = None
        with _log_lock:
            _log_buffers.clear()
            _log_buffers["run-1/test.log"] = bytearray(b"data")

        _flush_log_buffers()

        # Data should be restored
        with _log_lock:
            assert "run-1/test.log" in _log_buffers


class TestFlushLogBuffersForRun:
    @patch("api.v2.sessions.logs.get_storage_client")
    @patch("api.v2.sessions.logs.get_bucket_name", return_value="test-bucket")
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

        # run-2 should still be in buffers
        with _log_lock:
            assert "run-2/stdout.log" in _log_buffers
            assert "run-1/stdout.log" not in _log_buffers

    def test_no_matching_buffers_noop(self):
        with _log_lock:
            _log_buffers.clear()
        flush_log_buffers_for_run("nonexistent")  # Should not raise

    @patch("api.v2.sessions.logs.get_storage_client")
    @patch("api.v2.sessions.logs.get_bucket_name")
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
    def test_generates_manifest_without_device(self):
        db = MagicMock()
        db.device.find_first.return_value = None
        session = make_obj(
            name="Test", status="COMPLETED", productId="p-1",
            config={"stage": 4}, startedAt=None, finishedAt=None,
            passedCount=3, failedCount=1, completedCount=4,
        )
        result = _generate_manifest(db, session, "run-1")
        assert result["runId"] == "run-1"
        assert result["device"] is None
        assert result["executions"] == []

    def test_generates_manifest_with_device_and_executions(self):
        db = MagicMock()
        device = make_obj(id="d-1", serialNumber="0964", status="COMPLETED")
        db.device.find_first.return_value = device

        ex = make_obj(
            testId="t-1", status="PASSED",
            test=make_obj(name="test_boot"),
        )
        db.testexecution.find_many.return_value = [ex]

        session = make_obj(
            name="Test", status="COMPLETED", productId="p-1",
            config=None, startedAt=None, finishedAt=None,
            passedCount=1, failedCount=0, completedCount=1,
        )
        result = _generate_manifest(db, session, "run-1")
        assert result["device"]["id"] == "d-1"
        assert len(result["executions"]) == 1
        assert result["executions"][0]["testName"] == "test_boot"


# ---------------------------------------------------------------------------
# Route-level tests
# ---------------------------------------------------------------------------

class TestReportLogChunk:
    @patch("api.v2.sessions.logs._schedule_flush")
    @patch("api.v2.sessions.reporter._emit_validation_event")
    def test_valid_chunk_returns_200(self, mock_emit, mock_flush, authed_client, mock_db):
        mock_db.session.find_unique.return_value = make_obj(id="run-1")
        chunk_data = base64.b64encode(b"log line\n").decode()
        resp = authed_client.post("/v2/sessions/run-1/report/log-chunk", json={
            "file": "stdout.log",
            "data": chunk_data,
            "offset": 0,
        })
        assert resp.status_code == 200

    def test_session_not_found_returns_404(self, authed_client, mock_db):
        mock_db.session.find_unique.return_value = None
        resp = authed_client.post("/v2/sessions/run-1/report/log-chunk", json={
            "file": "stdout.log",
            "data": base64.b64encode(b"x").decode(),
            "offset": 0,
        })
        assert resp.status_code == 404

    def test_missing_body_returns_400(self, authed_client, mock_db):
        resp = authed_client.post("/v2/sessions/run-1/report/log-chunk",
                                   json={})
        assert resp.status_code == 400


class TestGetLogFile:
    @patch("api.v2.sessions.logs.get_storage_client")
    @patch("api.v2.sessions.logs.get_bucket_name", return_value="test-bucket")
    def test_session_not_found_returns_404(self, mock_bucket, mock_storage, authed_client, mock_db):
        mock_db.session.find_unique.return_value = None
        resp = authed_client.get("/v2/sessions/run-1/logs/stdout.log")
        assert resp.status_code == 404

    @patch("api.v2.sessions.logs.get_storage_client")
    @patch("api.v2.sessions.logs.get_bucket_name", return_value="test-bucket")
    def test_file_not_found_returns_404(self, mock_bucket, mock_storage, authed_client, mock_db):
        mock_db.session.find_unique.return_value = make_obj(id="run-1")
        storage = MagicMock()
        storage.stat_object.side_effect = Exception("not found")
        mock_storage.return_value = storage
        resp = authed_client.get("/v2/sessions/run-1/logs/stdout.log")
        assert resp.status_code == 404

    @patch("api.v2.sessions.logs.get_storage_client")
    @patch("api.v2.sessions.logs.get_bucket_name", return_value="test-bucket")
    def test_returns_file_content(self, mock_bucket, mock_storage, authed_client, mock_db):
        mock_db.session.find_unique.return_value = make_obj(id="run-1")
        storage = MagicMock()
        storage.stat_object.return_value = MagicMock(size=11)
        resp_obj = MagicMock()
        resp_obj.read.return_value = b"hello world"
        storage.get_object.return_value = resp_obj
        mock_storage.return_value = storage

        resp = authed_client.get("/v2/sessions/run-1/logs/stdout.log")
        assert resp.status_code == 200
        assert resp.data == b"hello world"
        assert resp.headers["X-Offset"] == "0"
        assert resp.headers["X-Total-Size"] == "11"

    @patch("api.v2.sessions.logs.get_storage_client")
    @patch("api.v2.sessions.logs.get_bucket_name", return_value="test-bucket")
    def test_offset_beyond_size_returns_empty(self, mock_bucket, mock_storage, authed_client, mock_db):
        mock_db.session.find_unique.return_value = make_obj(id="run-1")
        storage = MagicMock()
        storage.stat_object.return_value = MagicMock(size=5)
        mock_storage.return_value = storage

        resp = authed_client.get("/v2/sessions/run-1/logs/stdout.log?offset=100")
        assert resp.status_code == 200
        assert resp.data == b""
        assert resp.headers["X-Offset"] == "5"

    @patch("api.v2.sessions.logs.get_storage_client")
    @patch("api.v2.sessions.logs.get_bucket_name", return_value="test-bucket")
    def test_offset_reads_partial(self, mock_bucket, mock_storage, authed_client, mock_db):
        mock_db.session.find_unique.return_value = make_obj(id="run-1")
        storage = MagicMock()
        storage.stat_object.return_value = MagicMock(size=20)
        resp_obj = MagicMock()
        resp_obj.read.return_value = b"partial data"
        storage.get_object.return_value = resp_obj
        mock_storage.return_value = storage

        resp = authed_client.get("/v2/sessions/run-1/logs/stdout.log?offset=5")
        assert resp.status_code == 200
        assert resp.headers["X-Offset"] == "5"


class TestDownloadRun:
    @patch("api.v2.sessions.logs.get_storage_client")
    @patch("api.v2.sessions.logs.get_bucket_name", return_value="test-bucket")
    def test_session_not_found_returns_404(self, mock_bucket, mock_storage, authed_client, mock_db):
        mock_db.session.find_unique.return_value = None
        resp = authed_client.get("/v2/sessions/run-1/download")
        assert resp.status_code == 404

    @patch("api.v2.sessions.logs.get_storage_client")
    @patch("api.v2.sessions.logs.get_bucket_name", return_value="test-bucket")
    def test_existing_zip_returns_url(self, mock_bucket, mock_storage, authed_client, mock_db):
        mock_db.session.find_unique.return_value = make_obj(id="run-1")
        storage = MagicMock()
        storage.stat_object.return_value = True  # ZIP exists
        storage.presigned_get_object.return_value = "https://s3/run.zip"
        mock_storage.return_value = storage

        resp = authed_client.get("/v2/sessions/run-1/download")
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert data["url"] == "https://s3/run.zip"

    @patch("api.v2.sessions.logs.get_storage_client")
    @patch("api.v2.sessions.logs.get_bucket_name", return_value="test-bucket")
    def test_no_artifacts_returns_404(self, mock_bucket, mock_storage, authed_client, mock_db):
        mock_db.session.find_unique.return_value = make_obj(id="run-1")
        storage = MagicMock()
        storage.stat_object.side_effect = Exception("not found")
        storage.list_objects.return_value = []
        mock_storage.return_value = storage

        resp = authed_client.get("/v2/sessions/run-1/download")
        assert resp.status_code == 404


class TestGetManifest:
    @patch("api.v2.sessions.logs.get_storage_client")
    @patch("api.v2.sessions.logs.get_bucket_name", return_value="test-bucket")
    def test_session_not_found_returns_404(self, mock_bucket, mock_storage, authed_client, mock_db):
        mock_db.session.find_unique.return_value = None
        resp = authed_client.get("/v2/sessions/run-1/manifest")
        assert resp.status_code == 404

    @patch("api.v2.sessions.logs.get_storage_client")
    @patch("api.v2.sessions.logs.get_bucket_name", return_value="test-bucket")
    def test_stored_manifest_returned(self, mock_bucket, mock_storage, authed_client, mock_db):
        mock_db.session.find_unique.return_value = make_obj(id="run-1")
        storage = MagicMock()
        storage.stat_object.return_value = True
        resp_obj = MagicMock()
        resp_obj.read.return_value = b'{"runId": "run-1", "status": "COMPLETED"}'
        storage.get_object.return_value = resp_obj
        mock_storage.return_value = storage

        resp = authed_client.get("/v2/sessions/run-1/manifest")
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert data["runId"] == "run-1"

    @patch("api.v2.sessions.logs.get_storage_client")
    @patch("api.v2.sessions.logs.get_bucket_name", return_value="test-bucket")
    def test_generates_manifest_when_not_stored(self, mock_bucket, mock_storage, authed_client, mock_db):
        session = make_obj(
            id="run-1", name="Test", status="COMPLETED", productId="p-1",
            config=None, startedAt=None, finishedAt=None,
            passedCount=1, failedCount=0, completedCount=1,
        )
        mock_db.session.find_unique.return_value = session
        mock_db.device.find_first.return_value = None

        storage = MagicMock()
        storage.stat_object.side_effect = Exception("not found")
        mock_storage.return_value = storage

        resp = authed_client.get("/v2/sessions/run-1/manifest")
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert data["runId"] == "run-1"
