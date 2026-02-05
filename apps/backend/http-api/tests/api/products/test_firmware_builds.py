"""Integration tests for Firmware Builds API."""

import json
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from tests.conftest import make_obj


@pytest.fixture(autouse=True)
def _mock_presigned_url():
    """Mock presigned_url in products.shared so no real storage connection is made."""
    with patch("api.v2.products.shared.presigned_get_url", return_value=None):
        yield


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

    mock_db.firmwarebuild.count.return_value = 2
    mock_db.firmwarebuild.find_many.return_value = [
        make_obj(
            id="build-1",
            productId="prod-1",
            applicationId="app-1",
            boardRevisionId="rev-1",
            version="1.0.0",
            majorVersion=1,
            minorVersion=0,
            buildNumber=0,
            bootloaderId=None,
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
            application=make_obj(
                name="Main App",
                applicationId="app-001",
            ),
            boardRevision=make_obj(
                version="1.0",
            ),
        ),
        make_obj(
            id="build-2",
            productId="prod-1",
            applicationId="app-1",
            boardRevisionId="rev-1",
            version="1.0.1",
            majorVersion=1,
            minorVersion=0,
            buildNumber=1,
            bootloaderId="boot-1",
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
            application=make_obj(
                name="Main App",
                applicationId="app-001",
            ),
            boardRevision=make_obj(
                version="1.0",
            ),
        ),
    ]

    response = authed_client.get("/v2/products/prod-1/firmware-builds")
    assert response.status_code == 200

    data = json.loads(response.data)
    assert "data" in data
    assert "data" in data["data"]
    assert "pagination" in data["data"]
    assert len(data["data"]["data"]) == 2
    assert data["data"]["pagination"]["total"] == 2


def test_update_firmware_build(authed_client, mock_db):
    """Test updating a firmware build."""
    existing = make_obj(
        id="build-1",
        productId="prod-1",
        applicationId="app-1",
        boardRevisionId="rev-1",
        version="1.0.0",
        majorVersion=1,
        minorVersion=0,
        buildNumber=0,
        bootloaderId=None,
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
        applicationId="app-1",
        boardRevisionId="rev-1",
        version="1.0.0",
        majorVersion=1,
        minorVersion=0,
        buildNumber=0,
        bootloaderId=None,
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
        application=make_obj(
            name="Main App",
            applicationId="app-001",
        ),
        boardRevision=make_obj(
            version="1.0",
        ),
    )

    with patch("api.v2.products.firmware_builds.log_audit"):
        response = authed_client.put(
            "/v2/products/prod-1/firmware-builds/build-1",
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
        "/v2/products/prod-1/firmware-builds/nonexistent",
        data=json.dumps({"status": "RELEASED"}),
    )

    assert response.status_code == 404


def test_delete_firmware_build(authed_client, mock_db):
    """Test deleting a firmware build."""
    mock_db.firmwarebuild.find_first.return_value = make_obj(
        id="build-delete",
        productId="prod-1",
        applicationId="app-1",
        boardRevisionId="rev-1",
        version="1.0.0",
        storageKey="firmware/prod-1/build-delete/app.bin",
        filename="app.bin",
        createdAt=datetime(2025, 1, 10, tzinfo=timezone.utc),
        updatedAt=datetime(2025, 1, 10, tzinfo=timezone.utc),
    )

    mock_storage = MagicMock()
    mock_storage.remove_object = MagicMock()

    with patch("api.v2.products.firmware_builds.get_storage_client", return_value=mock_storage):
        with patch("api.v2.products.firmware_builds.get_bucket_name", return_value="test-bucket"):
            with patch("api.v2.products.firmware_builds.log_audit"):
                response = authed_client.delete("/v2/products/prod-1/firmware-builds/build-delete")

    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["data"]["deleted"] is True

    mock_storage.remove_object.assert_called_once_with("test-bucket", "firmware/prod-1/build-delete/app.bin")
