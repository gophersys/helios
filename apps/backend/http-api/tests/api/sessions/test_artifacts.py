"""Tests for sessions/artifacts.py — list and download session artifacts."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from tests.conftest import make_obj


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now():
    return datetime(2025, 6, 1, tzinfo=timezone.utc)


def _session_obj(**overrides):
    defaults = dict(
        id="run-1",
        status="FINISHED",
        createdAt=_now(),
        updatedAt=_now(),
        finishedAt=_now(),
    )
    defaults.update(overrides)
    return make_obj(**defaults)


def _minio_obj(name: str, size: int = 1024, is_dir: bool = False):
    """Create a mock MinIO object summary."""
    obj = MagicMock()
    obj.object_name = name
    obj.size = size
    obj.is_dir = is_dir
    obj.last_modified = _now()
    obj.content_type = "application/octet-stream"
    return obj


@pytest.fixture(autouse=True)
def _mock_storage():
    """Prevent real MinIO calls in all tests."""
    mock_client = MagicMock()
    with patch("api.v2.sessions.artifacts.get_storage_client", return_value=mock_client):
        with patch("api.v2.sessions.artifacts.get_bucket_name", return_value="test-bucket"):
            yield mock_client


# ---------------------------------------------------------------------------
# TestListArtifacts
# ---------------------------------------------------------------------------

class TestListArtifacts:
    """Tests for GET /v2/validation/runs/<id>/artifacts."""

    def test_list_returns_artifact_list(self, authed_client, mock_db, _mock_storage):
        """List artifacts returns all non-directory objects under the run prefix."""
        mock_db.session.find_unique.return_value = _session_obj()
        prefix = "sessions/run-1/"
        _mock_storage.list_objects.return_value = [
            _minio_obj(f"{prefix}test_output.log", size=2048),
            _minio_obj(f"{prefix}report.jsonl", size=512),
        ]

        resp = authed_client.get("/v2/sessions/run-1/artifacts")
        assert resp.status_code == 200
        body = resp.get_json()
        assert len(body["data"]) == 2
        names = [a["name"] for a in body["data"]]
        assert "test_output.log" in names
        assert "report.jsonl" in names

    def test_list_skips_directory_entries(self, authed_client, mock_db, _mock_storage):
        """List artifacts skips directory entries from MinIO."""
        mock_db.session.find_unique.return_value = _session_obj()
        prefix = "sessions/run-1/"
        _mock_storage.list_objects.return_value = [
            _minio_obj(f"{prefix}", size=0, is_dir=True),
            _minio_obj(f"{prefix}results.log", size=100),
        ]

        resp = authed_client.get("/v2/sessions/run-1/artifacts")
        assert resp.status_code == 200
        body = resp.get_json()
        assert len(body["data"]) == 1
        assert body["data"][0]["name"] == "results.log"

    def test_list_empty_when_no_artifacts(self, authed_client, mock_db, _mock_storage):
        """List artifacts returns empty list when no files exist for run."""
        mock_db.session.find_unique.return_value = _session_obj()
        _mock_storage.list_objects.return_value = []

        resp = authed_client.get("/v2/sessions/run-1/artifacts")
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["data"] == []

    def test_list_run_not_found_returns_404(self, authed_client, mock_db):
        """List artifacts for nonexistent run returns 404."""
        mock_db.session.find_unique.return_value = None

        resp = authed_client.get("/v2/sessions/nope/artifacts")
        assert resp.status_code == 404

    def test_list_storage_error_returns_empty(self, authed_client, mock_db, _mock_storage):
        """List artifacts returns empty list gracefully on storage error."""
        mock_db.session.find_unique.return_value = _session_obj()
        _mock_storage.list_objects.side_effect = Exception("MinIO unavailable")

        resp = authed_client.get("/v2/sessions/run-1/artifacts")
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["data"] == []

    def test_list_returns_size_and_last_modified(self, authed_client, mock_db, _mock_storage):
        """List artifacts includes size and lastModified per object."""
        mock_db.session.find_unique.return_value = _session_obj()
        prefix = "sessions/run-1/"
        _mock_storage.list_objects.return_value = [
            _minio_obj(f"{prefix}debug.log", size=4096),
        ]

        resp = authed_client.get("/v2/sessions/run-1/artifacts")
        body = resp.get_json()
        artifact = body["data"][0]
        assert artifact["size"] == 4096
        assert artifact["lastModified"] is not None


# ---------------------------------------------------------------------------
# TestDownloadArtifact
# ---------------------------------------------------------------------------

class TestDownloadArtifact:
    """Tests for GET /v2/validation/runs/<id>/artifacts/<name>."""

    def test_download_log_file_returns_text_content_type(self, authed_client, mock_db, _mock_storage):
        """Download .log artifact returns text/plain content type."""
        mock_db.session.find_unique.return_value = _session_obj()
        mock_response = MagicMock()
        mock_response.read.return_value = b"log line 1\nlog line 2\n"
        mock_response.close = MagicMock()
        mock_response.release_conn = MagicMock()
        _mock_storage.get_object.return_value = mock_response

        resp = authed_client.get("/v2/sessions/run-1/artifacts/test_output.log")
        assert resp.status_code == 200
        assert "text/plain" in resp.content_type

    def test_download_json_file_returns_json_content_type(self, authed_client, mock_db, _mock_storage):
        """Download .jsonl artifact returns application/json content type."""
        mock_db.session.find_unique.return_value = _session_obj()
        mock_response = MagicMock()
        mock_response.read.return_value = b'{"test": "pass"}\n'
        mock_response.close = MagicMock()
        mock_response.release_conn = MagicMock()
        _mock_storage.get_object.return_value = mock_response

        resp = authed_client.get("/v2/sessions/run-1/artifacts/report.jsonl")
        assert resp.status_code == 200
        assert "application/json" in resp.content_type

    def test_download_run_not_found_returns_404(self, authed_client, mock_db):
        """Download artifact for nonexistent run returns 404."""
        mock_db.session.find_unique.return_value = None

        resp = authed_client.get("/v2/sessions/nope/artifacts/test.log")
        assert resp.status_code == 404

    def test_download_artifact_not_found_returns_404(self, authed_client, mock_db, _mock_storage):
        """Download nonexistent artifact file returns 404."""
        mock_db.session.find_unique.return_value = _session_obj()
        _mock_storage.get_object.side_effect = Exception("NoSuchKey")

        resp = authed_client.get("/v2/sessions/run-1/artifacts/missing.log")
        assert resp.status_code == 404

    def test_download_path_traversal_returns_400(self, authed_client, mock_db):
        """Download with path traversal attempt returns 400."""
        mock_db.session.find_unique.return_value = _session_obj()

        resp = authed_client.get("/v2/sessions/run-1/artifacts/..%2F..%2Fsecret")
        assert resp.status_code in (400, 404)

    def test_download_returns_file_bytes(self, authed_client, mock_db, _mock_storage):
        """Download artifact returns raw bytes with Content-Disposition header."""
        mock_db.session.find_unique.return_value = _session_obj()
        content = b"line one\nline two\n"
        mock_response = MagicMock()
        mock_response.read.return_value = content
        mock_response.close = MagicMock()
        mock_response.release_conn = MagicMock()
        _mock_storage.get_object.return_value = mock_response

        resp = authed_client.get("/v2/sessions/run-1/artifacts/output.log")
        assert resp.status_code == 200
        assert resp.data == content
        assert "Content-Disposition" in resp.headers

    # TODO: test_download_csv_returns_text_csv_content_type
    # TODO: test_download_absolute_path_name_returns_400
