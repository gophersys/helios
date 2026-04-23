"""Tests for ConcordClient with mocked requests."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.clients.concord import ConcordClient


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def client() -> ConcordClient:
    """ConcordClient targeting a dummy URL with a fixed API key."""
    return ConcordClient(api_url="https://test.concord.local", api_key="test-key-abc")


def _mock_response(status_code: int = 200, json_data: dict | None = None) -> MagicMock:
    """Build a mock requests.Response."""
    mock_resp = MagicMock()
    mock_resp.status_code = status_code
    mock_resp.json.return_value = json_data or {}
    mock_resp.text = str(json_data or {})
    return mock_resp


# ---------------------------------------------------------------------------
# _headers
# ---------------------------------------------------------------------------

class TestHeaders:
    """Tests for ConcordClient._headers()."""

    def test_headers_contains_authorization(self, client):
        """Authorization header is 'ApiKey {api_key}'."""
        headers = client._headers()
        assert headers["Authorization"] == "ApiKey test-key-abc"

    def test_headers_contains_content_type(self, client):
        """Content-Type is application/json."""
        assert client._headers()["Content-Type"] == "application/json"


# ---------------------------------------------------------------------------
# api_get
# ---------------------------------------------------------------------------

class TestApiGet:
    """Tests for ConcordClient.api_get()."""

    def test_api_get_success_returns_json(self, client):
        """200 response returns parsed JSON dict."""
        mock_resp = _mock_response(200, {"data": {"id": "abc"}})
        with patch("requests.get", return_value=mock_resp) as mock_get:
            result = client.api_get("/v2/builds/abc")

        assert result == {"data": {"id": "abc"}}
        mock_get.assert_called_once()

    def test_api_get_sends_auth_header(self, client):
        """GET request includes Authorization header."""
        mock_resp = _mock_response(200, {})
        with patch("requests.get", return_value=mock_resp) as mock_get:
            client.api_get("/v2/builds")

        _, kwargs = mock_get.call_args
        assert "Authorization" in kwargs.get("headers", {})

    def test_api_get_failure_returns_none(self, client):
        """500 response returns None."""
        mock_resp = _mock_response(500)
        with patch("requests.get", return_value=mock_resp):
            result = client.api_get("/v2/builds")

        assert result is None

    def test_api_get_network_exception_returns_none(self, client):
        """Network exception returns None without raising."""
        with patch("requests.get", side_effect=ConnectionError("timeout")):
            result = client.api_get("/v2/builds")

        assert result is None

    def test_api_get_constructs_full_url(self, client):
        """Full URL is base_url + path."""
        mock_resp = _mock_response(200, {})
        with patch("requests.get", return_value=mock_resp) as mock_get:
            client.api_get("/v2/builds?status=QUEUED")

        args, _ = mock_get.call_args
        assert "https://test.concord.local/v2/builds?status=QUEUED" == args[0]


# ---------------------------------------------------------------------------
# api_post
# ---------------------------------------------------------------------------

class TestApiPost:
    """Tests for ConcordClient.api_post()."""

    def test_api_post_sends_json_body(self, client):
        """POST sends JSON body containing the provided data dict."""
        mock_resp = _mock_response(200, {"ok": True})
        with patch("requests.post", return_value=mock_resp) as mock_post:
            client.api_post("/v2/builds", {"status": "QUEUED"})

        _, kwargs = mock_post.call_args
        assert kwargs.get("json") == {"status": "QUEUED"}

    def test_api_post_failure_returns_none(self, client):
        """4xx response from POST returns None."""
        mock_resp = _mock_response(422, {"error": "bad request"})
        with patch("requests.post", return_value=mock_resp):
            result = client.api_post("/v2/builds", {})

        assert result is None


# ---------------------------------------------------------------------------
# api_patch
# ---------------------------------------------------------------------------

class TestApiPatch:
    """Tests for ConcordClient.api_patch()."""

    def test_api_patch_sends_json_body(self, client):
        """PATCH sends JSON body and correct HTTP method."""
        mock_resp = _mock_response(200, {"updated": True})
        with patch("requests.patch", return_value=mock_resp) as mock_patch:
            result = client.api_patch("/v2/builds/abc", {"status": "BUILDING"})

        _, kwargs = mock_patch.call_args
        assert kwargs.get("json") == {"status": "BUILDING"}
        assert result == {"updated": True}

    def test_api_patch_failure_returns_none(self, client):
        """404 on PATCH returns None."""
        mock_resp = _mock_response(404)
        with patch("requests.patch", return_value=mock_resp):
            result = client.api_patch("/v2/builds/missing", {})

        assert result is None


# ---------------------------------------------------------------------------
# upload_file
# ---------------------------------------------------------------------------

class TestUploadFile:
    """Tests for ConcordClient.upload_file()."""

    def test_upload_file_success(self, client, tmp_path):
        """upload_file returns True on 200."""
        artifact = tmp_path / "109.0.8.3.hex"
        artifact.write_bytes(b"fake hex content")

        mock_resp = _mock_response(200, {})
        with patch("requests.post", return_value=mock_resp) as mock_post:
            result = client.upload_file("/v2/builds/abc/artifacts", artifact, "109.0.8.3.hex")

        assert result is True

    def test_upload_file_sends_multipart(self, client, tmp_path):
        """upload_file sends multipart form with 'file' field."""
        artifact = tmp_path / "test.hex"
        artifact.write_bytes(b"data")

        mock_resp = _mock_response(200, {})
        with patch("requests.post", return_value=mock_resp) as mock_post:
            client.upload_file("/v2/builds/abc/artifacts", artifact, "test.hex")

        _, kwargs = mock_post.call_args
        assert "files" in kwargs
        assert "file" in kwargs["files"]

    def test_upload_file_includes_metadata(self, client, tmp_path):
        """Metadata dict is passed as 'data' form fields."""
        artifact = tmp_path / "test.hex"
        artifact.write_bytes(b"data")
        meta = {"role": "app", "artifactType": "plaintextHex"}

        mock_resp = _mock_response(200, {})
        with patch("requests.post", return_value=mock_resp) as mock_post:
            client.upload_file("/v2/builds/abc/artifacts", artifact, "test.hex", metadata=meta)

        _, kwargs = mock_post.call_args
        assert kwargs.get("data") == meta

    def test_upload_file_failure_returns_false(self, client, tmp_path):
        """400 response returns False."""
        artifact = tmp_path / "test.hex"
        artifact.write_bytes(b"data")

        mock_resp = _mock_response(400)
        with patch("requests.post", return_value=mock_resp):
            result = client.upload_file("/v2/builds/abc/artifacts", artifact, "test.hex")

        assert result is False


# ---------------------------------------------------------------------------
# stream_log_chunk
# ---------------------------------------------------------------------------

class TestStreamLogChunk:
    """Tests for ConcordClient.stream_log_chunk()."""

    def test_stream_log_chunk_does_not_raise_on_exception(self, client):
        """Fire-and-forget: no exception propagates even if request fails."""
        with patch("requests.post", side_effect=Exception("network down")):
            # Must not raise
            client.stream_log_chunk("job-abc", "some log line\n")

    def test_stream_log_chunk_posts_to_correct_endpoint(self, client):
        """Posts to /v2/builds/{job_id}/log with chunk in body."""
        mock_resp = _mock_response(200, {})
        with patch("requests.post", return_value=mock_resp) as mock_post:
            client.stream_log_chunk("job-abc-123", "log line\n")

        args, kwargs = mock_post.call_args
        assert "/v2/builds/job-abc-123/log" in args[0]
        assert kwargs.get("json", {}).get("chunk") == "log line\n"

    def test_stream_log_chunk_sends_auth_header(self, client):
        """Request includes Authorization header."""
        mock_resp = _mock_response(200, {})
        with patch("requests.post", return_value=mock_resp) as mock_post:
            client.stream_log_chunk("job-x", "line\n")
        _, kwargs = mock_post.call_args
        assert "ApiKey" in kwargs.get("headers", {}).get("Authorization", "")


# ---------------------------------------------------------------------------
# report_progress
# ---------------------------------------------------------------------------

class TestReportProgress:
    """Tests for ConcordClient.report_progress()."""

    def test_report_progress_posts_step_and_progress(self, client):
        """Sends step, progress, and message as JSON."""
        mock_resp = _mock_response(200, {})
        with patch("requests.post", return_value=mock_resp) as mock_post:
            client.report_progress("job-1", "clone", progress=50, message="cloning repo")
        args, kwargs = mock_post.call_args
        assert "/v2/builds/job-1/progress" in args[0]
        body = kwargs.get("json", {})
        assert body["step"] == "clone"
        assert body["progress"] == 50
        assert body["message"] == "cloning repo"

    def test_report_progress_does_not_raise_on_failure(self, client):
        """Fire-and-forget: exceptions are swallowed."""
        with patch("requests.post", side_effect=Exception("timeout")):
            client.report_progress("job-1", "build")  # must not raise


# ---------------------------------------------------------------------------
# heartbeat
# ---------------------------------------------------------------------------

class TestHeartbeat:
    """Tests for ConcordClient.heartbeat()."""

    def test_heartbeat_patches_job_with_timestamp(self, client):
        """Sends PATCH to /v2/builds/{job_id} with lastHeartbeat."""
        mock_resp = _mock_response(200, {})
        with patch("requests.patch", return_value=mock_resp) as mock_patch:
            client.heartbeat("job-abc")
        args, kwargs = mock_patch.call_args
        assert "/v2/builds/job-abc" in args[0]
        assert "lastHeartbeat" in kwargs.get("json", {})

    def test_heartbeat_does_not_raise_on_failure(self, client):
        """Fire-and-forget: exceptions are swallowed."""
        with patch("requests.patch", side_effect=Exception("connection refused")):
            client.heartbeat("job-abc")  # must not raise


# ---------------------------------------------------------------------------
# get_product
# ---------------------------------------------------------------------------

class TestGetProduct:
    """Tests for ConcordClient.get_product()."""

    def test_get_product_returns_data_on_success(self, client):
        """Returns the nested data dict on 200."""
        product = {"id": "p1", "name": "Alpha"}
        mock_resp = _mock_response(200, {"data": product})
        with patch("requests.get", return_value=mock_resp):
            result = client.get_product("p1")
        assert result == product

    def test_get_product_returns_none_on_missing_data(self, client):
        """Returns None when response has no 'data' key."""
        mock_resp = _mock_response(200, {"error": "not found"})
        with patch("requests.get", return_value=mock_resp):
            result = client.get_product("p1")
        assert result is None

    def test_get_product_returns_none_on_api_error(self, client):
        """Returns None when API returns 404."""
        mock_resp = _mock_response(404)
        with patch("requests.get", return_value=mock_resp):
            result = client.get_product("missing")
        assert result is None


# ---------------------------------------------------------------------------
# upload_file — additional edge cases
# ---------------------------------------------------------------------------

class TestUploadFileEdgeCases:
    """Additional edge cases for upload_file."""

    def test_upload_file_exception_returns_false(self, client, tmp_path):
        """Network exception returns False."""
        artifact = tmp_path / "test.hex"
        artifact.write_bytes(b"data")
        with patch("requests.post", side_effect=ConnectionError("refused")):
            assert client.upload_file("/v2/builds/x/artifacts", artifact, "test.hex") is False

    def test_upload_file_no_metadata(self, client, tmp_path):
        """Omitting metadata passes empty dict as form data."""
        artifact = tmp_path / "test.hex"
        artifact.write_bytes(b"data")
        mock_resp = _mock_response(200, {})
        with patch("requests.post", return_value=mock_resp) as mock_post:
            client.upload_file("/v2/builds/x/artifacts", artifact, "test.hex")
        _, kwargs = mock_post.call_args
        assert kwargs.get("data") == {}


# ---------------------------------------------------------------------------
# api_post — additional edge cases
# ---------------------------------------------------------------------------

class TestApiPostEdgeCases:
    """Additional edge cases for api_post."""

    def test_api_post_exception_returns_none(self, client):
        """Network error returns None."""
        with patch("requests.post", side_effect=ConnectionError("refused")):
            assert client.api_post("/v2/builds", {}) is None

    def test_api_post_success_returns_json(self, client):
        """200 response returns parsed JSON."""
        mock_resp = _mock_response(200, {"id": "new-job"})
        with patch("requests.post", return_value=mock_resp):
            result = client.api_post("/v2/builds", {"status": "QUEUED"})
        assert result == {"id": "new-job"}


# ---------------------------------------------------------------------------
# api_patch — additional edge cases
# ---------------------------------------------------------------------------

class TestApiPatchEdgeCases:
    """Additional edge cases for api_patch."""

    def test_api_patch_exception_returns_none(self, client):
        """Network error returns None."""
        with patch("requests.patch", side_effect=ConnectionError("refused")):
            assert client.api_patch("/v2/builds/x", {}) is None
