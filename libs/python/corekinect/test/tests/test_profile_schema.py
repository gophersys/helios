"""Unit tests for fixture profile schema validation."""

import json
import tempfile
from pathlib import Path

import pytest

from corekinect.errors import ConfigError
from corekinect.test.profile_schema import (
    VALID_CAPABILITIES,
    load_validated_profile,
    validate_fixture_profile,
)


# =============================================================================
# Valid profile fixture
# =============================================================================


VALID_PROFILE = {
    "station_id": "bench-33",
    "product": "alpha",
    "board": "alpha_b0",
    "mtib_revision": "1.2",
    "capabilities": ["button", "peltier", "charger_relay"],
    "dut": {
        "device_id": "70B3D584C01E1DDD",
        "snr": "09J5",
        "imei": "355025931651952",
        "iccids": ["89148000009808560116"],
    },
    "power": {
        "battery_installed": True,
        "dut_voltage": 4.5,
        "charger_voltage": 5.0,
        "boot_settle_s": 10,
    },
    "button": {"gpio_pin": 2, "active_low": True},
    "peltier": {"gpio_pin": 4, "temp_adc_channel": 7},
    "charger_relay": {"gpio_pin": 5, "active_high": True},
    "ppg_simulator": None,
    "led_sensor": None,
    "nfc_reader": None,
    "motion": None,
}


# =============================================================================
# Tests: validate_fixture_profile
# =============================================================================


class TestValidProfile:
    """A valid profile should produce no errors."""

    def test_valid_profile_no_errors(self):
        errors = validate_fixture_profile(VALID_PROFILE)
        assert errors == []

    def test_minimal_profile_no_errors(self):
        """Only required fields — should be valid."""
        data = {"station_id": "bench-1", "product": "test", "board": "test_b0"}
        errors = validate_fixture_profile(data)
        assert errors == []

    def test_private_fields_ignored(self):
        """Fields starting with _ should be ignored."""
        data = dict(VALID_PROFILE)
        data["_hardware_notes"] = {"some": "data"}
        data["_doc"] = "notes"
        errors = validate_fixture_profile(data)
        assert errors == []


class TestRequiredFields:
    """Missing or wrongly-typed required fields."""

    def test_missing_station_id(self):
        data = dict(VALID_PROFILE)
        del data["station_id"]
        errors = validate_fixture_profile(data)
        assert any("station_id" in e and "required" in e for e in errors)

    def test_missing_product(self):
        data = dict(VALID_PROFILE)
        del data["product"]
        errors = validate_fixture_profile(data)
        assert any("product" in e and "required" in e for e in errors)

    def test_missing_board(self):
        data = dict(VALID_PROFILE)
        del data["board"]
        errors = validate_fixture_profile(data)
        assert any("board" in e and "required" in e for e in errors)

    def test_wrong_type_station_id(self):
        data = dict(VALID_PROFILE)
        data["station_id"] = 123
        errors = validate_fixture_profile(data)
        assert any("station_id" in e and "str" in e for e in errors)

    def test_not_a_dict(self):
        errors = validate_fixture_profile("not a dict")
        assert len(errors) == 1
        assert "must be a dict" in errors[0]


class TestCapabilities:
    """Capability list validation."""

    def test_unknown_capability(self):
        data = dict(VALID_PROFILE)
        data["capabilities"] = ["button", "laser_cannon"]
        errors = validate_fixture_profile(data)
        assert any("laser_cannon" in e and "unknown capability" in e for e in errors)

    def test_non_string_capability(self):
        data = dict(VALID_PROFILE)
        data["capabilities"] = ["button", 42]
        errors = validate_fixture_profile(data)
        assert any("expected string" in e for e in errors)

    def test_all_valid_capabilities(self):
        data = dict(VALID_PROFILE)
        data["capabilities"] = list(VALID_CAPABILITIES)
        errors = validate_fixture_profile(data)
        assert errors == []


class TestPowerConfig:
    """Power config sub-object validation."""

    def test_missing_battery_installed(self):
        data = dict(VALID_PROFILE)
        data["power"] = {"dut_voltage": 4.5}
        errors = validate_fixture_profile(data)
        assert any("battery_installed" in e and "required" in e for e in errors)

    def test_missing_dut_voltage(self):
        data = dict(VALID_PROFILE)
        data["power"] = {"battery_installed": True}
        errors = validate_fixture_profile(data)
        assert any("dut_voltage" in e and "required" in e for e in errors)

    def test_wrong_type_battery_installed(self):
        data = dict(VALID_PROFILE)
        data["power"] = {"battery_installed": "yes", "dut_voltage": 4.5}
        errors = validate_fixture_profile(data)
        assert any("battery_installed" in e and "bool" in e for e in errors)

    def test_unknown_power_field(self):
        data = dict(VALID_PROFILE)
        data["power"] = dict(VALID_PROFILE["power"])
        data["power"]["typo_field"] = 42
        errors = validate_fixture_profile(data)
        assert any("typo_field" in e and "unknown" in e for e in errors)


class TestHardwareBlocks:
    """Hardware block sub-object validation."""

    def test_button_missing_gpio_pin(self):
        data = dict(VALID_PROFILE)
        data["button"] = {"active_low": True}
        errors = validate_fixture_profile(data)
        assert any("gpio_pin" in e and "required" in e for e in errors)

    def test_peltier_missing_temp_adc(self):
        data = dict(VALID_PROFILE)
        data["peltier"] = {"gpio_pin": 4}
        errors = validate_fixture_profile(data)
        assert any("temp_adc_channel" in e and "required" in e for e in errors)

    def test_charger_relay_wrong_type(self):
        data = dict(VALID_PROFILE)
        data["charger_relay"] = {"gpio_pin": "five", "active_high": True}
        errors = validate_fixture_profile(data)
        assert any("gpio_pin" in e and "int" in e for e in errors)

    def test_null_hardware_block_accepted(self):
        """null means 'not wired' — should be accepted."""
        data = dict(VALID_PROFILE)
        data["ppg_simulator"] = None
        data["led_sensor"] = None
        errors = validate_fixture_profile(data)
        assert errors == []


class TestUnknownFields:
    """Unknown top-level fields should be flagged."""

    def test_unknown_top_level_field(self):
        data = dict(VALID_PROFILE)
        data["laser_module"] = {"power": 9000}
        errors = validate_fixture_profile(data)
        assert any("laser_module" in e and "unknown" in e for e in errors)


# =============================================================================
# Tests: load_validated_profile
# =============================================================================


class TestLoadValidatedProfile:
    """File-based loading with validation."""

    def test_load_valid_file(self, tmp_path):
        path = tmp_path / "profile.json"
        path.write_text(json.dumps(VALID_PROFILE))

        data = load_validated_profile(path)
        assert data["product"] == "alpha"

    def test_load_invalid_file_strict(self, tmp_path):
        path = tmp_path / "bad.json"
        path.write_text(json.dumps({"bad": "data"}))

        with pytest.raises(ConfigError, match="error"):
            load_validated_profile(path, strict=True)

    def test_load_invalid_file_lenient(self, tmp_path):
        path = tmp_path / "bad.json"
        path.write_text(json.dumps({"station_id": "x", "product": "y", "board": "z", "typo": 1}))

        # strict=False should not raise
        data = load_validated_profile(path, strict=False)
        assert data["product"] == "y"

    def test_load_missing_file(self):
        with pytest.raises(FileNotFoundError):
            load_validated_profile("/nonexistent/profile.json")

    def test_load_real_alpha_profile(self):
        """Validate the actual Alpha fixture profile if it exists."""
        alpha_path = Path(
            "apps/validation/alpha/fixtures/alpha_b0.json"
        )
        if not alpha_path.exists():
            pytest.skip("Alpha profile not in working directory")

        data = load_validated_profile(alpha_path)
        assert data["product"] == "alpha"
