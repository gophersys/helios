"""Integration tests for the Chipsets API."""

import json
from datetime import datetime, timezone
from unittest.mock import patch

from tests.conftest import make_obj


def test_list_chipsets(authed_client, mock_db):
    """Test listing chipsets with pagination."""
    mock_db.chipset.count.return_value = 2
    mock_db.chipset.find_many.return_value = [
        make_obj(
            id="chip-1",
            name="nRF52840",
            manufacturer="Nordic Semiconductor",
            isModem=False,
            description=None,
            active=True,
            createdAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
            updatedAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
        ),
        make_obj(
            id="chip-2",
            name="nRF9160",
            manufacturer="Nordic Semiconductor",
            isModem=True,
            description="LTE modem",
            active=True,
            createdAt=datetime(2025, 1, 2, tzinfo=timezone.utc),
            updatedAt=datetime(2025, 1, 2, tzinfo=timezone.utc),
        ),
    ]

    response = authed_client.get("/v2/products/chipsets")
    assert response.status_code == 200

    data = json.loads(response.data)
    assert "data" in data
    assert "data" in data["data"]
    assert "pagination" in data["data"]
    assert len(data["data"]["data"]) == 2
    assert data["data"]["pagination"]["total"] == 2


def test_list_chipsets_unauthorized(client):
    """Test listing chipsets without auth returns 401."""
    response = client.get("/v2/products/chipsets")
    assert response.status_code == 401


def test_create_chipset(authed_client, mock_db):
    """Test creating a new chipset."""
    mock_db.chipset.find_unique.return_value = None

    mock_db.chipset.create.return_value = make_obj(
        id="chip-new",
        name="ESP32",
        manufacturer="Espressif",
        isModem=False,
        description="Wi-Fi + BLE",
        active=True,
        createdAt=datetime(2025, 1, 15, tzinfo=timezone.utc),
        updatedAt=datetime(2025, 1, 15, tzinfo=timezone.utc),
    )

    with patch("src.api.v2.products.chipsets.log_audit"):
        response = authed_client.post(
            "/v2/products/chipsets",
            data=json.dumps({
                "name": "ESP32",
                "manufacturer": "Espressif",
                "isModem": False,
                "description": "Wi-Fi + BLE",
            }),
        )

    assert response.status_code == 201
    data = json.loads(response.data)
    assert data["data"]["name"] == "ESP32"
    assert data["data"]["id"] == "chip-new"


def test_create_chipset_duplicate_name(authed_client, mock_db):
    """Test creating a chipset with duplicate name returns 409."""
    mock_db.chipset.find_unique.return_value = make_obj(
        id="existing-chip",
        name="nRF52840",
    )

    response = authed_client.post(
        "/v2/products/chipsets",
        data=json.dumps({"name": "nRF52840"}),
    )

    assert response.status_code == 409


def test_create_chipset_missing_name(authed_client, mock_db):
    """Test creating chipset with missing name returns 400."""
    response = authed_client.post(
        "/v2/products/chipsets",
        data=json.dumps({}),
    )

    assert response.status_code == 400


def test_get_chipset(authed_client, mock_db):
    """Test getting a single chipset."""
    mock_db.chipset.find_unique.return_value = make_obj(
        id="chip-123",
        name="nRF9151",
        manufacturer="Nordic Semiconductor",
        isModem=True,
        description="LTE modem SiP",
        active=True,
        createdAt=datetime(2025, 1, 10, tzinfo=timezone.utc),
        updatedAt=datetime(2025, 1, 11, tzinfo=timezone.utc),
    )

    response = authed_client.get("/v2/products/chipsets/chip-123")
    assert response.status_code == 200

    data = json.loads(response.data)
    assert data["data"]["id"] == "chip-123"
    assert data["data"]["name"] == "nRF9151"
    assert data["data"]["isModem"] is True


def test_get_chipset_not_found(authed_client, mock_db):
    """Test getting a non-existent chipset returns 404."""
    mock_db.chipset.find_unique.return_value = None

    response = authed_client.get("/v2/products/chipsets/nonexistent")
    assert response.status_code == 404


def test_update_chipset(authed_client, mock_db):
    """Test updating an existing chipset."""
    existing = make_obj(
        id="chip-update",
        name="nRF52840",
        manufacturer="Nordic",
        isModem=False,
        description=None,
        active=True,
        createdAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
        updatedAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
    )
    mock_db.chipset.find_unique.return_value = existing

    mock_db.chipset.update.return_value = make_obj(
        id="chip-update",
        name="nRF52840",
        manufacturer="Nordic Semiconductor",
        isModem=False,
        description="BLE SoC",
        active=True,
        createdAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
        updatedAt=datetime(2025, 1, 15, tzinfo=timezone.utc),
    )

    with patch("src.api.v2.products.chipsets.log_audit"):
        response = authed_client.put(
            "/v2/products/chipsets/chip-update",
            data=json.dumps({
                "manufacturer": "Nordic Semiconductor",
                "description": "BLE SoC",
            }),
        )

    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["data"]["manufacturer"] == "Nordic Semiconductor"
    assert data["data"]["description"] == "BLE SoC"


def test_delete_chipset(authed_client, mock_db):
    """Test deleting a chipset with no references."""
    mock_db.chipset.find_unique.return_value = make_obj(
        id="chip-delete",
        name="Old Chipset",
        manufacturer=None,
        isModem=False,
        description=None,
        active=True,
        createdAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
        updatedAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
    )

    # No references in board revision chipsets or firmware builds
    mock_db.boardrevisionchipset.find_first.return_value = None
    mock_db.firmwarebuild.find_first.return_value = None

    with patch("src.api.v2.products.chipsets.log_audit"):
        response = authed_client.delete("/v2/products/chipsets/chip-delete")

    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["data"]["deleted"] is True


def test_delete_chipset_in_use_by_board_revision(authed_client, mock_db):
    """Test deleting a chipset used by board revisions returns 409."""
    mock_db.chipset.find_unique.return_value = make_obj(
        id="chip-in-use",
        name="nRF52840",
        manufacturer="Nordic",
        isModem=False,
        description=None,
        active=True,
        createdAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
        updatedAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
    )

    # Reference exists in board revision chipsets
    mock_db.boardrevisionchipset.find_first.return_value = make_obj(
        id="brc-1",
        boardRevisionId="rev-1",
        chipsetId="chip-in-use",
    )

    response = authed_client.delete("/v2/products/chipsets/chip-in-use")
    assert response.status_code == 409


def test_delete_chipset_in_use_by_firmware_build(authed_client, mock_db):
    """Test deleting a chipset used by firmware builds returns 409."""
    mock_db.chipset.find_unique.return_value = make_obj(
        id="chip-in-use",
        name="nRF9160",
        manufacturer="Nordic",
        isModem=True,
        description=None,
        active=True,
        createdAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
        updatedAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
    )

    # No board revision chipset reference
    mock_db.boardrevisionchipset.find_first.return_value = None
    # But firmware build reference exists
    mock_db.firmwarebuild.find_first.return_value = make_obj(
        id="build-1",
        chipsetId="chip-in-use",
    )

    response = authed_client.delete("/v2/products/chipsets/chip-in-use")
    assert response.status_code == 409


def test_update_chipset_no_fields(authed_client, mock_db):
    """Test updating a chipset with no fields returns 400."""
    response = authed_client.put(
        "/v2/products/chipsets/chip-1",
        data=json.dumps({}),
    )

    assert response.status_code == 400


def test_update_chipset_duplicate_name(authed_client, mock_db):
    """Test updating a chipset to a duplicate name returns 409."""
    existing = make_obj(
        id="chip-update",
        name="nRF52840",
        manufacturer="Nordic",
        isModem=False,
        description=None,
        active=True,
        createdAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
        updatedAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
    )
    dup = make_obj(
        id="other",
        name="nRF9160",
    )

    mock_db.chipset.find_unique.side_effect = [existing, dup]

    with patch("src.api.v2.products.chipsets.log_audit"):
        response = authed_client.put(
            "/v2/products/chipsets/chip-update",
            data=json.dumps({"name": "nRF9160"}),
        )

    assert response.status_code == 409
