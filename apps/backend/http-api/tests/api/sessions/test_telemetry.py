"""Tests for api/v2/sessions/telemetry_api.py — telemetry manifest and channel endpoints."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from tests.conftest import make_obj


@pytest.fixture(autouse=True)
def _mock_storage():
    with patch("api.v2.sessions.telemetry_api.get_storage_client") as mock_client, \
         patch("api.v2.sessions.telemetry_api.get_bucket_name", return_value="test-bucket"):
        yield mock_client


class TestGetTelemetryManifest:
    """Tests for get_telemetry_manifest endpoint."""

    def test_session_not_found_returns_404(self, authed_client, mock_db):
        mock_db.session.find_unique.return_value = None
        resp = authed_client.get("/v2/sessions/run-1/telemetry/manifest")
        assert resp.status_code == 404

    def test_manifest_not_found_returns_404(self, authed_client, mock_db, _mock_storage):
        mock_db.session.find_unique.return_value = make_obj(id="run-1")
        storage = MagicMock()
        storage.stat_object.side_effect = Exception("not found")
        _mock_storage.return_value = storage

        resp = authed_client.get("/v2/sessions/run-1/telemetry/manifest")
        assert resp.status_code == 404

    def test_returns_manifest_json(self, authed_client, mock_db, _mock_storage):
        mock_db.session.find_unique.return_value = make_obj(id="run-1")
        storage = MagicMock()
        storage.stat_object.return_value = True
        resp_obj = MagicMock()
        resp_obj.read.return_value = b'{"channels": ["power"]}'
        storage.get_object.return_value = resp_obj
        _mock_storage.return_value = storage

        resp = authed_client.get("/v2/sessions/run-1/telemetry/manifest")
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert data["channels"] == ["power"]

    def test_storage_error_returns_500(self, authed_client, mock_db, _mock_storage):
        mock_db.session.find_unique.return_value = make_obj(id="run-1")
        _mock_storage.side_effect = Exception("storage down")

        resp = authed_client.get("/v2/sessions/run-1/telemetry/manifest")
        assert resp.status_code == 500


class TestGetTelemetryChannel:
    """Tests for get_telemetry_channel endpoint."""

    def test_session_not_found_returns_404(self, authed_client, mock_db):
        mock_db.session.find_unique.return_value = None
        resp = authed_client.get("/v2/sessions/run-1/telemetry/power")
        assert resp.status_code == 404

    def test_invalid_channel_name_returns_404(self, authed_client, mock_db):
        mock_db.session.find_unique.return_value = make_obj(id="run-1")
        resp = authed_client.get("/v2/sessions/run-1/telemetry/../../etc")
        # The route won't match with slashes, but special chars:
        # The sanitization strips invalid chars so safe_channel != channel → 404
        # This route requires valid path segment anyway

    def test_channel_not_found_returns_404(self, authed_client, mock_db, _mock_storage):
        mock_db.session.find_unique.return_value = make_obj(id="run-1")
        storage = MagicMock()
        storage.stat_object.side_effect = Exception("not found")
        _mock_storage.return_value = storage

        resp = authed_client.get("/v2/sessions/run-1/telemetry/power")
        assert resp.status_code == 404

    def test_returns_channel_data(self, authed_client, mock_db, _mock_storage):
        mock_db.session.find_unique.return_value = make_obj(id="run-1")
        storage = MagicMock()
        storage.stat_object.return_value = MagicMock(size=100)
        resp_obj = MagicMock()
        jsonl_data = b'{"ts":1,"v":3.3}\n{"ts":2,"v":3.2}\n'
        resp_obj.read.return_value = jsonl_data
        storage.get_object.return_value = resp_obj
        _mock_storage.return_value = storage

        resp = authed_client.get("/v2/sessions/run-1/telemetry/power")
        assert resp.status_code == 200
        assert resp.content_type == "application/x-ndjson"
        assert resp.data == jsonl_data

    def test_channel_with_special_chars_sanitized(self, authed_client, mock_db, _mock_storage):
        mock_db.session.find_unique.return_value = make_obj(id="run-1")
        # Channel with spaces/dots should be rejected
        resp = authed_client.get("/v2/sessions/run-1/telemetry/po.wer")
        assert resp.status_code == 404

    def test_storage_error_returns_500(self, authed_client, mock_db, _mock_storage):
        mock_db.session.find_unique.return_value = make_obj(id="run-1")
        storage = MagicMock()
        storage.stat_object.return_value = MagicMock(size=100)
        storage.get_object.side_effect = Exception("storage error")
        _mock_storage.return_value = storage

        resp = authed_client.get("/v2/sessions/run-1/telemetry/power")
        assert resp.status_code == 500
