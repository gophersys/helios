"""Integration tests for Firmware Applications API."""

import json
from datetime import datetime, timezone
from unittest.mock import patch

from tests.conftest import make_obj


def test_create_firmware_app(authed_client, mock_db):
    """Test creating a new firmware application."""
    # Mock product exists
    mock_db.product.find_unique.return_value = make_obj(
        id="prod-1",
        name="Test Product",
        description="",
        active=True,
        metadata={},
        createdAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
        updatedAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
    )

    # Mock no existing app with same applicationId
    mock_db.firmwareapplication.find_first.return_value = None

    # Mock create returns new app
    mock_db.firmwareapplication.create.return_value = make_obj(
        id="app-new",
        productId="prod-1",
        applicationId=123,
        name="New Firmware App",
        targetMcu="nRF9160",
        chipset="Sigma5 Cx",
        coreCloudDeviceType="sensor",
        coreCloudVariant="v2",
        notes="New app notes",
        createdAt=datetime(2025, 1, 15, tzinfo=timezone.utc),
        updatedAt=datetime(2025, 1, 15, tzinfo=timezone.utc),
        firmwareBuilds=[],
    )

    with patch("src.api.v2.products.firmware_apps.log_audit"):
        response = authed_client.post(
            "/v2/products/prod-1/firmware-apps",
            data=json.dumps({
                "applicationId": 123,
                "name": "New Firmware App",
                "targetMcu": "nRF9160",
                "chipset": "Sigma5 Cx",
                "coreCloudDeviceType": "sensor",
                "coreCloudVariant": "v2",
                "notes": "New app notes",
            }),
        )

    assert response.status_code == 201
    data = json.loads(response.data)
    assert data["data"]["applicationId"] == 123
    assert data["data"]["name"] == "New Firmware App"
    assert data["data"]["targetMcu"] == "nRF9160"


def test_create_firmware_app_product_not_found(authed_client, mock_db):
    """Test creating firmware app for non-existent product returns 404."""
    mock_db.product.find_unique.return_value = None

    response = authed_client.post(
        "/v2/products/nonexistent/firmware-apps",
        data=json.dumps({
            "applicationId": 123,
            "name": "Test App",
        }),
    )

    assert response.status_code == 404


def test_create_firmware_app_duplicate_app_id(authed_client, mock_db):
    """Test creating firmware app with duplicate applicationId returns 409."""
    # Mock product exists
    mock_db.product.find_unique.return_value = make_obj(
        id="prod-1",
        name="Test Product",
        description="",
        active=True,
        metadata={},
        createdAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
        updatedAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
    )

    # Mock existing app with same applicationId
    mock_db.firmwareapplication.find_first.return_value = make_obj(
        id="app-existing",
        productId="prod-1",
        applicationId=123,
        name="Existing App",
        targetMcu="nRF9160",
        chipset="Sigma5 Cx",
        coreCloudDeviceType=None,
        coreCloudVariant=None,
        notes=None,
        createdAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
        updatedAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
    )

    response = authed_client.post(
        "/v2/products/prod-1/firmware-apps",
        data=json.dumps({
            "applicationId": 123,
            "name": "Another App",
        }),
    )

    assert response.status_code == 409
    data = json.loads(response.data)
    assert len(data["errors"]) > 0


def test_update_firmware_app(authed_client, mock_db):
    """Test updating an existing firmware application."""
    # Mock find_first returns existing app
    existing = make_obj(
        id="app-1",
        productId="prod-1",
        applicationId=123,
        name="Old App Name",
        targetMcu="nRF9160",
        chipset="Sigma5 Cx",
        coreCloudDeviceType="sensor",
        coreCloudVariant="v1",
        notes="Old notes",
        createdAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
        updatedAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
    )
    mock_db.firmwareapplication.find_first.return_value = existing

    # Mock update returns updated app
    mock_db.firmwareapplication.update.return_value = make_obj(
        id="app-1",
        productId="prod-1",
        applicationId=123,
        name="Updated App Name",
        targetMcu="nRF52840",
        chipset="Sigma5 Cx",
        coreCloudDeviceType="actuator",
        coreCloudVariant="v2",
        notes="Updated notes",
        createdAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
        updatedAt=datetime(2025, 1, 15, tzinfo=timezone.utc),
        firmwareBuilds=[],
    )

    with patch("src.api.v2.products.firmware_apps.log_audit"):
        response = authed_client.put(
            "/v2/products/prod-1/firmware-apps/app-1",
            data=json.dumps({
                "name": "Updated App Name",
                "targetMcu": "nRF52840",
                "coreCloudDeviceType": "actuator",
                "coreCloudVariant": "v2",
                "notes": "Updated notes",
            }),
        )

    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["data"]["name"] == "Updated App Name"
    assert data["data"]["targetMcu"] == "nRF52840"


def test_delete_firmware_app(authed_client, mock_db):
    """Test deleting a firmware app with no builds."""
    # Mock find_first returns existing app
    mock_db.firmwareapplication.find_first.return_value = make_obj(
        id="app-delete",
        productId="prod-1",
        applicationId=123,
        name="App to Delete",
        targetMcu="nRF9160",
        chipset="Sigma5 Cx",
        coreCloudDeviceType=None,
        coreCloudVariant=None,
        notes=None,
        createdAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
        updatedAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
    )

    # Mock no firmware build references
    mock_db.firmwarebuild.find_first.return_value = None

    with patch("src.api.v2.products.firmware_apps.log_audit"):
        response = authed_client.delete("/v2/products/prod-1/firmware-apps/app-delete")

    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["data"]["deleted"] is True


def test_delete_firmware_app_with_builds(authed_client, mock_db):
    """Test deleting a firmware app with builds returns 409."""
    # Mock find_first returns existing app
    mock_db.firmwareapplication.find_first.return_value = make_obj(
        id="app-has-builds",
        productId="prod-1",
        applicationId=123,
        name="App with Builds",
        targetMcu="nRF9160",
        chipset="Sigma5 Cx",
        coreCloudDeviceType=None,
        coreCloudVariant=None,
        notes=None,
        createdAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
        updatedAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
    )

    # Mock firmware build reference exists
    mock_db.firmwarebuild.find_first.return_value = make_obj(
        id="build-1",
        applicationId="app-has-builds",
    )

    response = authed_client.delete("/v2/products/prod-1/firmware-apps/app-has-builds")
    assert response.status_code == 409
    data = json.loads(response.data)
    assert len(data["errors"]) > 0
