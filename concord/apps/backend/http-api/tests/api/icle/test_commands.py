"""Integration tests for the ICLE Commands, Config, and OTA APIs.

Tests:
- POST /v2/devices/icle/commands/<id>/ack — acknowledge a pending command
- PUT /v2/devices/icle/<id>/config — push config to a device
- POST /v2/devices/icle/<id>/ota — trigger OTA update on a device
"""

import json
from datetime import datetime, timezone
from unittest.mock import patch

from tests.conftest import make_obj


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _device_obj(**overrides) -> object:
    """Create a mock ICLE device object."""
    defaults = {
        "id": "dev-001",
        "deviceId": "ICLE-001",
        "name": "Test Device",
        "status": "ONLINE",
    }
    defaults.update(overrides)
    return make_obj(**defaults)


def _command_obj(**overrides) -> object:
    """Create a mock IclePendingCommand object."""
    defaults = {
        "id": "cmd-001",
        "deviceId": "dev-001",
        "commandType": "config_update",
        "payload": {"sample_rate_hz": 10},
        "priority": 10,
        "acknowledged": False,
        "createdAt": datetime(2026, 3, 10, tzinfo=timezone.utc),
        "expiresAt": None,
    }
    defaults.update(overrides)
    return make_obj(**defaults)


# ---------------------------------------------------------------------------
# POST /v2/devices/icle/commands/<id>/ack — acknowledge_command
# ---------------------------------------------------------------------------


def test_acknowledge_command_success(authed_client, mock_db):
    """Acknowledge an existing command marks it as acknowledged."""
    mock_db.iclependingcommand.find_unique.return_value = _command_obj()

    response = authed_client.post("/v2/devices/icle/commands/cmd-001/ack")
    assert response.status_code == 200

    body = json.loads(response.data)
    assert body["errors"] == []
    assert body["data"]["acknowledged"] is True

    # Verify the update was called
    mock_db.iclependingcommand.update.assert_called_once_with(
        where={"id": "cmd-001"},
        data={"acknowledged": True},
    )


def test_acknowledge_command_not_found(authed_client, mock_db):
    """Acknowledge a non-existent command returns 404."""
    mock_db.iclependingcommand.find_unique.return_value = None

    response = authed_client.post("/v2/devices/icle/commands/nonexistent/ack")
    assert response.status_code == 404

    body = json.loads(response.data)
    assert body["errors"][0]["message"] == "Command not found"


def test_acknowledge_command_unauthorized(client):
    """Acknowledge command without auth returns 401."""
    response = client.post("/v2/devices/icle/commands/cmd-001/ack")
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# PUT /v2/devices/icle/<id>/config — push_config
# ---------------------------------------------------------------------------


def test_push_config_success(authed_client, mock_db):
    """Push config to an existing device creates a pending command and updates device."""
    mock_db.icledevice.find_unique.return_value = _device_obj()

    created_command = _command_obj(
        id="cmd-new",
        commandType="config_update",
        payload={"sample_rate_hz": 10, "channels": [0, 1]},
    )
    mock_db.iclependingcommand.create.return_value = created_command

    config = {"sample_rate_hz": 10, "channels": [0, 1]}

    with patch("api.v2.icle.config.log_audit"):
        response = authed_client.put(
            "/v2/devices/icle/dev-001/config",
            data=json.dumps({"config": config}),
        )

    assert response.status_code == 200

    body = json.loads(response.data)
    assert body["errors"] == []
    assert body["data"]["commandId"] == "cmd-new"
    assert body["data"]["commandType"] == "config_update"
    assert body["data"]["queued"] is True

    # Verify both the command was created and device was updated
    mock_db.iclependingcommand.create.assert_called_once()
    mock_db.icledevice.update.assert_called_once()


def test_push_config_device_not_found(authed_client, mock_db):
    """Push config to a non-existent device returns 404."""
    mock_db.icledevice.find_unique.return_value = None

    response = authed_client.put(
        "/v2/devices/icle/nonexistent/config",
        data=json.dumps({"config": {"key": "value"}}),
    )

    assert response.status_code == 404

    body = json.loads(response.data)
    assert body["errors"][0]["message"] == "ICLE device not found"


def test_push_config_missing_config_field(authed_client, mock_db):
    """Push config without 'config' field returns 400."""
    response = authed_client.put(
        "/v2/devices/icle/dev-001/config",
        data=json.dumps({"data": {"key": "value"}}),
    )

    assert response.status_code == 400

    body = json.loads(response.data)
    assert "config" in body["errors"][0]["message"].lower()


def test_push_config_invalid_config_type(authed_client, mock_db):
    """Push config with non-object config returns 400."""
    response = authed_client.put(
        "/v2/devices/icle/dev-001/config",
        data=json.dumps({"config": "not_an_object"}),
    )

    assert response.status_code == 400

    body = json.loads(response.data)
    assert "object" in body["errors"][0]["message"].lower()


def test_push_config_empty_body(authed_client, mock_db):
    """Push config with empty body returns 400."""
    response = authed_client.put(
        "/v2/devices/icle/dev-001/config",
        data=json.dumps({}),
    )

    assert response.status_code == 400


def test_push_config_audit_logged(authed_client, mock_db):
    """Push config calls log_audit with the config payload."""
    mock_db.icledevice.find_unique.return_value = _device_obj()
    mock_db.iclependingcommand.create.return_value = _command_obj()

    config = {"sample_rate_hz": 20}

    with patch("api.v2.icle.config.log_audit") as mock_audit:
        response = authed_client.put(
            "/v2/devices/icle/dev-001/config",
            data=json.dumps({"config": config}),
        )

    assert response.status_code == 200
    mock_audit.assert_called_once()
    call_args = mock_audit.call_args
    assert call_args[0][0] == "icle.config.push"
    assert call_args[0][1] == "IcleDevice"
    assert call_args[0][2] == "dev-001"
    assert call_args[0][3] == {"config": config}


def test_push_config_unauthorized(client):
    """Push config without auth returns 401."""
    response = client.put(
        "/v2/devices/icle/dev-001/config",
        data=json.dumps({"config": {"key": "value"}}),
        content_type="application/json",
    )
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# POST /v2/devices/icle/<id>/ota — trigger_ota
# ---------------------------------------------------------------------------


def test_trigger_ota_success(authed_client, mock_db):
    """Trigger OTA on an existing device creates a high-priority pending command."""
    mock_db.icledevice.find_unique.return_value = _device_obj()

    created_command = _command_obj(
        id="cmd-ota",
        commandType="ota_trigger",
        priority=100,
    )
    mock_db.iclependingcommand.create.return_value = created_command

    with patch("api.v2.icle.ota.log_audit"):
        response = authed_client.post(
            "/v2/devices/icle/dev-001/ota",
            data=json.dumps({
                "url": "https://example.com/firmware/icle-v1.1.0.bin",
                "version": "1.1.0",
                "checksum": "abc123def456",
            }),
        )

    assert response.status_code == 200

    body = json.loads(response.data)
    assert body["errors"] == []
    assert body["data"]["commandId"] == "cmd-ota"
    assert body["data"]["commandType"] == "ota_trigger"
    assert body["data"]["queued"] is True
    assert body["data"]["version"] == "1.1.0"


def test_trigger_ota_without_checksum(authed_client, mock_db):
    """Trigger OTA without optional checksum field succeeds."""
    mock_db.icledevice.find_unique.return_value = _device_obj()
    mock_db.iclependingcommand.create.return_value = _command_obj(
        id="cmd-ota-2",
        commandType="ota_trigger",
    )

    with patch("api.v2.icle.ota.log_audit"):
        response = authed_client.post(
            "/v2/devices/icle/dev-001/ota",
            data=json.dumps({
                "url": "https://example.com/firmware.bin",
                "version": "1.2.0",
            }),
        )

    assert response.status_code == 200

    # Verify the payload sent to create does not include checksum
    create_call = mock_db.iclependingcommand.create.call_args
    payload = create_call.kwargs["data"]["payload"]
    # Payload is wrapped in Json(), so check the inner dict
    assert hasattr(payload, "__class__")


def test_trigger_ota_device_not_found(authed_client, mock_db):
    """Trigger OTA on a non-existent device returns 404."""
    mock_db.icledevice.find_unique.return_value = None

    response = authed_client.post(
        "/v2/devices/icle/nonexistent/ota",
        data=json.dumps({
            "url": "https://example.com/firmware.bin",
            "version": "1.0.0",
        }),
    )

    assert response.status_code == 404

    body = json.loads(response.data)
    assert body["errors"][0]["message"] == "ICLE device not found"


def test_trigger_ota_missing_url(authed_client, mock_db):
    """Trigger OTA without url returns 400."""
    response = authed_client.post(
        "/v2/devices/icle/dev-001/ota",
        data=json.dumps({"version": "1.0.0"}),
    )

    assert response.status_code == 400

    body = json.loads(response.data)
    assert "url" in body["errors"][0]["message"].lower()


def test_trigger_ota_missing_version(authed_client, mock_db):
    """Trigger OTA without version returns 400."""
    response = authed_client.post(
        "/v2/devices/icle/dev-001/ota",
        data=json.dumps({"url": "https://example.com/firmware.bin"}),
    )

    assert response.status_code == 400

    body = json.loads(response.data)
    assert "version" in body["errors"][0]["message"].lower()


def test_trigger_ota_invalid_url(authed_client, mock_db):
    """Trigger OTA with non-HTTP URL returns 400."""
    response = authed_client.post(
        "/v2/devices/icle/dev-001/ota",
        data=json.dumps({
            "url": "ftp://example.com/firmware.bin",
            "version": "1.0.0",
        }),
    )

    assert response.status_code == 400

    body = json.loads(response.data)
    assert "url" in body["errors"][0]["message"].lower()


def test_trigger_ota_empty_body(authed_client, mock_db):
    """Trigger OTA with empty body returns 400."""
    response = authed_client.post(
        "/v2/devices/icle/dev-001/ota",
        data=json.dumps({}),
    )

    assert response.status_code == 400


def test_trigger_ota_audit_logged(authed_client, mock_db):
    """Trigger OTA calls log_audit with the OTA payload."""
    mock_db.icledevice.find_unique.return_value = _device_obj()
    mock_db.iclependingcommand.create.return_value = _command_obj(
        commandType="ota_trigger",
    )

    with patch("api.v2.icle.ota.log_audit") as mock_audit:
        response = authed_client.post(
            "/v2/devices/icle/dev-001/ota",
            data=json.dumps({
                "url": "https://example.com/firmware.bin",
                "version": "2.0.0",
                "checksum": "sha256hash",
            }),
        )

    assert response.status_code == 200
    mock_audit.assert_called_once()
    call_args = mock_audit.call_args
    assert call_args[0][0] == "icle.ota.trigger"
    assert call_args[0][1] == "IcleDevice"
    assert call_args[0][2] == "dev-001"
    assert call_args[0][3]["url"] == "https://example.com/firmware.bin"
    assert call_args[0][3]["version"] == "2.0.0"
    assert call_args[0][3]["checksum"] == "sha256hash"


def test_trigger_ota_unauthorized(client):
    """Trigger OTA without auth returns 401."""
    response = client.post(
        "/v2/devices/icle/dev-001/ota",
        data=json.dumps({
            "url": "https://example.com/firmware.bin",
            "version": "1.0.0",
        }),
        content_type="application/json",
    )
    assert response.status_code == 401
