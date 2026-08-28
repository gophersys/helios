"""Unit tests for HeartbeatRequest.from_json and to_status_data.

Complements the existing test_icle_types.py with additional edge cases.
"""
from __future__ import annotations

import pytest


class TestHeartbeatRequestFromJson:
    """Tests for HeartbeatRequest.from_json()."""

    def test_missing_device_id_returns_error(self):
        """from_json returns error when device_id is absent."""
        from src.api.v2.icle.types import HeartbeatRequest

        req, err = HeartbeatRequest.from_json({"firmware_version": "1.0.0"})

        assert req is None
        assert "device_id" in err

    def test_missing_firmware_version_returns_error(self):
        """from_json returns error when firmware_version is absent."""
        from src.api.v2.icle.types import HeartbeatRequest

        req, err = HeartbeatRequest.from_json({"device_id": "ICLE-001"})

        assert req is None
        assert "firmware_version" in err

    def test_empty_body_returns_error(self):
        """from_json returns error for empty/None input."""
        from src.api.v2.icle.types import HeartbeatRequest

        req, err = HeartbeatRequest.from_json({})
        assert req is None
        assert err is not None

        req2, err2 = HeartbeatRequest.from_json(None)
        assert req2 is None
        assert err2 is not None

    @pytest.mark.parametrize("status", ["online", "offline", "logging", "config", "boot", "ota"])
    def test_valid_statuses_accepted(self, status: str):
        """from_json accepts all documented status values."""
        from src.api.v2.icle.types import HeartbeatRequest

        req, err = HeartbeatRequest.from_json({
            "device_id": "ICLE-001",
            "firmware_version": "1.0.0",
            "status": status,
        })

        assert err is None
        assert req.status == status

    def test_invalid_status_returns_error(self):
        """from_json returns error for unrecognized status values."""
        from src.api.v2.icle.types import HeartbeatRequest

        req, err = HeartbeatRequest.from_json({
            "device_id": "ICLE-001",
            "firmware_version": "1.0.0",
            "status": "broken",
        })

        assert req is None
        assert "status" in err.lower() or "broken" in err

    def test_uptime_seconds_non_number_returns_error(self):
        """from_json returns error when uptime_seconds is not numeric."""
        from src.api.v2.icle.types import HeartbeatRequest

        req, err = HeartbeatRequest.from_json({
            "device_id": "ICLE-001",
            "firmware_version": "1.0.0",
            "uptime_seconds": "not-a-number",
        })

        assert req is None
        assert "uptime_seconds" in err

    def test_power_readings_not_list_returns_error(self):
        """from_json returns error when power_readings is not a list."""
        from src.api.v2.icle.types import HeartbeatRequest

        req, err = HeartbeatRequest.from_json({
            "device_id": "ICLE-001",
            "firmware_version": "1.0.0",
            "power_readings": {"channel": 0},  # should be a list
        })

        assert req is None
        assert "power_readings" in err

    def test_power_readings_invalid_entry_returns_error(self):
        """from_json returns error when a power reading entry is not an object."""
        from src.api.v2.icle.types import HeartbeatRequest

        req, err = HeartbeatRequest.from_json({
            "device_id": "ICLE-001",
            "firmware_version": "1.0.0",
            "power_readings": ["not-an-object"],
        })

        assert req is None
        assert "index 0" in err

    def test_camelcase_power_readings(self):
        """from_json parses camelCase power reading fields."""
        from src.api.v2.icle.types import HeartbeatRequest

        req, err = HeartbeatRequest.from_json({
            "deviceId": "ICLE-004",
            "firmwareVersion": "1.0.0",
            "powerReadings": [
                {"channel": 1, "voltageMv": 5000, "currentMa": 200, "powerMw": 1000},
            ],
        })

        assert err is None
        assert req is not None
        assert len(req.power_readings) == 1
        assert req.power_readings[0].voltage_mv == 5000.0

    def test_whitespace_stripped_from_strings(self):
        """from_json strips leading/trailing whitespace from string fields."""
        from src.api.v2.icle.types import HeartbeatRequest

        req, err = HeartbeatRequest.from_json({
            "device_id": "  ICLE-005  ",
            "firmware_version": "  1.0.0  ",
        })

        assert err is None
        assert req.device_id == "ICLE-005"
        assert req.firmware_version == "1.0.0"


class TestHeartbeatRequestToStatusData:
    """Tests for HeartbeatRequest.to_status_data()."""

    def test_minimal_request_omits_none_fields(self):
        """to_status_data excludes optional fields that are None."""
        from src.api.v2.icle.types import HeartbeatRequest

        req, _ = HeartbeatRequest.from_json({
            "device_id": "ICLE-001",
            "firmware_version": "1.0.0",
        })

        data = req.to_status_data()

        assert data["firmwareVersion"] == "1.0.0"
        assert "uptimeSeconds" not in data
        assert "freeHeapBytes" not in data
        assert "powerReadings" not in data

    def test_full_request_includes_all_optional_fields(self):
        """to_status_data includes all non-None optional fields."""
        from src.api.v2.icle.types import HeartbeatRequest

        req, _ = HeartbeatRequest.from_json({
            "device_id": "ICLE-002",
            "firmware_version": "2.0.0",
            "uptime_seconds": 3600,
            "free_heap_bytes": 65536,
            "wifi_rssi": -60,
            "sd_card_free_mb": 1024,
            "current_log_file": "log.csv",
            "power_readings": [
                {"channel": 0, "voltage_mv": 3300, "current_ma": 100, "power_mw": 330},
            ],
        })

        data = req.to_status_data()

        assert data["uptimeSeconds"] == 3600
        assert data["freeHeapBytes"] == 65536
        assert data["wifiRssi"] == -60
        assert data["sdCardFreeMb"] == 1024
        assert data["currentLogFile"] == "log.csv"
        assert len(data["powerReadings"]) == 1
        assert data["powerReadings"][0]["voltageMv"] == 3300.0
