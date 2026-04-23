"""
Unit tests for ICLE types validation in src/api/v2/icle/types.py.

Tests all from_json() methods and to_update_data() / to_status_data() methods
for HeartbeatRequest, DeviceUpdateRequest, ConfigPushRequest, and OtaTriggerRequest.
"""


# ── HeartbeatRequest ──────────────────────────────────


def test_heartbeat_request_valid_minimal():
    """HeartbeatRequest with only required fields parses successfully."""
    from src.api.v2.icle.types import HeartbeatRequest

    data = {"device_id": "ICLE-001", "firmware_version": "1.0.0"}
    req, err = HeartbeatRequest.from_json(data)

    assert err is None
    assert req is not None
    assert req.device_id == "ICLE-001"
    assert req.firmware_version == "1.0.0"
    assert req.ip_address is None
    assert req.mac_address is None
    assert req.status == "online"
    assert req.uptime_seconds is None
    assert req.free_heap_bytes is None
    assert req.wifi_rssi is None
    assert req.sd_card_free_mb is None
    assert req.current_log_file is None
    assert req.power_readings is None


def test_heartbeat_request_valid_full():
    """HeartbeatRequest with all fields parses correctly."""
    from src.api.v2.icle.types import HeartbeatRequest

    data = {
        "device_id": "ICLE-002",
        "firmware_version": "2.0.0",
        "ip_address": "10.0.0.100",
        "mac_address": "AA:BB:CC:DD:EE:FF",
        "status": "logging",
        "uptime_seconds": 7200,
        "free_heap_bytes": 98304,
        "wifi_rssi": -55,
        "sd_card_free_mb": 2048,
        "current_log_file": "log_005.bin",
        "power_readings": [
            {"channel": 0, "voltage_mv": 3300, "current_ma": 150, "power_mw": 495},
        ],
    }
    req, err = HeartbeatRequest.from_json(data)

    assert err is None
    assert req is not None
    assert req.device_id == "ICLE-002"
    assert req.firmware_version == "2.0.0"
    assert req.ip_address == "10.0.0.100"
    assert req.mac_address == "AA:BB:CC:DD:EE:FF"
    assert req.status == "logging"
    assert req.uptime_seconds == 7200
    assert req.free_heap_bytes == 98304
    assert req.wifi_rssi == -55
    assert req.sd_card_free_mb == 2048
    assert req.current_log_file == "log_005.bin"
    assert len(req.power_readings) == 1
    assert req.power_readings[0].channel == 0
    assert req.power_readings[0].voltage_mv == 3300.0


def test_heartbeat_request_camel_case():
    """HeartbeatRequest accepts camelCase field names."""
    from src.api.v2.icle.types import HeartbeatRequest

    data = {
        "deviceId": "ICLE-003",
        "firmwareVersion": "3.0.0",
        "ipAddress": "192.168.1.50",
        "macAddress": "11:22:33:44:55:66",
        "uptimeSeconds": 100,
        "freeHeapBytes": 50000,
        "wifiRssi": -70,
        "sdCardFreeMb": 512,
        "currentLogFile": "data.csv",
    }
    req, err = HeartbeatRequest.from_json(data)

    assert err is None
    assert req.device_id == "ICLE-003"
    assert req.firmware_version == "3.0.0"
    assert req.ip_address == "192.168.1.50"
    assert req.uptime_seconds == 100
    assert req.free_heap_bytes == 50000
    assert req.wifi_rssi == -70
    assert req.sd_card_free_mb == 512


def test_heartbeat_request_empty_body():
    """HeartbeatRequest with None body returns error."""
    from src.api.v2.icle.types import HeartbeatRequest

    req, err = HeartbeatRequest.from_json(None)
    assert req is None
    assert err == "Request body must contain JSON data"


def test_heartbeat_request_empty_dict():
    """HeartbeatRequest with empty dict returns error for missing device_id."""
    from src.api.v2.icle.types import HeartbeatRequest

    req, err = HeartbeatRequest.from_json({})
    assert req is None
    assert err == "Request body must contain JSON data"


def test_heartbeat_request_missing_device_id():
    """HeartbeatRequest without device_id returns error."""
    from src.api.v2.icle.types import HeartbeatRequest

    data = {"firmware_version": "1.0.0"}
    req, err = HeartbeatRequest.from_json(data)

    assert req is None
    assert err == "Field 'device_id' is required"


def test_heartbeat_request_blank_device_id():
    """HeartbeatRequest with blank device_id returns error."""
    from src.api.v2.icle.types import HeartbeatRequest

    data = {"device_id": "   ", "firmware_version": "1.0.0"}
    req, err = HeartbeatRequest.from_json(data)

    assert req is None
    assert err == "Field 'device_id' is required"


def test_heartbeat_request_missing_firmware_version():
    """HeartbeatRequest without firmware_version returns error."""
    from src.api.v2.icle.types import HeartbeatRequest

    data = {"device_id": "ICLE-001"}
    req, err = HeartbeatRequest.from_json(data)

    assert req is None
    assert err == "Field 'firmware_version' is required"


def test_heartbeat_request_invalid_status():
    """HeartbeatRequest with unknown status returns error."""
    from src.api.v2.icle.types import HeartbeatRequest

    data = {"device_id": "ICLE-001", "firmware_version": "1.0.0", "status": "SLEEPING"}
    req, err = HeartbeatRequest.from_json(data)

    assert req is None
    assert "Invalid status" in err
    assert "sleeping" in err  # lowered input


def test_heartbeat_request_all_valid_statuses():
    """HeartbeatRequest accepts all valid status values."""
    from src.api.v2.icle.types import HeartbeatRequest

    for status in ["online", "offline", "logging", "config", "boot", "ota"]:
        data = {"device_id": "ICLE-001", "firmware_version": "1.0.0", "status": status}
        req, err = HeartbeatRequest.from_json(data)
        assert err is None, f"Status '{status}' should be valid"
        assert req.status == status


def test_heartbeat_request_status_case_insensitive():
    """HeartbeatRequest converts status to lowercase."""
    from src.api.v2.icle.types import HeartbeatRequest

    data = {"device_id": "ICLE-001", "firmware_version": "1.0.0", "status": "ONLINE"}
    req, err = HeartbeatRequest.from_json(data)

    assert err is None
    assert req.status == "online"


def test_heartbeat_request_invalid_uptime_type():
    """HeartbeatRequest with non-numeric uptime_seconds returns error."""
    from src.api.v2.icle.types import HeartbeatRequest

    data = {"device_id": "ICLE-001", "firmware_version": "1.0.0", "uptime_seconds": "abc"}
    req, err = HeartbeatRequest.from_json(data)

    assert req is None
    assert "uptime_seconds" in err


def test_heartbeat_request_invalid_free_heap_type():
    """HeartbeatRequest with non-numeric free_heap_bytes returns error."""
    from src.api.v2.icle.types import HeartbeatRequest

    data = {"device_id": "ICLE-001", "firmware_version": "1.0.0", "free_heap_bytes": "abc"}
    req, err = HeartbeatRequest.from_json(data)

    assert req is None
    assert "free_heap_bytes" in err


def test_heartbeat_request_invalid_wifi_rssi_type():
    """HeartbeatRequest with non-numeric wifi_rssi returns error."""
    from src.api.v2.icle.types import HeartbeatRequest

    data = {"device_id": "ICLE-001", "firmware_version": "1.0.0", "wifi_rssi": "strong"}
    req, err = HeartbeatRequest.from_json(data)

    assert req is None
    assert "wifi_rssi" in err


def test_heartbeat_request_invalid_sd_card_type():
    """HeartbeatRequest with non-numeric sd_card_free_mb returns error."""
    from src.api.v2.icle.types import HeartbeatRequest

    data = {"device_id": "ICLE-001", "firmware_version": "1.0.0", "sd_card_free_mb": "plenty"}
    req, err = HeartbeatRequest.from_json(data)

    assert req is None
    assert "sd_card_free_mb" in err


def test_heartbeat_request_power_readings_not_list():
    """HeartbeatRequest with non-list power_readings returns error."""
    from src.api.v2.icle.types import HeartbeatRequest

    data = {
        "device_id": "ICLE-001",
        "firmware_version": "1.0.0",
        "power_readings": {"channel": 0},
    }
    req, err = HeartbeatRequest.from_json(data)

    assert req is None
    assert "power_readings" in err
    assert "list" in err


def test_heartbeat_request_power_reading_not_object():
    """HeartbeatRequest with non-object power reading entry returns error."""
    from src.api.v2.icle.types import HeartbeatRequest

    data = {
        "device_id": "ICLE-001",
        "firmware_version": "1.0.0",
        "power_readings": [42],
    }
    req, err = HeartbeatRequest.from_json(data)

    assert req is None
    assert "index 0" in err
    assert "object" in err


def test_heartbeat_request_power_readings_camel_case():
    """HeartbeatRequest parses power readings with camelCase field names."""
    from src.api.v2.icle.types import HeartbeatRequest

    data = {
        "device_id": "ICLE-001",
        "firmware_version": "1.0.0",
        "powerReadings": [
            {"channel": 1, "voltageMv": 5000, "currentMa": 25, "powerMw": 125},
        ],
    }
    req, err = HeartbeatRequest.from_json(data)

    assert err is None
    assert len(req.power_readings) == 1
    assert req.power_readings[0].voltage_mv == 5000.0
    assert req.power_readings[0].current_ma == 25.0
    assert req.power_readings[0].power_mw == 125.0


# ── HeartbeatRequest.to_status_data() ────────────────


def test_heartbeat_to_status_data_minimal():
    """to_status_data with only required fields returns minimal dict."""
    from src.api.v2.icle.types import HeartbeatRequest

    req, _ = HeartbeatRequest.from_json({
        "device_id": "ICLE-001",
        "firmware_version": "1.0.0",
    })
    status_data = req.to_status_data()

    assert status_data == {"firmwareVersion": "1.0.0"}


def test_heartbeat_to_status_data_full():
    """to_status_data with all optional fields includes them all."""
    from src.api.v2.icle.types import HeartbeatRequest

    req, _ = HeartbeatRequest.from_json({
        "device_id": "ICLE-001",
        "firmware_version": "1.0.0",
        "uptime_seconds": 3600,
        "free_heap_bytes": 50000,
        "wifi_rssi": -60,
        "sd_card_free_mb": 1024,
        "current_log_file": "log_001.csv",
        "power_readings": [
            {"channel": 0, "voltage_mv": 3300, "current_ma": 100, "power_mw": 330},
        ],
    })
    status_data = req.to_status_data()

    assert status_data["firmwareVersion"] == "1.0.0"
    assert status_data["uptimeSeconds"] == 3600
    assert status_data["freeHeapBytes"] == 50000
    assert status_data["wifiRssi"] == -60
    assert status_data["sdCardFreeMb"] == 1024
    assert status_data["currentLogFile"] == "log_001.csv"
    assert len(status_data["powerReadings"]) == 1
    assert status_data["powerReadings"][0]["channel"] == 0
    assert status_data["powerReadings"][0]["voltageMv"] == 3300.0


# ── DeviceUpdateRequest ──────────────────────────────


def test_device_update_valid_name():
    """DeviceUpdateRequest with name field parses correctly."""
    from src.api.v2.icle.types import DeviceUpdateRequest

    data = {"name": "My ICLE Device"}
    req, err = DeviceUpdateRequest.from_json(data)

    assert err is None
    assert req is not None
    assert req.name == "My ICLE Device"
    assert req._has_name is True


def test_device_update_valid_registered():
    """DeviceUpdateRequest with registered field parses correctly."""
    from src.api.v2.icle.types import DeviceUpdateRequest

    data = {"registered": True}
    req, err = DeviceUpdateRequest.from_json(data)

    assert err is None
    assert req.registered is True
    assert req._has_registered is True


def test_device_update_valid_pending_config():
    """DeviceUpdateRequest with pendingConfig field parses correctly."""
    from src.api.v2.icle.types import DeviceUpdateRequest

    config = {"sample_rate_hz": 10, "channels": [0, 1]}
    data = {"pendingConfig": config}
    req, err = DeviceUpdateRequest.from_json(data)

    assert err is None
    assert req.pending_config == config
    assert req._has_pending_config is True


def test_device_update_pending_config_snake_case():
    """DeviceUpdateRequest accepts pending_config in snake_case."""
    from src.api.v2.icle.types import DeviceUpdateRequest

    config = {"key": "value"}
    data = {"pending_config": config}
    req, err = DeviceUpdateRequest.from_json(data)

    assert err is None
    assert req.pending_config == config
    assert req._has_pending_config is True


def test_device_update_empty_body():
    """DeviceUpdateRequest with None returns error."""
    from src.api.v2.icle.types import DeviceUpdateRequest

    req, err = DeviceUpdateRequest.from_json(None)
    assert req is None
    assert err == "Request body must contain JSON data"


def test_device_update_empty_dict():
    """DeviceUpdateRequest with empty dict returns error."""
    from src.api.v2.icle.types import DeviceUpdateRequest

    req, err = DeviceUpdateRequest.from_json({})
    assert req is None
    assert err == "Request body must contain JSON data"


def test_device_update_invalid_registered_type():
    """DeviceUpdateRequest with non-boolean registered returns error."""
    from src.api.v2.icle.types import DeviceUpdateRequest

    data = {"registered": "yes"}
    req, err = DeviceUpdateRequest.from_json(data)

    assert req is None
    assert "registered" in err
    assert "boolean" in err


def test_device_update_invalid_pending_config_type():
    """DeviceUpdateRequest with non-object pendingConfig returns error."""
    from src.api.v2.icle.types import DeviceUpdateRequest

    data = {"pendingConfig": "not_an_object"}
    req, err = DeviceUpdateRequest.from_json(data)

    assert req is None
    assert "pendingConfig" in err
    assert "object" in err


def test_device_update_name_too_long():
    """DeviceUpdateRequest with name exceeding 255 chars returns error."""
    from src.api.v2.icle.types import DeviceUpdateRequest

    data = {"name": "x" * 256}
    req, err = DeviceUpdateRequest.from_json(data)

    assert req is None
    assert "255" in err


def test_device_update_name_null_clears():
    """DeviceUpdateRequest with name=None sets name to None (clear)."""
    from src.api.v2.icle.types import DeviceUpdateRequest

    data = {"name": None}
    req, err = DeviceUpdateRequest.from_json(data)

    assert err is None
    assert req.name is None
    assert req._has_name is True


def test_device_update_to_update_data():
    """to_update_data returns only explicitly set fields."""
    from src.api.v2.icle.types import DeviceUpdateRequest

    data = {"name": "Updated", "registered": True}
    req, _ = DeviceUpdateRequest.from_json(data)

    update_data = req.to_update_data()
    assert update_data == {"name": "Updated", "registered": True}


def test_device_update_to_update_data_omits_unset():
    """to_update_data omits fields that were not in the request."""
    from src.api.v2.icle.types import DeviceUpdateRequest

    data = {"name": "Only Name"}
    req, _ = DeviceUpdateRequest.from_json(data)

    update_data = req.to_update_data()
    assert "name" in update_data
    assert "registered" not in update_data
    assert "pendingConfig" not in update_data


def test_device_update_to_update_data_empty():
    """to_update_data returns empty dict when no known fields provided."""
    from src.api.v2.icle.types import DeviceUpdateRequest

    # from_json on an empty dict returns an error, so we need a dict with
    # only unknown fields — but from_json validates for empty dict.
    # Instead, test that a valid request with only null-able unchanged fields
    # returns the expected update_data.
    data = {"name": "Test"}
    req, _ = DeviceUpdateRequest.from_json(data)
    # Manually clear the flag to simulate no fields
    req._has_name = False

    update_data = req.to_update_data()
    assert update_data == {}


# ── ConfigPushRequest ─────────────────────────────────


def test_config_push_valid():
    """ConfigPushRequest with a config object parses correctly."""
    from src.api.v2.icle.types import ConfigPushRequest

    data = {"config": {"sample_rate_hz": 10, "channels": [0, 1]}}
    req, err = ConfigPushRequest.from_json(data)

    assert err is None
    assert req is not None
    assert req.config == {"sample_rate_hz": 10, "channels": [0, 1]}


def test_config_push_empty_body():
    """ConfigPushRequest with None body returns error."""
    from src.api.v2.icle.types import ConfigPushRequest

    req, err = ConfigPushRequest.from_json(None)
    assert req is None
    assert err == "Request body must contain JSON data"


def test_config_push_empty_dict():
    """ConfigPushRequest with empty dict returns error."""
    from src.api.v2.icle.types import ConfigPushRequest

    req, err = ConfigPushRequest.from_json({})
    assert req is None
    assert err == "Request body must contain JSON data"


def test_config_push_missing_config():
    """ConfigPushRequest without config field returns error."""
    from src.api.v2.icle.types import ConfigPushRequest

    data = {"data": {"key": "value"}}
    req, err = ConfigPushRequest.from_json(data)

    assert req is None
    assert err == "Field 'config' is required"


def test_config_push_config_not_dict():
    """ConfigPushRequest with non-object config returns error."""
    from src.api.v2.icle.types import ConfigPushRequest

    data = {"config": "not_an_object"}
    req, err = ConfigPushRequest.from_json(data)

    assert req is None
    assert err == "Field 'config' must be an object"


def test_config_push_config_is_list():
    """ConfigPushRequest with list config returns error."""
    from src.api.v2.icle.types import ConfigPushRequest

    data = {"config": [1, 2, 3]}
    req, err = ConfigPushRequest.from_json(data)

    assert req is None
    assert err == "Field 'config' must be an object"


def test_config_push_config_empty_dict():
    """ConfigPushRequest with empty config dict is valid (clears config)."""
    from src.api.v2.icle.types import ConfigPushRequest

    data = {"config": {}}
    req, err = ConfigPushRequest.from_json(data)

    assert err is None
    assert req.config == {}


# ── OtaTriggerRequest ─────────────────────────────────


def test_ota_trigger_valid():
    """OtaTriggerRequest with all fields parses correctly."""
    from src.api.v2.icle.types import OtaTriggerRequest

    data = {
        "url": "https://example.com/firmware/icle-v1.1.0.bin",
        "version": "1.1.0",
        "checksum": "abc123def456",
    }
    req, err = OtaTriggerRequest.from_json(data)

    assert err is None
    assert req is not None
    assert req.url == "https://example.com/firmware/icle-v1.1.0.bin"
    assert req.version == "1.1.0"
    assert req.checksum == "abc123def456"


def test_ota_trigger_without_checksum():
    """OtaTriggerRequest without optional checksum parses correctly."""
    from src.api.v2.icle.types import OtaTriggerRequest

    data = {
        "url": "http://example.com/firmware.bin",
        "version": "2.0.0",
    }
    req, err = OtaTriggerRequest.from_json(data)

    assert err is None
    assert req.checksum is None


def test_ota_trigger_empty_body():
    """OtaTriggerRequest with None body returns error."""
    from src.api.v2.icle.types import OtaTriggerRequest

    req, err = OtaTriggerRequest.from_json(None)
    assert req is None
    assert err == "Request body must contain JSON data"


def test_ota_trigger_empty_dict():
    """OtaTriggerRequest with empty dict returns error."""
    from src.api.v2.icle.types import OtaTriggerRequest

    req, err = OtaTriggerRequest.from_json({})
    assert req is None
    assert err == "Request body must contain JSON data"


def test_ota_trigger_missing_url():
    """OtaTriggerRequest without url returns error."""
    from src.api.v2.icle.types import OtaTriggerRequest

    data = {"version": "1.0.0"}
    req, err = OtaTriggerRequest.from_json(data)

    assert req is None
    assert err == "Field 'url' is required"


def test_ota_trigger_blank_url():
    """OtaTriggerRequest with blank url returns error."""
    from src.api.v2.icle.types import OtaTriggerRequest

    data = {"url": "   ", "version": "1.0.0"}
    req, err = OtaTriggerRequest.from_json(data)

    assert req is None
    assert err == "Field 'url' is required"


def test_ota_trigger_invalid_url_scheme():
    """OtaTriggerRequest with non-HTTP URL returns error."""
    from src.api.v2.icle.types import OtaTriggerRequest

    data = {"url": "ftp://example.com/firmware.bin", "version": "1.0.0"}
    req, err = OtaTriggerRequest.from_json(data)

    assert req is None
    assert "HTTP/HTTPS" in err


def test_ota_trigger_missing_version():
    """OtaTriggerRequest without version returns error."""
    from src.api.v2.icle.types import OtaTriggerRequest

    data = {"url": "https://example.com/firmware.bin"}
    req, err = OtaTriggerRequest.from_json(data)

    assert req is None
    assert err == "Field 'version' is required"


def test_ota_trigger_blank_version():
    """OtaTriggerRequest with blank version returns error."""
    from src.api.v2.icle.types import OtaTriggerRequest

    data = {"url": "https://example.com/firmware.bin", "version": "  "}
    req, err = OtaTriggerRequest.from_json(data)

    assert req is None
    assert err == "Field 'version' is required"


def test_ota_trigger_http_url_accepted():
    """OtaTriggerRequest accepts http:// URLs (not just https)."""
    from src.api.v2.icle.types import OtaTriggerRequest

    data = {"url": "http://example.com/firmware.bin", "version": "1.0.0"}
    req, err = OtaTriggerRequest.from_json(data)

    assert err is None
    assert req.url == "http://example.com/firmware.bin"


def test_ota_trigger_url_whitespace_stripped():
    """OtaTriggerRequest strips whitespace from url and version."""
    from src.api.v2.icle.types import OtaTriggerRequest

    data = {
        "url": "  https://example.com/firmware.bin  ",
        "version": "  1.0.0  ",
    }
    req, err = OtaTriggerRequest.from_json(data)

    assert err is None
    assert req.url == "https://example.com/firmware.bin"
    assert req.version == "1.0.0"


def test_ota_trigger_empty_checksum_becomes_none():
    """OtaTriggerRequest with empty checksum string stores None."""
    from src.api.v2.icle.types import OtaTriggerRequest

    data = {
        "url": "https://example.com/firmware.bin",
        "version": "1.0.0",
        "checksum": "   ",
    }
    req, err = OtaTriggerRequest.from_json(data)

    assert err is None
    assert req.checksum is None
