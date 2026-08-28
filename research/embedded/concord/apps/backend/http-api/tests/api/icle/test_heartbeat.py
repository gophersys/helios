"""Integration tests for the ICLE Heartbeat API.

Tests device heartbeat/discovery endpoint:
- POST /v2/devices/icle/heartbeat — upsert device, return pending commands
"""

import json
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from tests.conftest import make_obj


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _heartbeat_payload(**overrides) -> dict:
    """Minimal valid heartbeat request payload."""
    defaults = {
        "device_id": "ICLE-001",
        "firmware_version": "1.0.0",
        "ip_address": "192.168.1.100",
        "mac_address": "AA:BB:CC:DD:EE:FF",
        "status": "online",
    }
    defaults.update(overrides)
    return defaults


def _device_obj(**overrides) -> object:
    """Create a mock ICLE device object for upsert return."""
    defaults = {
        "id": "dev-001",
        "deviceId": "ICLE-001",
        "name": None,
        "ipAddress": "192.168.1.100",
        "macAddress": "AA:BB:CC:DD:EE:FF",
        "firmwareVersion": "1.0.0",
        "status": "ONLINE",
        "registered": False,
        "lastHeartbeat": datetime(2026, 3, 10, 12, 0, 0, tzinfo=timezone.utc),
        "lastStatusData": {},
    }
    defaults.update(overrides)
    return make_obj(**defaults)


# ---------------------------------------------------------------------------
# POST /v2/devices/icle/heartbeat — heartbeat (no auth)
# ---------------------------------------------------------------------------


def test_heartbeat_new_device(client, mock_db):
    """Heartbeat from a new device creates it via upsert and returns response."""
    mock_db.icledevice.upsert = MagicMock(
        return_value=_device_obj(registered=False)
    )
    mock_db.iclependingcommand.find_many.return_value = []

    response = client.post(
        "/v2/devices/icle/heartbeat",
        data=json.dumps(_heartbeat_payload()),
        content_type="application/json",
    )
    assert response.status_code == 200

    body = json.loads(response.data)
    assert body["errors"] == []

    data = body["data"]
    assert data["acknowledged"] is True
    assert data["registered"] is False
    assert data["heartbeat_interval_ms"] == 5000
    assert "server_time" in data
    assert data["pending_commands"] == []


def test_heartbeat_existing_device(client, mock_db):
    """Heartbeat from a registered device returns registered=True."""
    mock_db.icledevice.upsert = MagicMock(
        return_value=_device_obj(registered=True)
    )
    mock_db.iclependingcommand.find_many.return_value = []

    response = client.post(
        "/v2/devices/icle/heartbeat",
        data=json.dumps(_heartbeat_payload()),
        content_type="application/json",
    )
    assert response.status_code == 200

    body = json.loads(response.data)
    assert body["data"]["registered"] is True


def test_heartbeat_with_pending_commands(client, mock_db):
    """Heartbeat returns pending commands for the device."""
    mock_db.icledevice.upsert = MagicMock(
        return_value=_device_obj(id="dev-001")
    )
    mock_db.iclependingcommand.find_many.return_value = [
        make_obj(
            id="cmd-001",
            commandType="config_update",
            payload={"sample_rate_hz": 10},
        ),
        make_obj(
            id="cmd-002",
            commandType="ota_trigger",
            payload={"url": "https://example.com/fw.bin", "version": "1.1.0"},
        ),
    ]

    response = client.post(
        "/v2/devices/icle/heartbeat",
        data=json.dumps(_heartbeat_payload()),
        content_type="application/json",
    )
    assert response.status_code == 200

    body = json.loads(response.data)
    cmds = body["data"]["pending_commands"]
    assert len(cmds) == 2
    assert cmds[0]["id"] == "cmd-001"
    assert cmds[0]["type"] == "config_update"
    assert cmds[1]["id"] == "cmd-002"
    assert cmds[1]["type"] == "ota_trigger"


def test_heartbeat_with_full_status_data(client, mock_db):
    """Heartbeat with all optional status fields passes them to upsert."""
    mock_db.icledevice.upsert = MagicMock(return_value=_device_obj())
    mock_db.iclependingcommand.find_many.return_value = []

    payload = _heartbeat_payload(
        status="logging",
        uptime_seconds=7200,
        free_heap_bytes=98304,
        wifi_rssi=-55,
        sd_card_free_mb=2048,
        current_log_file="log_003.bin",
        power_readings=[
            {"channel": 0, "voltage_mv": 3300, "current_ma": 150, "power_mw": 495},
            {"channel": 1, "voltage_mv": 5000, "current_ma": 25, "power_mw": 125},
        ],
    )

    response = client.post(
        "/v2/devices/icle/heartbeat",
        data=json.dumps(payload),
        content_type="application/json",
    )
    assert response.status_code == 200

    # Verify upsert was called with correct status
    call_kwargs = mock_db.icledevice.upsert.call_args
    create_data = call_kwargs.kwargs["data"]["create"]
    assert create_data["status"] == "LOGGING"


def test_heartbeat_missing_device_id(client, mock_db):
    """Heartbeat without device_id returns 400."""
    payload = {"firmware_version": "1.0.0"}

    response = client.post(
        "/v2/devices/icle/heartbeat",
        data=json.dumps(payload),
        content_type="application/json",
    )
    assert response.status_code == 400

    body = json.loads(response.data)
    assert len(body["errors"]) > 0
    assert "device_id" in body["errors"][0]["message"].lower()


def test_heartbeat_missing_firmware_version(client, mock_db):
    """Heartbeat without firmware_version returns 400."""
    payload = {"device_id": "ICLE-001"}

    response = client.post(
        "/v2/devices/icle/heartbeat",
        data=json.dumps(payload),
        content_type="application/json",
    )
    assert response.status_code == 400

    body = json.loads(response.data)
    assert "firmware_version" in body["errors"][0]["message"].lower()


def test_heartbeat_empty_body(client, mock_db):
    """Heartbeat with empty body returns 400."""
    response = client.post(
        "/v2/devices/icle/heartbeat",
        data=json.dumps({}),
        content_type="application/json",
    )
    assert response.status_code == 400


def test_heartbeat_invalid_status(client, mock_db):
    """Heartbeat with invalid status value returns 400."""
    payload = _heartbeat_payload(status="invalid_state")

    response = client.post(
        "/v2/devices/icle/heartbeat",
        data=json.dumps(payload),
        content_type="application/json",
    )
    assert response.status_code == 400

    body = json.loads(response.data)
    assert "status" in body["errors"][0]["message"].lower()


def test_heartbeat_camel_case_fields(client, mock_db):
    """Heartbeat accepts camelCase field names as well as snake_case."""
    mock_db.icledevice.upsert = MagicMock(return_value=_device_obj())
    mock_db.iclependingcommand.find_many.return_value = []

    payload = {
        "deviceId": "ICLE-002",
        "firmwareVersion": "2.0.0",
        "ipAddress": "10.0.0.50",
        "macAddress": "11:22:33:44:55:66",
    }

    response = client.post(
        "/v2/devices/icle/heartbeat",
        data=json.dumps(payload),
        content_type="application/json",
    )
    assert response.status_code == 200


def test_heartbeat_websocket_emit(client, mock_db):
    """Heartbeat emits a WebSocket event with device data."""
    mock_db.icledevice.upsert = MagicMock(return_value=_device_obj())
    mock_db.iclependingcommand.find_many.return_value = []

    with patch("api.v2.icle.heartbeat.emit_icle_update") as mock_emit:
        response = client.post(
            "/v2/devices/icle/heartbeat",
            data=json.dumps(_heartbeat_payload()),
            content_type="application/json",
        )

    assert response.status_code == 200
    mock_emit.assert_called_once()

    emitted_data = mock_emit.call_args[0][0]
    assert emitted_data["deviceId"] == "ICLE-001"
    assert emitted_data["status"] == "ONLINE"


def test_heartbeat_invalid_uptime_type(client, mock_db):
    """Heartbeat with non-numeric uptime_seconds returns 400."""
    payload = _heartbeat_payload(uptime_seconds="not_a_number")

    response = client.post(
        "/v2/devices/icle/heartbeat",
        data=json.dumps(payload),
        content_type="application/json",
    )
    assert response.status_code == 400


def test_heartbeat_invalid_power_readings_not_list(client, mock_db):
    """Heartbeat with non-list power_readings returns 400."""
    payload = _heartbeat_payload(power_readings="not_a_list")

    response = client.post(
        "/v2/devices/icle/heartbeat",
        data=json.dumps(payload),
        content_type="application/json",
    )
    assert response.status_code == 400

    body = json.loads(response.data)
    assert "power_readings" in body["errors"][0]["message"].lower()


def test_heartbeat_invalid_power_reading_entry(client, mock_db):
    """Heartbeat with non-object entries in power_readings returns 400."""
    payload = _heartbeat_payload(power_readings=["not_an_object"])

    response = client.post(
        "/v2/devices/icle/heartbeat",
        data=json.dumps(payload),
        content_type="application/json",
    )
    assert response.status_code == 400

    body = json.loads(response.data)
    assert "power reading" in body["errors"][0]["message"].lower()


def test_heartbeat_no_json_body(client, mock_db):
    """Heartbeat with no JSON body returns 400."""
    response = client.post(
        "/v2/devices/icle/heartbeat",
        content_type="application/json",
    )
    assert response.status_code == 400
