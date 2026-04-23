"""Integration tests for the Firmware Builds API endpoints."""

from __future__ import annotations

import io
import json
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from tests.conftest import make_obj


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now():
    return datetime(2026, 1, 1, tzinfo=timezone.utc)


def _product_obj(**overrides):
    defaults = dict(id="prod-1", name="Alpha B0", slug="alpha-b0")
    defaults.update(overrides)
    return make_obj(**defaults)


def _fw_set_obj(**overrides):
    defaults = dict(
        id="set-1",
        productId="prod-1",
        boardRevisionId=None,
        version="0.8.3",
        releaseTrack="bench",
        isManufacturing=False,
        isDebug=True,
        source="upload",
        modemVersion=None,
        modemStorageKey=None,
        status="active",
        notes=None,
        builds=[],
        boardRevision=None,
        createdAt=_now(),
        updatedAt=_now(),
    )
    defaults.update(overrides)
    return make_obj(**defaults)


def _fw_build_obj(**overrides):
    defaults = dict(
        id="build-1",
        firmwareSetId="set-1",
        targetId=None,
        versionString="0.8.3",
        hexStorageKey="firmware-builds/prod-1/set-1/app.hex",
        cfwStorageKey=None,
        hexEncStorageKey=None,
        filename="app.hex",
        sizeBytes=102400,
        checksum="abc123",
        contentType="application/octet-stream",
        notes=None,
        target=None,
        createdAt=_now(),
    )
    defaults.update(overrides)
    return make_obj(**defaults)


@pytest.fixture(autouse=True)
def _mock_storage():
    """Prevent real MinIO calls in all tests in this module."""
    mock_client = MagicMock()
    with patch("api.v2.products.firmware_builds.get_storage_client", return_value=mock_client):
        with patch("api.v2.products.firmware_builds.get_bucket_name", return_value="test-bucket"):
            with patch("api.v2.products.firmware_builds.presigned_url", return_value="https://minio.local/presigned"):
                yield mock_client


# ---------------------------------------------------------------------------
# TestListFirmwareSets
# ---------------------------------------------------------------------------

class TestListFirmwareSets:
    """Tests for GET /v2/products/<id>/firmware."""

    def test_list_returns_paginated_results(self, authed_client, mock_db):
        """List firmware sets returns paginated set list."""
        mock_db.product.find_unique.return_value = _product_obj()
        mock_db.firmwareset.count.return_value = 2
        mock_db.firmwareset.find_many.return_value = [
            _fw_set_obj(id="set-1", version="0.8.3"),
            _fw_set_obj(id="set-2", version="0.8.2"),
        ]

        resp = authed_client.get("/v2/products/prod-1/firmware")
        assert resp.status_code == 200
        body = resp.get_json()
        assert len(body["data"]["data"]) == 2
        assert body["data"]["pagination"]["total"] == 2

    def test_list_product_not_found_returns_404(self, authed_client, mock_db):
        """List firmware sets for nonexistent product returns 404."""
        mock_db.product.find_unique.return_value = None

        resp = authed_client.get("/v2/products/no-such-prod/firmware")
        assert resp.status_code == 404

    def test_list_with_track_filter(self, authed_client, mock_db):
        """List firmware sets filters by ?releaseTrack= query param."""
        mock_db.product.find_unique.return_value = _product_obj()
        mock_db.firmwareset.count.return_value = 1
        mock_db.firmwareset.find_many.return_value = [_fw_set_obj(releaseTrack="production")]

        resp = authed_client.get("/v2/products/prod-1/firmware?releaseTrack=production")
        assert resp.status_code == 200
        call_where = mock_db.firmwareset.count.call_args[1]["where"]
        assert call_where["releaseTrack"] == "production"

    def test_list_with_is_manufacturing_filter(self, authed_client, mock_db):
        """List firmware sets filters by ?isManufacturing=true."""
        mock_db.product.find_unique.return_value = _product_obj()
        mock_db.firmwareset.count.return_value = 1
        mock_db.firmwareset.find_many.return_value = [_fw_set_obj(isManufacturing=True)]

        resp = authed_client.get("/v2/products/prod-1/firmware?isManufacturing=true")
        assert resp.status_code == 200
        call_where = mock_db.firmwareset.count.call_args[1]["where"]
        assert call_where["isManufacturing"] is True

    def test_list_empty(self, authed_client, mock_db):
        """List returns empty results for product with no firmware sets."""
        mock_db.product.find_unique.return_value = _product_obj()
        mock_db.firmwareset.count.return_value = 0
        mock_db.firmwareset.find_many.return_value = []

        resp = authed_client.get("/v2/products/prod-1/firmware")
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["data"]["data"] == []


# ---------------------------------------------------------------------------
# TestGetFirmwareSet
# ---------------------------------------------------------------------------

class TestGetFirmwareSet:
    """Tests for GET /v2/products/<id>/firmware/<set_id>."""

    def test_get_existing_set(self, authed_client, mock_db):
        """Get firmware set by ID returns set with builds."""
        build = _fw_build_obj()
        fw_set = _fw_set_obj(builds=[build])
        mock_db.firmwareset.find_first.return_value = fw_set

        resp = authed_client.get("/v2/products/prod-1/firmware/set-1")
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["data"]["id"] == "set-1"
        assert body["data"]["version"] == "0.8.3"
        assert len(body["data"]["builds"]) == 1

    def test_get_set_not_found_returns_404(self, authed_client, mock_db):
        """Get nonexistent firmware set returns 404."""
        mock_db.firmwareset.find_first.return_value = None

        resp = authed_client.get("/v2/products/prod-1/firmware/nope")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# TestCreateFirmwareSet
# ---------------------------------------------------------------------------

class TestCreateFirmwareSet:
    """Tests for POST /v2/products/<id>/firmware."""

    def test_create_success(self, authed_client, mock_db):
        """Create firmware set with valid payload returns 201."""
        mock_db.product.find_unique.return_value = _product_obj()
        mock_db.firmwareset.create.return_value = _fw_set_obj()

        with patch("api.v2.products.firmware_builds.log_audit"):
            resp = authed_client.post("/v2/products/prod-1/firmware", data=json.dumps({
                "version": "0.8.3",
                "releaseTrack": "bench",
                "isManufacturing": False,
                "isDebug": True,
            }))

        assert resp.status_code == 201
        body = resp.get_json()
        assert body["data"]["version"] == "0.8.3"

    def test_create_missing_version_returns_400(self, authed_client, mock_db):
        """Create firmware set without version returns 400."""
        mock_db.product.find_unique.return_value = _product_obj()

        resp = authed_client.post("/v2/products/prod-1/firmware", data=json.dumps({
            "releaseTrack": "bench",
        }))
        assert resp.status_code == 400

    def test_create_invalid_track_returns_400(self, authed_client, mock_db):
        """Create firmware set with invalid releaseTrack returns 400."""
        mock_db.product.find_unique.return_value = _product_obj()

        resp = authed_client.post("/v2/products/prod-1/firmware", data=json.dumps({
            "version": "1.0.0",
            "releaseTrack": "nightly",
        }))
        assert resp.status_code == 400

    def test_create_product_not_found_returns_404(self, authed_client, mock_db):
        """Create firmware set for nonexistent product returns 404."""
        mock_db.product.find_unique.return_value = None

        resp = authed_client.post("/v2/products/nope/firmware", data=json.dumps({
            "version": "1.0.0",
        }))
        assert resp.status_code == 404

    def test_create_no_body_returns_400(self, authed_client, mock_db):
        """Create firmware set with no JSON body returns 400."""
        mock_db.product.find_unique.return_value = _product_obj()

        resp = authed_client.post(
            "/v2/products/prod-1/firmware",
            data="",
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# TestUpdateFirmwareSet
# ---------------------------------------------------------------------------

class TestUpdateFirmwareSet:
    """Tests for PUT /v2/products/<id>/firmware/<set_id>."""

    def test_update_status_success(self, authed_client, mock_db):
        """Update firmware set status returns 200."""
        mock_db.firmwareset.find_first.return_value = _fw_set_obj(status="active")
        mock_db.firmwareset.update.return_value = _fw_set_obj(status="deprecated")

        with patch("api.v2.products.firmware_builds.log_audit"):
            resp = authed_client.put("/v2/products/prod-1/firmware/set-1", data=json.dumps({
                "status": "deprecated",
            }))

        assert resp.status_code == 200

    def test_update_invalid_status_returns_400(self, authed_client, mock_db):
        """Update firmware set with invalid status returns 400."""
        mock_db.firmwareset.find_first.return_value = _fw_set_obj()

        resp = authed_client.put("/v2/products/prod-1/firmware/set-1", data=json.dumps({
            "status": "released",
        }))
        assert resp.status_code == 400

    def test_update_no_fields_returns_400(self, authed_client, mock_db):
        """Update firmware set with empty payload returns 400."""
        mock_db.firmwareset.find_first.return_value = _fw_set_obj()

        resp = authed_client.put("/v2/products/prod-1/firmware/set-1", data=json.dumps({}))
        assert resp.status_code == 400

    def test_update_set_not_found_returns_404(self, authed_client, mock_db):
        """Update nonexistent firmware set returns 404."""
        mock_db.firmwareset.find_first.return_value = None

        resp = authed_client.put("/v2/products/prod-1/firmware/nope", data=json.dumps({
            "status": "deprecated",
        }))
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# TestDeleteFirmwareSet
# ---------------------------------------------------------------------------

class TestDeleteFirmwareSet:
    """Tests for DELETE /v2/products/<id>/firmware/<set_id>."""

    def test_delete_success(self, authed_client, mock_db):
        """Delete firmware set removes DB record and storage objects."""
        fw_set = _fw_set_obj(builds=[_fw_build_obj()])
        mock_db.firmwareset.find_first.return_value = fw_set

        with patch("api.v2.products.firmware_builds.log_audit"):
            resp = authed_client.delete("/v2/products/prod-1/firmware/set-1")

        assert resp.status_code == 200
        assert resp.get_json()["data"]["deleted"] is True

    def test_delete_not_found_returns_404(self, authed_client, mock_db):
        """Delete nonexistent firmware set returns 404."""
        mock_db.firmwareset.find_first.return_value = None

        resp = authed_client.delete("/v2/products/prod-1/firmware/nope")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# TestUploadFirmwareBuild
# ---------------------------------------------------------------------------

class TestUploadFirmwareBuild:
    """Tests for POST /v2/products/<id>/firmware/<set_id>/builds."""

    def test_upload_hex_success(self, authed_client, mock_db):
        """Upload hex file into a firmware set returns 201 with build data."""
        mock_db.firmwareset.find_first.return_value = _fw_set_obj()
        mock_db.firmwarebuild.create.return_value = _fw_build_obj()

        with patch("api.v2.products.firmware_builds.log_audit"):
            resp = authed_client.post(
                "/v2/products/prod-1/firmware/set-1/builds",
                data={
                    "file": (io.BytesIO(b"\xff\xfe" + b"\x00" * 100), "app_nrf52840.hex"),
                    "artifactType": "hex",
                    "versionString": "0.8.3",
                },
                content_type="multipart/form-data",
            )

        assert resp.status_code == 201
        body = resp.get_json()
        assert body["data"]["filename"] == "app.hex"

    def test_upload_bin_artifact(self, authed_client, mock_db):
        """Upload bin file creates a build record."""
        mock_db.firmwareset.find_first.return_value = _fw_set_obj()
        mock_db.firmwarebuild.create.return_value = _fw_build_obj(
            filename="modem.bin",
        )

        with patch("api.v2.products.firmware_builds.log_audit"):
            resp = authed_client.post(
                "/v2/products/prod-1/firmware/set-1/builds",
                data={
                    "file": (io.BytesIO(b"\x00" * 50), "modem.bin"),
                    "artifactType": "hex",
                },
                content_type="multipart/form-data",
            )

        assert resp.status_code == 201

    def test_upload_invalid_extension_returns_400(self, authed_client, mock_db):
        """Upload file with disallowed extension returns 400."""
        mock_db.firmwareset.find_first.return_value = _fw_set_obj()

        resp = authed_client.post(
            "/v2/products/prod-1/firmware/set-1/builds",
            data={
                "file": (io.BytesIO(b"test"), "firmware.exe"),
            },
            content_type="multipart/form-data",
        )
        assert resp.status_code == 400

    def test_upload_no_file_returns_400(self, authed_client, mock_db):
        """Upload with no file field returns 400."""
        mock_db.firmwareset.find_first.return_value = _fw_set_obj()

        resp = authed_client.post(
            "/v2/products/prod-1/firmware/set-1/builds",
            data={"artifactType": "hex"},
            content_type="multipart/form-data",
        )
        assert resp.status_code == 400

    def test_upload_set_not_found_returns_404(self, authed_client, mock_db):
        """Upload to nonexistent firmware set returns 404."""
        mock_db.firmwareset.find_first.return_value = None

        resp = authed_client.post(
            "/v2/products/prod-1/firmware/nope/builds",
            data={
                "file": (io.BytesIO(b"\x00" * 10), "app.hex"),
            },
            content_type="multipart/form-data",
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# TestDownloadFirmwareBuild
# ---------------------------------------------------------------------------

class TestDownloadFirmwareBuild:
    """Tests for GET /v2/firmware/builds/<build_id>/download."""

    def test_download_success(self, authed_client, mock_db):
        """Download build with hexStorageKey returns presigned URL."""
        build = _fw_build_obj(hexStorageKey="firmware-builds/prod-1/set-1/app.hex")
        mock_db.firmwarebuild.find_unique.return_value = build

        resp = authed_client.get("/v2/firmware/builds/build-1/download")
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["data"]["url"] == "https://minio.local/presigned"
        assert body["data"]["filename"] == "app.hex"

    def test_download_no_artifact_returns_404(self, authed_client, mock_db):
        """Download build with no storage keys returns 404."""
        build = _fw_build_obj(hexStorageKey=None, cfwStorageKey=None)
        mock_db.firmwarebuild.find_unique.return_value = build

        resp = authed_client.get("/v2/firmware/builds/build-1/download")
        assert resp.status_code == 404

    def test_download_build_not_found_returns_404(self, authed_client, mock_db):
        """Download nonexistent build returns 404."""
        mock_db.firmwarebuild.find_unique.return_value = None

        resp = authed_client.get("/v2/firmware/builds/nope/download")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# TestSerializeOutput
# ---------------------------------------------------------------------------

class TestSerializeOutput:
    """Tests for consistent serialization fields."""

    def test_firmware_set_serialization_fields(self, authed_client, mock_db):
        """Serialized firmware set contains all expected fields."""
        build = _fw_build_obj()
        fw_set = _fw_set_obj(builds=[build])
        mock_db.firmwareset.find_first.return_value = fw_set

        resp = authed_client.get("/v2/products/prod-1/firmware/set-1")
        body = resp.get_json()
        data = body["data"]

        for field in ["id", "productId", "version", "releaseTrack", "isManufacturing",
                      "isDebug", "source", "status", "builds", "createdAt", "updatedAt"]:
            assert field in data, f"Missing field: {field}"

    def test_build_serialization_includes_checksum(self, authed_client, mock_db):
        """Serialized build includes checksum field."""
        build = _fw_build_obj(checksum="deadbeef")
        fw_set = _fw_set_obj(builds=[build])
        mock_db.firmwareset.find_first.return_value = fw_set

        resp = authed_client.get("/v2/products/prod-1/firmware/set-1")
        body = resp.get_json()
        assert body["data"]["builds"][0]["checksum"] == "deadbeef"
