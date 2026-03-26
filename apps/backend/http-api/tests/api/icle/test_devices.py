"""Integration tests for the ICLE Devices API.

Tests CRUD operations for ICLE device management:
- GET /v2/devices/icle — list with pagination and filters
- GET /v2/devices/icle/<id> — get single device with pending commands
- PUT /v2/devices/icle/<id> — update device fields
- DELETE /v2/devices/icle/<id> — delete device
"""

import json
from datetime import datetime, timezone
from unittest.mock import patch

from tests.conftest import make_obj


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _device_defaults(**overrides) -> dict:
    """Common ICLE device fields for test mocks."""
    defaults = {
        "id": "dev-001",
        "deviceId": "ICLE-001",
        "name": "Test ICLE Device",
        "ipAddress": "192.168.1.100",
        "macAddress": "AA:BB:CC:DD:EE:FF",
        "firmwareVersion": "1.0.0",
        "status": "ONLINE",
        "registered": True,
        "lastHeartbeat": datetime(2026, 3, 10, 12, 0, 0, tzinfo=timezone.utc),
        "lastStatusData": {"uptimeSeconds": 3600},
        "pendingConfig": None,
        "metadata": {},
        "createdAt": datetime(2026, 3, 1, tzinfo=timezone.utc),
        "updatedAt": datetime(2026, 3, 10, tzinfo=timezone.utc),
    }
    defaults.update(overrides)
    return defaults


# ---------------------------------------------------------------------------
# GET /v2/devices/icle — list_devices
# ---------------------------------------------------------------------------


def test_list_icle_devices_success(authed_client, mock_db):
    """List ICLE devices returns paginated list of devices."""
    mock_db.icledevice.count.return_value = 2
    mock_db.icledevice.find_many.return_value = [
        make_obj(**_device_defaults(id="dev-001", deviceId="ICLE-001")),
        make_obj(**_device_defaults(id="dev-002", deviceId="ICLE-002", name="Second Device")),
    ]

    response = authed_client.get("/v2/devices/icle")
    assert response.status_code == 200

    body = json.loads(response.data)
    assert "data" in body
    assert "errors" in body
    assert len(body["errors"]) == 0

    result = body["data"]
    assert isinstance(result["data"], list)
    assert len(result["data"]) == 2
    assert result["data"][0]["deviceId"] == "ICLE-001"
    assert result["data"][1]["deviceId"] == "ICLE-002"

    # Pagination metadata
    assert result["pagination"]["page"] == 1
    assert result["pagination"]["total"] == 2


def test_list_icle_devices_empty(authed_client, mock_db):
    """List ICLE devices returns empty list when no devices exist."""
    mock_db.icledevice.count.return_value = 0
    mock_db.icledevice.find_many.return_value = []

    response = authed_client.get("/v2/devices/icle")
    assert response.status_code == 200

    body = json.loads(response.data)
    result = body["data"]
    assert result["data"] == []
    assert result["pagination"]["total"] == 0
    assert result["pagination"]["pages"] == 1


def test_list_icle_devices_pagination(authed_client, mock_db):
    """List ICLE devices respects page and limit parameters."""
    mock_db.icledevice.count.return_value = 150
    mock_db.icledevice.find_many.return_value = [
        make_obj(**_device_defaults(id=f"dev-{i}", deviceId=f"ICLE-{i}"))
        for i in range(50)
    ]

    response = authed_client.get("/v2/devices/icle?page=2&limit=50")
    assert response.status_code == 200

    body = json.loads(response.data)
    pagination = body["data"]["pagination"]
    assert pagination["page"] == 2
    assert pagination["total"] == 150
    assert pagination["pages"] == 3
    assert pagination["limit"] == 50

    # Verify skip was calculated correctly (page 2, limit 50 => skip 50)
    call_kwargs = mock_db.icledevice.find_many.call_args
    assert call_kwargs.kwargs["skip"] == 50
    assert call_kwargs.kwargs["take"] == 50


def test_list_icle_devices_filter_by_status(authed_client, mock_db):
    """List ICLE devices filters by status query parameter."""
    mock_db.icledevice.count.return_value = 1
    mock_db.icledevice.find_many.return_value = [
        make_obj(**_device_defaults(status="LOGGING")),
    ]

    response = authed_client.get("/v2/devices/icle?status=logging")
    assert response.status_code == 200

    # Verify the where clause was passed with uppercased status
    call_kwargs = mock_db.icledevice.find_many.call_args
    assert call_kwargs.kwargs["where"]["status"] == "LOGGING"


def test_list_icle_devices_filter_by_registered(authed_client, mock_db):
    """List ICLE devices filters by registered query parameter."""
    mock_db.icledevice.count.return_value = 1
    mock_db.icledevice.find_many.return_value = [
        make_obj(**_device_defaults(registered=False)),
    ]

    response = authed_client.get("/v2/devices/icle?registered=false")
    assert response.status_code == 200

    call_kwargs = mock_db.icledevice.find_many.call_args
    assert call_kwargs.kwargs["where"]["registered"] is False


def test_list_icle_devices_limit_capped_at_100(authed_client, mock_db):
    """List ICLE devices caps the limit parameter at 100."""
    mock_db.icledevice.count.return_value = 0
    mock_db.icledevice.find_many.return_value = []

    response = authed_client.get("/v2/devices/icle?limit=500")
    assert response.status_code == 200

    call_kwargs = mock_db.icledevice.find_many.call_args
    assert call_kwargs.kwargs["take"] == 100


def test_list_icle_devices_unauthorized(client):
    """List ICLE devices without auth returns 401."""
    response = client.get("/v2/devices/icle")
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# GET /v2/devices/icle/<id> — get_device
# ---------------------------------------------------------------------------


def test_get_icle_device_success(authed_client, mock_db):
    """Get a single ICLE device by ID returns full device data with pending commands."""
    mock_cmd = make_obj(
        id="cmd-001",
        commandType="config_update",
        payload={"sample_rate_hz": 10},
        priority=10,
        createdAt=datetime(2026, 3, 10, 12, 0, 0, tzinfo=timezone.utc),
        expiresAt=None,
        acknowledged=False,
    )
    mock_db.icledevice.find_unique.return_value = make_obj(
        **_device_defaults(),
        commands=[mock_cmd],
    )

    response = authed_client.get("/v2/devices/icle/dev-001")
    assert response.status_code == 200

    body = json.loads(response.data)
    assert body["errors"] == []
    device = body["data"]
    assert device["id"] == "dev-001"
    assert device["deviceId"] == "ICLE-001"
    assert device["firmwareVersion"] == "1.0.0"
    assert device["status"] == "ONLINE"
    assert device["registered"] is True

    # Pending commands included
    assert "pendingCommands" in device
    assert len(device["pendingCommands"]) == 1
    assert device["pendingCommands"][0]["commandType"] == "config_update"


def test_get_icle_device_no_commands(authed_client, mock_db):
    """Get a single ICLE device with no pending commands omits the commands key."""
    mock_db.icledevice.find_unique.return_value = make_obj(
        **_device_defaults(),
        commands=[],
    )

    response = authed_client.get("/v2/devices/icle/dev-001")
    assert response.status_code == 200

    body = json.loads(response.data)
    device = body["data"]
    assert device["id"] == "dev-001"
    # Empty commands list means pendingCommands should not be in the result
    # (the serializer only includes it when commands is truthy)
    assert "pendingCommands" not in device


def test_get_icle_device_not_found(authed_client, mock_db):
    """Get a non-existent ICLE device returns 404."""
    mock_db.icledevice.find_unique.return_value = None

    response = authed_client.get("/v2/devices/icle/nonexistent")
    assert response.status_code == 404

    body = json.loads(response.data)
    assert len(body["errors"]) > 0
    assert body["errors"][0]["message"] == "ICLE device not found"


def test_get_icle_device_unauthorized(client):
    """Get ICLE device without auth returns 401."""
    response = client.get("/v2/devices/icle/dev-001")
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# PUT /v2/devices/icle/<id> — update_device
# ---------------------------------------------------------------------------


def test_update_icle_device_success(authed_client, mock_db):
    """Update an ICLE device returns the updated device data."""
    existing = make_obj(**_device_defaults())
    updated = make_obj(**_device_defaults(name="Renamed Device", registered=False))

    mock_db.icledevice.find_unique.return_value = existing
    mock_db.icledevice.update.return_value = updated

    with patch("api.v2.icle.devices.log_audit"):
        response = authed_client.put(
            "/v2/devices/icle/dev-001",
            data=json.dumps({"name": "Renamed Device", "registered": False}),
        )

    assert response.status_code == 200

    body = json.loads(response.data)
    assert body["errors"] == []
    assert body["data"]["name"] == "Renamed Device"
    assert body["data"]["registered"] is False


def test_update_icle_device_pending_config(authed_client, mock_db):
    """Update an ICLE device with pendingConfig stores the config object."""
    existing = make_obj(**_device_defaults())
    config = {"sample_rate_hz": 20, "channels": [0, 1]}
    updated = make_obj(**_device_defaults(pendingConfig=config))

    mock_db.icledevice.find_unique.return_value = existing
    mock_db.icledevice.update.return_value = updated

    with patch("api.v2.icle.devices.log_audit"):
        response = authed_client.put(
            "/v2/devices/icle/dev-001",
            data=json.dumps({"pendingConfig": config}),
        )

    assert response.status_code == 200

    body = json.loads(response.data)
    assert body["data"]["pendingConfig"] == config


def test_update_icle_device_not_found(authed_client, mock_db):
    """Update a non-existent ICLE device returns 404."""
    mock_db.icledevice.find_unique.return_value = None

    response = authed_client.put(
        "/v2/devices/icle/nonexistent",
        data=json.dumps({"name": "New Name"}),
    )

    assert response.status_code == 404

    body = json.loads(response.data)
    assert body["errors"][0]["message"] == "ICLE device not found"


def test_update_icle_device_no_fields(authed_client, mock_db):
    """Update an ICLE device with no update fields returns 400."""
    mock_db.icledevice.find_unique.return_value = make_obj(**_device_defaults())

    response = authed_client.put(
        "/v2/devices/icle/dev-001",
        data=json.dumps({"someUnknownField": "value"}),
    )

    assert response.status_code == 400

    body = json.loads(response.data)
    assert len(body["errors"]) > 0


def test_update_icle_device_empty_body(authed_client, mock_db):
    """Update an ICLE device with empty body returns 400."""
    response = authed_client.put(
        "/v2/devices/icle/dev-001",
        data=json.dumps({}),
    )

    assert response.status_code == 400


def test_update_icle_device_invalid_registered(authed_client, mock_db):
    """Update an ICLE device with non-boolean registered returns 400."""
    response = authed_client.put(
        "/v2/devices/icle/dev-001",
        data=json.dumps({"registered": "yes"}),
    )

    assert response.status_code == 400

    body = json.loads(response.data)
    assert "registered" in body["errors"][0]["message"].lower()


def test_update_icle_device_name_too_long(authed_client, mock_db):
    """Update an ICLE device with name exceeding 255 characters returns 400."""
    response = authed_client.put(
        "/v2/devices/icle/dev-001",
        data=json.dumps({"name": "x" * 256}),
    )

    assert response.status_code == 400


def test_update_icle_device_audit_logged(authed_client, mock_db):
    """Update an ICLE device calls log_audit with correct parameters."""
    existing = make_obj(**_device_defaults())
    updated = make_obj(**_device_defaults(name="Audited Name"))

    mock_db.icledevice.find_unique.return_value = existing
    mock_db.icledevice.update.return_value = updated

    with patch("api.v2.icle.devices.log_audit") as mock_audit:
        response = authed_client.put(
            "/v2/devices/icle/dev-001",
            data=json.dumps({"name": "Audited Name"}),
        )

    assert response.status_code == 200
    mock_audit.assert_called_once()
    call_args = mock_audit.call_args
    assert call_args[0][0] == "icle.device.update"
    assert call_args[0][1] == "IcleDevice"
    assert call_args[0][2] == "dev-001"


def test_update_icle_device_unauthorized(client):
    """Update ICLE device without auth returns 401."""
    response = client.put(
        "/v2/devices/icle/dev-001",
        data=json.dumps({"name": "New Name"}),
        content_type="application/json",
    )
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# DELETE /v2/devices/icle/<id> — delete_device
# ---------------------------------------------------------------------------


def test_delete_icle_device_success(authed_client, mock_db):
    """Delete an existing ICLE device returns success with null data."""
    mock_db.icledevice.find_unique.return_value = make_obj(**_device_defaults())

    with patch("api.v2.icle.devices.log_audit"):
        response = authed_client.delete("/v2/devices/icle/dev-001")

    assert response.status_code == 200

    body = json.loads(response.data)
    assert body["errors"] == []
    assert body["data"] is None

    # Verify delete was called
    mock_db.icledevice.delete.assert_called_once_with(where={"id": "dev-001"})


def test_delete_icle_device_not_found(authed_client, mock_db):
    """Delete a non-existent ICLE device returns 404."""
    mock_db.icledevice.find_unique.return_value = None

    response = authed_client.delete("/v2/devices/icle/nonexistent")
    assert response.status_code == 404

    body = json.loads(response.data)
    assert body["errors"][0]["message"] == "ICLE device not found"


def test_delete_icle_device_audit_logged(authed_client, mock_db):
    """Delete an ICLE device calls log_audit with the device's deviceId."""
    mock_db.icledevice.find_unique.return_value = make_obj(**_device_defaults())

    with patch("api.v2.icle.devices.log_audit") as mock_audit:
        response = authed_client.delete("/v2/devices/icle/dev-001")

    assert response.status_code == 200
    mock_audit.assert_called_once()
    call_args = mock_audit.call_args
    assert call_args[0][0] == "icle.device.delete"
    assert call_args[0][1] == "IcleDevice"
    assert call_args[0][2] == "dev-001"
    assert call_args[0][3] == {"deviceId": "ICLE-001"}


def test_delete_icle_device_unauthorized(client):
    """Delete ICLE device without auth returns 401."""
    response = client.delete("/v2/devices/icle/dev-001")
    assert response.status_code == 401
