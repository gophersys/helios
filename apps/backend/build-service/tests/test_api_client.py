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

    # TODO: test_stream_log_chunk_timeout_does_not_block
    # TODO: test_heartbeat_posts_started_at
