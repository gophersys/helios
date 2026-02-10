"""Integration tests for Firmware Builds API."""

import json
from datetime import datetime, timezone
from io import BytesIO
from unittest.mock import MagicMock, patch

import pytest

from tests.conftest import make_obj


@pytest.fixture(autouse=True)
def _mock_presigned_url():
    """Mock presigned_url in catalog.shared so no real storage connection is made."""
    with patch("api.v2.catalog.shared.presigned_get_url", return_value=None):
        yield


def _make_chipset_obj(id="chip-1", name="nRF52840", isModem=False):
    return make_obj(id=id, name=name, isModem=isModem)


def test_list_firmware_builds(authed_client, mock_db):
    """Test listing firmware builds with pagination."""
    mock_db.product.find_unique.return_value = make_obj(
        id="prod-1",
        name="Test Product",
        description="",
        active=True,
        metadata={},
        createdAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
        updatedAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
    )

    chipset_obj = _make_chipset_obj()

    mock_db.firmwarebuild.count.return_value = 2
    mock_db.firmwarebuild.find_many.return_value = [
        make_obj(
            id="build-1",
            productId="prod-1",
            chipsetId="chip-1",
            version="1.0.0",
            isManufacturing=False,
            storageKey="firmware/prod-1/build-1/app.bin",
            filename="app.bin",
            sizeBytes=12345,
            checksum="abc123",
            contentType="application/octet-stream",
            status="RELEASED",
            notes=None,
            createdAt=datetime(2025, 1, 10, tzinfo=timezone.utc),
            updatedAt=datetime(2025, 1, 10, tzinfo=timezone.utc),
            chipset=chipset_obj,
        ),
        make_obj(
            id="build-2",
            productId="prod-1",
            chipsetId="chip-1",
            version="1.0.1",
            isManufacturing=True,
            storageKey="firmware/prod-1/build-2/app.bin",
            filename="app.bin",
            sizeBytes=12346,
            checksum="abc124",
            contentType="application/octet-stream",
            status="DRAFT",
            notes="Manufacturing build",
            createdAt=datetime(2025, 1, 11, tzinfo=timezone.utc),
            updatedAt=datetime(2025, 1, 11, tzinfo=timezone.utc),
            chipset=chipset_obj,
        ),
    ]

    response = authed_client.get("/v2/catalog/prod-1/firmware-builds")
    assert response.status_code == 200

    data = json.loads(response.data)
    assert "data" in data
    assert "data" in data["data"]
    assert "pagination" in data["data"]
    assert len(data["data"]["data"]) == 2
    assert data["data"]["pagination"]["total"] == 2


def test_update_firmware_build(authed_client, mock_db):
    """Test updating a firmware build."""
    chipset_obj = _make_chipset_obj()

    existing = make_obj(
        id="build-1",
        productId="prod-1",
        chipsetId="chip-1",
        version="1.0.0",
        isManufacturing=False,
        storageKey="firmware/prod-1/build-1/app.bin",
        filename="app.bin",
        sizeBytes=12345,
        checksum="abc123",
        contentType="application/octet-stream",
        status="DRAFT",
        notes="Old notes",
        createdAt=datetime(2025, 1, 10, tzinfo=timezone.utc),
        updatedAt=datetime(2025, 1, 10, tzinfo=timezone.utc),
    )
    mock_db.firmwarebuild.find_first.return_value = existing

    mock_db.firmwarebuild.update.return_value = make_obj(
        id="build-1",
        productId="prod-1",
        chipsetId="chip-1",
        version="1.0.0",
        isManufacturing=False,
        storageKey="firmware/prod-1/build-1/app.bin",
        filename="app.bin",
        sizeBytes=12345,
        checksum="abc123",
        contentType="application/octet-stream",
        status="RELEASED",
        notes="Updated notes",
        createdAt=datetime(2025, 1, 10, tzinfo=timezone.utc),
        updatedAt=datetime(2025, 1, 15, tzinfo=timezone.utc),
        chipset=chipset_obj,
    )

    with patch("api.v2.catalog.firmware_builds.log_audit"):
        response = authed_client.put(
            "/v2/catalog/prod-1/firmware-builds/build-1",
            data=json.dumps({
                "status": "RELEASED",
                "notes": "Updated notes",
            }),
        )

    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["data"]["status"] == "RELEASED"
    assert data["data"]["notes"] == "Updated notes"


def test_update_firmware_build_not_found(authed_client, mock_db):
    """Test updating a non-existent firmware build returns 404."""
    mock_db.firmwarebuild.find_first.return_value = None

    response = authed_client.put(
        "/v2/catalog/prod-1/firmware-builds/nonexistent",
        data=json.dumps({"status": "RELEASED"}),
    )

    assert response.status_code == 404


def test_delete_firmware_build(authed_client, mock_db):
    """Test deleting a firmware build."""
    mock_db.firmwarebuild.find_first.return_value = make_obj(
        id="build-delete",
        productId="prod-1",
        chipsetId="chip-1",
        version="1.0.0",
        storageKey="firmware/prod-1/build-delete/app.bin",
        filename="app.bin",
        createdAt=datetime(2025, 1, 10, tzinfo=timezone.utc),
        updatedAt=datetime(2025, 1, 10, tzinfo=timezone.utc),
    )

    mock_storage = MagicMock()
    mock_storage.remove_object = MagicMock()

    with patch("api.v2.catalog.firmware_builds.get_storage_client", return_value=mock_storage):
        with patch("api.v2.catalog.firmware_builds.get_bucket_name", return_value="test-bucket"):
            with patch("api.v2.catalog.firmware_builds.log_audit"):
                response = authed_client.delete("/v2/catalog/prod-1/firmware-builds/build-delete")

    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["data"]["deleted"] is True

    mock_storage.remove_object.assert_called_once_with("test-bucket", "firmware/prod-1/build-delete/app.bin")


def test_upload_firmware_build(authed_client, mock_db):
    """Test successful firmware build upload."""
    mock_db.product.find_unique.return_value = make_obj(
        id="prod-1",
        name="Test Product",
    )

    mock_db.chipset.find_unique.return_value = _make_chipset_obj()
    mock_db.firmwarebuild.find_first.return_value = None

    mock_db.firmwarebuild.create.return_value = make_obj(
        id="build-new",
        productId="prod-1",
        chipsetId="chip-1",
        version="1.0.0",
        isManufacturing=False,
        storageKey="firmware/prod-1/pending/app.hex",
        filename="app.hex",
        sizeBytes=13,
        checksum="abc",
        contentType="application/octet-stream",
        status="DRAFT",
        notes=None,
        createdAt=datetime(2025, 1, 15, tzinfo=timezone.utc),
        updatedAt=datetime(2025, 1, 15, tzinfo=timezone.utc),
    )

    mock_db.firmwarebuild.update.return_value = make_obj(
        id="build-new",
        productId="prod-1",
        chipsetId="chip-1",
        version="1.0.0",
        isManufacturing=False,
        storageKey="firmware/prod-1/build-new/app.hex",
        filename="app.hex",
        sizeBytes=13,
        checksum="abc",
        contentType="application/octet-stream",
        status="DRAFT",
        notes=None,
        createdAt=datetime(2025, 1, 15, tzinfo=timezone.utc),
        updatedAt=datetime(2025, 1, 15, tzinfo=timezone.utc),
        chipset=_make_chipset_obj(),
    )

    mock_storage = MagicMock()
    auth_headers_no_ct = {k: v for k, v in authed_client._headers.items() if k != "Content-Type"}

    with patch("api.v2.catalog.firmware_builds.get_storage_client", return_value=mock_storage):
        with patch("api.v2.catalog.firmware_builds.get_bucket_name", return_value="test-bucket"):
            with patch("api.v2.catalog.firmware_builds.log_audit"):
                response = authed_client._client.post(
                    "/v2/catalog/prod-1/firmware-builds/upload",
                    data={
                        "file": (BytesIO(b"fake firmware"), "app.hex"),
                        "chipsetId": "chip-1",
                        "version": "1.0.0",
                    },
                    headers=auth_headers_no_ct,
                    content_type="multipart/form-data",
                )

    assert response.status_code == 201
    data = json.loads(response.data)
    assert data["data"]["id"] == "build-new"
    assert data["data"]["version"] == "1.0.0"


def test_upload_firmware_build_no_file(authed_client, mock_db):
    """Test uploading firmware build without file returns 400."""
    mock_db.product.find_unique.return_value = make_obj(
        id="prod-1",
        name="Test Product",
    )

    auth_headers_no_ct = {k: v for k, v in authed_client._headers.items() if k != "Content-Type"}

    response = authed_client._client.post(
        "/v2/catalog/prod-1/firmware-builds/upload",
        data={"chipsetId": "chip-1", "version": "1.0.0"},
        headers=auth_headers_no_ct,
        content_type="multipart/form-data",
    )

    assert response.status_code == 400


def test_upload_firmware_build_invalid_extension(authed_client, mock_db):
    """Test uploading firmware build with invalid extension returns 400."""
    mock_db.product.find_unique.return_value = make_obj(
        id="prod-1",
        name="Test Product",
    )

    auth_headers_no_ct = {k: v for k, v in authed_client._headers.items() if k != "Content-Type"}

    response = authed_client._client.post(
        "/v2/catalog/prod-1/firmware-builds/upload",
        data={
            "file": (BytesIO(b"bad file"), "malware.exe"),
            "chipsetId": "chip-1",
            "version": "1.0.0",
        },
        headers=auth_headers_no_ct,
        content_type="multipart/form-data",
    )

    assert response.status_code == 400


def test_upload_firmware_build_missing_chipset(authed_client, mock_db):
    """Test uploading firmware build without chipsetId returns 400."""
    mock_db.product.find_unique.return_value = make_obj(
        id="prod-1",
        name="Test Product",
    )

    auth_headers_no_ct = {k: v for k, v in authed_client._headers.items() if k != "Content-Type"}

    response = authed_client._client.post(
        "/v2/catalog/prod-1/firmware-builds/upload",
        data={
            "file": (BytesIO(b"fake firmware"), "app.hex"),
            "version": "1.0.0",
        },
        headers=auth_headers_no_ct,
        content_type="multipart/form-data",
    )

    assert response.status_code == 400


def test_upload_firmware_build_invalid_chipset(authed_client, mock_db):
    """Test uploading firmware build with non-existent chipset returns 400."""
    mock_db.product.find_unique.return_value = make_obj(
        id="prod-1",
        name="Test Product",
    )

    mock_db.chipset.find_unique.return_value = None

    auth_headers_no_ct = {k: v for k, v in authed_client._headers.items() if k != "Content-Type"}

    response = authed_client._client.post(
        "/v2/catalog/prod-1/firmware-builds/upload",
        data={
            "file": (BytesIO(b"fake firmware"), "app.hex"),
            "chipsetId": "bad",
            "version": "1.0.0",
        },
        headers=auth_headers_no_ct,
        content_type="multipart/form-data",
    )

    assert response.status_code == 400


def test_upload_firmware_build_missing_version(authed_client, mock_db):
    """Test uploading firmware build without version returns 400."""
    mock_db.product.find_unique.return_value = make_obj(
        id="prod-1",
        name="Test Product",
    )

    mock_db.chipset.find_unique.return_value = _make_chipset_obj()

    auth_headers_no_ct = {k: v for k, v in authed_client._headers.items() if k != "Content-Type"}

    response = authed_client._client.post(
        "/v2/catalog/prod-1/firmware-builds/upload",
        data={
            "file": (BytesIO(b"fake firmware"), "app.hex"),
            "chipsetId": "chip-1",
        },
        headers=auth_headers_no_ct,
        content_type="multipart/form-data",
    )

    assert response.status_code == 400


def test_upload_firmware_build_duplicate_version(authed_client, mock_db):
    """Test uploading firmware build with duplicate version returns 409."""
    mock_db.product.find_unique.return_value = make_obj(
        id="prod-1",
        name="Test Product",
    )

    mock_db.chipset.find_unique.return_value = _make_chipset_obj()
    mock_db.firmwarebuild.find_first.return_value = make_obj(
        id="build-existing",
        version="1.0.0",
    )

    auth_headers_no_ct = {k: v for k, v in authed_client._headers.items() if k != "Content-Type"}

    response = authed_client._client.post(
        "/v2/catalog/prod-1/firmware-builds/upload",
        data={
            "file": (BytesIO(b"fake firmware"), "app.hex"),
            "chipsetId": "chip-1",
            "version": "1.0.0",
        },
        headers=auth_headers_no_ct,
        content_type="multipart/form-data",
    )

    assert response.status_code == 409


def test_upload_firmware_build_modem_required(authed_client, mock_db):
    """Test uploading firmware for modem chipset without modem file returns 400."""
    mock_db.product.find_unique.return_value = make_obj(
        id="prod-1",
        name="Test Product",
    )

    mock_db.chipset.find_unique.return_value = _make_chipset_obj(
        id="chip-modem", name="nRF9160", isModem=True,
    )
    mock_db.firmwarebuild.find_first.return_value = None

    auth_headers_no_ct = {k: v for k, v in authed_client._headers.items() if k != "Content-Type"}

    response = authed_client._client.post(
        "/v2/catalog/prod-1/firmware-builds/upload",
        data={
            "file": (BytesIO(b"fake firmware"), "app.hex"),
            "chipsetId": "chip-modem",
            "version": "1.0.0",
        },
        headers=auth_headers_no_ct,
        content_type="multipart/form-data",
    )

    assert response.status_code == 400


def test_upload_firmware_build_modem_success(authed_client, mock_db):
    """Test successful firmware build upload with modem file."""
    mock_db.product.find_unique.return_value = make_obj(
        id="prod-1",
        name="Test Product",
    )

    modem_chipset = _make_chipset_obj(id="chip-modem", name="nRF9160", isModem=True)
    mock_db.chipset.find_unique.return_value = modem_chipset
    mock_db.firmwarebuild.find_first.return_value = None

    mock_db.firmwarebuild.create.return_value = make_obj(
        id="build-modem",
        productId="prod-1",
        chipsetId="chip-modem",
        version="1.0.0",
        isManufacturing=False,
        storageKey="firmware/prod-1/pending/app.hex",
        filename="app.hex",
        sizeBytes=13,
        checksum="abc",
        contentType="application/octet-stream",
        status="DRAFT",
        notes=None,
        modemFilename="modem.zip",
        modemSizeBytes=10,
        modemChecksum="def",
        createdAt=datetime(2025, 1, 15, tzinfo=timezone.utc),
        updatedAt=datetime(2025, 1, 15, tzinfo=timezone.utc),
    )

    mock_db.firmwarebuild.update.return_value = make_obj(
        id="build-modem",
        productId="prod-1",
        chipsetId="chip-modem",
        version="1.0.0",
        isManufacturing=False,
        storageKey="firmware/prod-1/build-modem/app.hex",
        filename="app.hex",
        sizeBytes=13,
        checksum="abc",
        contentType="application/octet-stream",
        status="DRAFT",
        notes=None,
        modemFilename="modem.zip",
        modemSizeBytes=10,
        modemChecksum="def",
        createdAt=datetime(2025, 1, 15, tzinfo=timezone.utc),
        updatedAt=datetime(2025, 1, 15, tzinfo=timezone.utc),
        chipset=modem_chipset,
    )

    mock_storage = MagicMock()
    auth_headers_no_ct = {k: v for k, v in authed_client._headers.items() if k != "Content-Type"}

    with patch("api.v2.catalog.firmware_builds.get_storage_client", return_value=mock_storage):
        with patch("api.v2.catalog.firmware_builds.get_bucket_name", return_value="test-bucket"):
            with patch("api.v2.catalog.firmware_builds.log_audit"):
                response = authed_client._client.post(
                    "/v2/catalog/prod-1/firmware-builds/upload",
                    data={
                        "file": (BytesIO(b"fake firmware"), "app.hex"),
                        "modemFile": (BytesIO(b"modem data"), "modem.zip"),
                        "chipsetId": "chip-modem",
                        "version": "1.0.0",
                    },
                    headers=auth_headers_no_ct,
                    content_type="multipart/form-data",
                )

    assert response.status_code == 201
    data = json.loads(response.data)
    assert data["data"]["id"] == "build-modem"
    assert data["data"]["modemFilename"] == "modem.zip"


def test_upload_firmware_build_modem_invalid_ext(authed_client, mock_db):
    """Test uploading firmware with modem file having invalid extension returns 400."""
    mock_db.product.find_unique.return_value = make_obj(
        id="prod-1",
        name="Test Product",
    )

    mock_db.chipset.find_unique.return_value = _make_chipset_obj(
        id="chip-modem", name="nRF9160", isModem=True,
    )
    mock_db.firmwarebuild.find_first.return_value = None

    auth_headers_no_ct = {k: v for k, v in authed_client._headers.items() if k != "Content-Type"}

    response = authed_client._client.post(
        "/v2/catalog/prod-1/firmware-builds/upload",
        data={
            "file": (BytesIO(b"fake firmware"), "app.hex"),
            "modemFile": (BytesIO(b"modem data"), "modem.bin"),
            "chipsetId": "chip-modem",
            "version": "1.0.0",
        },
        headers=auth_headers_no_ct,
        content_type="multipart/form-data",
    )

    assert response.status_code == 400


def test_download_firmware_build(authed_client, mock_db):
    """Test downloading a firmware build returns presigned URL."""
    mock_db.firmwarebuild.find_unique.return_value = make_obj(
        id="build-1",
        storageKey="firmware/prod-1/build-1/app.hex",
        filename="app.hex",
    )

    with patch("api.v2.catalog.shared.presigned_get_url", return_value="https://storage.example.com/firmware/app.hex"):
        response = authed_client.get("/v2/catalog/firmware-builds/build-1/download")

    assert response.status_code == 200
    data = json.loads(response.data)
    assert "url" in data["data"]
    assert data["data"]["filename"] == "app.hex"


def test_download_firmware_build_not_found(authed_client, mock_db):
    """Test downloading a non-existent firmware build returns 404."""
    mock_db.firmwarebuild.find_unique.return_value = None

    response = authed_client.get("/v2/catalog/firmware-builds/nonexistent/download")

    assert response.status_code == 404


def test_list_firmware_builds_with_filters(authed_client, mock_db):
    """Test listing firmware builds with query filters."""
    mock_db.product.find_unique.return_value = make_obj(
        id="prod-1",
        name="Test Product",
    )

    chipset_obj = _make_chipset_obj()

    mock_db.firmwarebuild.count.return_value = 1
    mock_db.firmwarebuild.find_many.return_value = [
        make_obj(
            id="build-filtered",
            productId="prod-1",
            chipsetId="chip-1",
            version="2.0.0",
            isManufacturing=True,
            storageKey="firmware/prod-1/build-filtered/app.bin",
            filename="app.bin",
            sizeBytes=5000,
            checksum="xyz",
            contentType="application/octet-stream",
            status="RELEASED",
            notes=None,
            createdAt=datetime(2025, 2, 1, tzinfo=timezone.utc),
            updatedAt=datetime(2025, 2, 1, tzinfo=timezone.utc),
            chipset=chipset_obj,
        ),
    ]

    response = authed_client.get(
        "/v2/catalog/prod-1/firmware-builds?chipsetId=chip-1&status=RELEASED&isManufacturing=true"
    )

    assert response.status_code == 200
    data = json.loads(response.data)
    assert len(data["data"]["data"]) == 1
    assert data["data"]["data"][0]["status"] == "RELEASED"
    assert data["data"]["pagination"]["total"] == 1


def test_delete_firmware_build_with_modem(authed_client, mock_db):
    """Test deleting a firmware build with modem file removes both objects."""
    mock_db.firmwarebuild.find_first.return_value = make_obj(
        id="build-modem-del",
        productId="prod-1",
        chipsetId="chip-1",
        version="1.0.0",
        storageKey="firmware/prod-1/build-modem-del/app.hex",
        modemStorageKey="firmware/prod-1/build-modem-del/modem.zip",
        filename="app.hex",
        createdAt=datetime(2025, 1, 10, tzinfo=timezone.utc),
        updatedAt=datetime(2025, 1, 10, tzinfo=timezone.utc),
    )

    mock_storage = MagicMock()
    mock_storage.remove_object = MagicMock()

    with patch("api.v2.catalog.firmware_builds.get_storage_client", return_value=mock_storage):
        with patch("api.v2.catalog.firmware_builds.get_bucket_name", return_value="test-bucket"):
            with patch("api.v2.catalog.firmware_builds.log_audit"):
                response = authed_client.delete("/v2/catalog/prod-1/firmware-builds/build-modem-del")

    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["data"]["deleted"] is True

    assert mock_storage.remove_object.call_count == 2
