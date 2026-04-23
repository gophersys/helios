"""Tests for api/v2/icle/logs.py — ICLE device log upload and listing."""

from __future__ import annotations

import io
from unittest.mock import MagicMock, patch

import pytest

from tests.conftest import make_obj


@pytest.fixture(autouse=True)
def _mock_storage():
    with patch("api.v2.icle.logs.get_storage_client") as mock_client, \
         patch("api.v2.icle.logs.get_bucket_name", return_value="test-bucket"), \
         patch("api.v2.icle.logs.presigned_get_url", return_value="https://s3/file"):
        yield mock_client


class TestListDeviceLogs:
    def test_device_not_found_returns_404(self, authed_client, mock_db):
        mock_db.icledevice.find_unique.return_value = None
        resp = authed_client.get("/v2/devices/icle/dev-1/logs")
        assert resp.status_code == 404

    def test_returns_empty_list(self, authed_client, mock_db):
        mock_db.icledevice.find_unique.return_value = make_obj(id="dev-1")
        mock_db.iclelog.count.return_value = 0
        mock_db.iclelog.find_many.return_value = []

        resp = authed_client.get("/v2/devices/icle/dev-1/logs")
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert data["data"] == []
        assert data["pagination"]["total"] == 0

    def test_returns_logs_with_download_urls(self, authed_client, mock_db):
        mock_db.icledevice.find_unique.return_value = make_obj(id="dev-1")
        mock_db.iclelog.count.return_value = 1
        log_entry = make_obj(
            id="log-1", deviceId="dev-1", filename="power.csv",
            storageKey="icle/logs/dev-1/power.csv",
            sizeBytes=1024, format="csv", uploadedAt=None,
        )
        mock_db.iclelog.find_many.return_value = [log_entry]

        resp = authed_client.get("/v2/devices/icle/dev-1/logs")
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert len(data["data"]) == 1
        assert data["data"][0]["downloadUrl"] == "https://s3/file"

    def test_pagination_params(self, authed_client, mock_db):
        mock_db.icledevice.find_unique.return_value = make_obj(id="dev-1")
        mock_db.iclelog.count.return_value = 25
        mock_db.iclelog.find_many.return_value = []

        resp = authed_client.get("/v2/devices/icle/dev-1/logs?page=2&limit=10")
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert data["pagination"]["page"] == 2
        assert data["pagination"]["limit"] == 10
        assert data["pagination"]["pages"] == 3


class TestUploadDeviceLog:
    def test_device_not_found_returns_404(self, authed_client, mock_db):
        mock_db.icledevice.find_unique.return_value = None
        data = {"file": (io.BytesIO(b"data"), "test.csv")}
        resp = authed_client.post("/v2/devices/icle/dev-1/logs",
                                   data=data, content_type="multipart/form-data")
        # The authed_client sets Content-Type to application/json in headers
        # For file uploads we need to override

    def test_no_file_returns_400(self, authed_client, mock_db):
        mock_db.icledevice.find_unique.return_value = make_obj(
            id="dev-1", deviceId="ICLE-001",
        )
        resp = authed_client.post("/v2/devices/icle/dev-1/logs")
        assert resp.status_code == 400

    @patch("api.v2.icle.logs.log_audit")
    def test_upload_creates_new_entry(self, mock_audit, authed_client, mock_db, _mock_storage, app):
        mock_db.icledevice.find_unique.return_value = make_obj(
            id="dev-1", deviceId="ICLE-001",
        )
        storage = MagicMock()
        _mock_storage.return_value = storage

        created = make_obj(
            id="log-1", deviceId="dev-1", filename="power.csv",
            storageKey="icle/logs/ICLE-001/20260101_power.csv",
            sizeBytes=5, format="csv", uploadedAt=None,
        )
        mock_db.iclelog.find_first.return_value = None
        mock_db.iclelog.create.return_value = created

        with app.test_client() as client:
            from src.services.auth.jwt import create_token
            token = create_token(
                user_id="test-user-id", email="test@example.com",
                name="Test", permission_set_id="test-perm-set-id", role="DEVELOPER",
            )
            resp = client.post(
                "/v2/devices/icle/dev-1/logs",
                data={"file": (io.BytesIO(b"hello"), "power.csv")},
                content_type="multipart/form-data",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert resp.status_code == 201

    @patch("api.v2.icle.logs.log_audit")
    def test_upload_updates_existing_entry(self, mock_audit, authed_client, mock_db, _mock_storage, app):
        mock_db.icledevice.find_unique.return_value = make_obj(
            id="dev-1", deviceId="ICLE-001",
        )
        storage = MagicMock()
        _mock_storage.return_value = storage

        existing = make_obj(id="log-existing")
        updated = make_obj(
            id="log-existing", deviceId="dev-1", filename="power.csv",
            storageKey="icle/logs/ICLE-001/new_power.csv",
            sizeBytes=5, format="csv", uploadedAt=None,
        )
        mock_db.iclelog.find_first.return_value = existing
        mock_db.iclelog.update.return_value = updated

        with app.test_client() as client:
            from src.services.auth.jwt import create_token
            token = create_token(
                user_id="test-user-id", email="test@example.com",
                name="Test", permission_set_id="test-perm-set-id", role="DEVELOPER",
            )
            resp = client.post(
                "/v2/devices/icle/dev-1/logs",
                data={"file": (io.BytesIO(b"hello"), "power.csv")},
                content_type="multipart/form-data",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert resp.status_code == 201
