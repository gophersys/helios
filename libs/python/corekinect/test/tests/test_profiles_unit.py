"""Unit tests for corekinect.test.profiles.

Tests the profile data model: enums, config dataclasses, FixtureProfile
parsing, DeviceProfile features, ValidationConfig logic, and the built-in
device profile registry.
"""

import pytest

from corekinect.test.profiles import (
    Capability,
    Feature,
    FEATURE_REQUIREMENTS,
    ButtonConfig,
    PpgSimulatorConfig,
    PeltierConfig,
    ChargerRelayConfig,
    LedSensorConfig,
    NfcReaderConfig,
    MotionConfig,
    PowerConfig,
    DutConfig,
    FixtureProfile,
    DeviceProfile,
    ValidationConfig,
    DEVICE_PROFILES,
    get_device_profile,
)


# =============================================================================
# Capability enum
# =============================================================================


class TestCapabilityEnum:
    def test_all_members_exist(self):
        expected = {
            "POWER", "BUTTON", "PELTIER", "CHARGER_RELAY",
            "PPG_SERVO", "PPG_LED", "LED_PHOTODIODE", "NFC_READER",
            "MOTION_ACTUATOR", "HAPTIC_SENSOR", "JLINK",
        }
        assert {m.name for m in Capability} == expected

    def test_values_are_strings(self):
        for cap in Capability:
            assert isinstance(cap.value, str)
            assert len(cap.value) > 0

    def test_is_str_enum(self):
        assert isinstance(Capability.POWER, str)
        assert Capability.POWER == "power"


# =============================================================================
# Feature enum
# =============================================================================


class TestFeatureEnum:
    def test_all_members_exist(self):
        expected = {
            "POWER", "BUTTON", "LED", "BIOMETRIC", "ENVIRONMENTAL",
            "MOTION", "NFC", "CELLULAR", "GNSS", "CHARGING", "HAPTIC",
        }
        assert {m.name for m in Feature} == expected

    def test_is_str_enum(self):
        assert isinstance(Feature.POWER, str)
        assert Feature.POWER == "power"


# =============================================================================
# FEATURE_REQUIREMENTS
# =============================================================================


class TestFeatureRequirements:
    def test_every_feature_has_entry(self):
        for feature in Feature:
            assert feature in FEATURE_REQUIREMENTS, f"{feature} missing from FEATURE_REQUIREMENTS"

    def test_values_are_lists(self):
        for feature, caps in FEATURE_REQUIREMENTS.items():
            assert isinstance(caps, list), f"{feature} requirements is not a list"

    def test_biometric_requires_ppg(self):
        assert Capability.PPG_SERVO in FEATURE_REQUIREMENTS[Feature.BIOMETRIC]
        assert Capability.PPG_LED in FEATURE_REQUIREMENTS[Feature.BIOMETRIC]

    def test_power_requires_nothing(self):
        assert FEATURE_REQUIREMENTS[Feature.POWER] == []


# =============================================================================
# Config dataclasses — frozen creation and defaults
# =============================================================================


class TestButtonConfig:
    def test_creation(self):
        cfg = ButtonConfig(gpio_pin=2)
        assert cfg.gpio_pin == 2
        assert cfg.active_low is True

    def test_frozen(self):
        cfg = ButtonConfig(gpio_pin=2)
        with pytest.raises(AttributeError):
            cfg.gpio_pin = 5

    def test_custom_active_low(self):
        cfg = ButtonConfig(gpio_pin=3, active_low=False)
        assert cfg.active_low is False


class TestPpgSimulatorConfig:
    def test_creation(self):
        cfg = PpgSimulatorConfig(
            servo_pwm_pin=7,
            servo_blocked_duty_us=1000,
            servo_exposed_duty_us=2000,
            hr_led_gpio_pin=3,
        )
        assert cfg.servo_pwm_pin == 7
        assert cfg.hr_led_gpio_pin == 3


class TestPeltierConfig:
    def test_creation(self):
        cfg = PeltierConfig(gpio_pin=4, temp_adc_channel=7)
        assert cfg.gpio_pin == 4
        assert cfg.temp_adc_channel == 7


class TestChargerRelayConfig:
    def test_defaults(self):
        cfg = ChargerRelayConfig(gpio_pin=5)
        assert cfg.active_high is True


class TestLedSensorConfig:
    def test_creation(self):
        cfg = LedSensorConfig(red_adc_channel=4, green_adc_channel=5, blue_adc_channel=6)
        assert cfg.red_adc_channel == 4


class TestNfcReaderConfig:
    def test_defaults(self):
        cfg = NfcReaderConfig()
        assert cfg.interface == "i2c"
        assert cfg.bus == 1


class TestMotionConfig:
    def test_defaults(self):
        cfg = MotionConfig()
        assert cfg.enabled is False


class TestPowerConfig:
    def test_defaults(self):
        cfg = PowerConfig(battery_installed=False)
        assert cfg.dut_voltage == 4.5
        assert cfg.charger_voltage == 5.0
        assert cfg.boot_settle_s == 10.0

    def test_battery_installed(self):
        cfg = PowerConfig(battery_installed=True)
        assert cfg.battery_installed is True


class TestDutConfig:
    def test_full_construction(self):
        cfg = DutConfig(
            device_id="70B3D584C01E1FCC",
            snr="0964",
            imei="355025931735979",
            iccids=["89148000009808558441"],
        )
        assert cfg.device_id == "70B3D584C01E1FCC"
        assert cfg.snr == "0964"
        assert cfg.imei == "355025931735979"
        assert len(cfg.iccids) == 1

    def test_optional_fields_default_none(self):
        cfg = DutConfig(device_id="abc", snr="123")
        assert cfg.imei is None
        assert cfg.iccids is None


# =============================================================================
# FixtureProfile.from_dict
# =============================================================================

def _full_profile_dict():
    """Return a complete fixture profile dict with all hardware blocks."""
    return {
        "station_id": "mtib-rev1.2",
        "product": "alpha",
        "board": "b0",
        "mtib_revision": "1.2",
        "capabilities": ["power", "button", "peltier", "charger_relay"],
        "power": {
            "battery_installed": True,
            "dut_voltage": 4.5,
            "charger_voltage": 5.0,
            "boot_settle_s": 10.0,
        },
        "dut": {
            "device_id": "70B3D584C01E1FCC",
            "snr": "0964",
            "imei": "355025931735979",
            "iccids": ["89148000009808558441"],
        },
        "button": {"gpio_pin": 2, "active_low": True},
        "peltier": {"gpio_pin": 4, "temp_adc_channel": 7},
        "charger_relay": {"gpio_pin": 5, "active_high": True},
    }


def _minimal_profile_dict():
    """Return a minimal dict with only required identity fields."""
    return {
        "station_id": "bench-1",
        "product": "alpha",
        "board": "b0",
    }


class TestFixtureProfileFromDict:
    def test_full_parse(self):
        data = _full_profile_dict()
        profile = FixtureProfile.from_dict(data)

        assert profile.station_id == "mtib-rev1.2"
        assert profile.product == "alpha"
        assert profile.board == "b0"
        assert profile.mtib_revision == "1.2"
        assert Capability.BUTTON in profile.capabilities
        assert Capability.POWER in profile.capabilities
        assert profile.power.battery_installed is True
        assert profile.dut.device_id == "70B3D584C01E1FCC"
        assert profile.button is not None
        assert profile.button.gpio_pin == 2
        assert profile.peltier is not None
        assert profile.charger_relay is not None

    def test_minimal_parse_uses_defaults(self):
        data = _minimal_profile_dict()
        profile = FixtureProfile.from_dict(data)

        assert profile.station_id == "bench-1"
        assert profile.power.battery_installed is False
        assert profile.power.dut_voltage == 4.5
        assert profile.dut.device_id == ""
        assert len(profile.capabilities) == 0

    def test_capabilities_parsed_from_strings(self):
        data = {"capabilities": ["ppg_servo", "ppg_led", "jlink"]}
        profile = FixtureProfile.from_dict(data)
        assert Capability.PPG_SERVO in profile.capabilities
        assert Capability.PPG_LED in profile.capabilities
        assert Capability.JLINK in profile.capabilities

    def test_hardware_blocks_none_when_absent(self):
        data = _minimal_profile_dict()
        profile = FixtureProfile.from_dict(data)

        assert profile.button is None
        assert profile.ppg_simulator is None
        assert profile.peltier is None
        assert profile.charger_relay is None
        assert profile.led_sensor is None
        assert profile.nfc_reader is None
        assert profile.motion is None

    def test_hardware_block_with_partial_fields_uses_defaults(self):
        data = {"button": {"gpio_pin": 9}}
        profile = FixtureProfile.from_dict(data)
        assert profile.button is not None
        assert profile.button.gpio_pin == 9
        assert profile.button.active_low is True  # default

    def test_convenience_properties(self):
        data = _full_profile_dict()
        profile = FixtureProfile.from_dict(data)
        assert profile.battery_installed is True
        assert profile.boot_settle_s == 10.0
        assert profile.dut_voltage == 4.5
        assert profile.charger_voltage == 5.0


# =============================================================================
# _parse_hardware_block
# =============================================================================


class TestParseHardwareBlock:
    def test_returns_none_for_missing_key(self):
        result = FixtureProfile._parse_hardware_block(
            {}, "button", ButtonConfig, {"gpio_pin": 2, "active_low": True}
        )
        assert result is None

    def test_returns_none_for_null_value(self):
        result = FixtureProfile._parse_hardware_block(
            {"button": None}, "button", ButtonConfig, {"gpio_pin": 2, "active_low": True}
        )
        assert result is None

    def test_returns_none_for_non_dict(self):
        result = FixtureProfile._parse_hardware_block(
            {"button": "not-a-dict"}, "button", ButtonConfig, {"gpio_pin": 2, "active_low": True}
        )
        assert result is None

    def test_creates_config_from_block(self):
        data = {"button": {"gpio_pin": 7, "active_low": False}}
        result = FixtureProfile._parse_hardware_block(
            data, "button", ButtonConfig, {"gpio_pin": 2, "active_low": True}
        )
        assert result is not None
        assert result.gpio_pin == 7
        assert result.active_low is False

    def test_uses_defaults_for_missing_fields(self):
        data = {"button": {"gpio_pin": 3}}
        result = FixtureProfile._parse_hardware_block(
            data, "button", ButtonConfig, {"gpio_pin": 2, "active_low": True}
        )
        assert result.gpio_pin == 3
        assert result.active_low is True  # from default


# =============================================================================
# FixtureProfile capability methods
# =============================================================================


class TestFixtureProfileCapabilities:
    def test_has_capability_true(self):
        profile = FixtureProfile.from_dict({"capabilities": ["button"]})
        assert profile.has_capability(Capability.BUTTON) is True

    def test_has_capability_false(self):
        profile = FixtureProfile.from_dict({"capabilities": ["button"]})
        assert profile.has_capability(Capability.PELTIER) is False

    def test_has_all_capabilities_true(self):
        profile = FixtureProfile.from_dict({"capabilities": ["button", "peltier"]})
        assert profile.has_all_capabilities([Capability.BUTTON, Capability.PELTIER]) is True

    def test_has_all_capabilities_false_when_one_missing(self):
        profile = FixtureProfile.from_dict({"capabilities": ["button"]})
        assert profile.has_all_capabilities([Capability.BUTTON, Capability.PELTIER]) is False

    def test_has_all_capabilities_empty_list(self):
        profile = FixtureProfile.from_dict({})
        assert profile.has_all_capabilities([]) is True

    def test_missing_capabilities(self):
        profile = FixtureProfile.from_dict({"capabilities": ["button"]})
        missing = profile.missing_capabilities([Capability.BUTTON, Capability.PELTIER, Capability.JLINK])
        assert Capability.PELTIER in missing
        assert Capability.JLINK in missing
        assert Capability.BUTTON not in missing

    def test_missing_capabilities_empty_when_all_present(self):
        profile = FixtureProfile.from_dict({"capabilities": ["button", "peltier"]})
        missing = profile.missing_capabilities([Capability.BUTTON, Capability.PELTIER])
        assert missing == []


# =============================================================================
# DeviceProfile
# =============================================================================


class TestDeviceProfile:
    def test_construction(self):
        dp = DeviceProfile(
            product="alpha",
            revision="b0",
            features={Feature.POWER, Feature.BUTTON},
        )
        assert dp.product == "alpha"
        assert dp.revision == "b0"
        assert Feature.POWER in dp.features

    def test_has_feature_true(self):
        dp = DeviceProfile(product="x", revision="1", features={Feature.LED})
        assert dp.has_feature(Feature.LED) is True

    def test_has_feature_false(self):
        dp = DeviceProfile(product="x", revision="1", features={Feature.LED})
        assert dp.has_feature(Feature.NFC) is False

    def test_defaults(self):
        dp = DeviceProfile(product="x", revision="1", features=set())
        assert dp.battery_required is False
        assert dp.boot_voltage_v == 4.5
        assert dp.charger_voltage_v == 5.0
        assert dp.device_type == 2
        assert dp.device_variant == 3
        assert dp.app_ids == [108, 109]


# =============================================================================
# ValidationConfig
# =============================================================================


class TestValidationConfig:
    def _make_config(self, device_features, fixture_caps):
        device = DeviceProfile(product="alpha", revision="b0", features=device_features)
        fixture = FixtureProfile.from_dict({"capabilities": [c.value for c in fixture_caps]})
        return ValidationConfig(device=device, fixture=fixture)

    def test_can_test_feature_supported_and_capable(self):
        cfg = self._make_config({Feature.BUTTON}, {Capability.BUTTON})
        assert cfg.can_test_feature(Feature.BUTTON) is True

    def test_can_test_feature_not_supported_by_device(self):
        cfg = self._make_config({Feature.POWER}, {Capability.BUTTON})
        assert cfg.can_test_feature(Feature.BUTTON) is False

    def test_can_test_feature_missing_capability(self):
        cfg = self._make_config({Feature.BIOMETRIC}, set())
        assert cfg.can_test_feature(Feature.BIOMETRIC) is False

    def test_can_test_feature_no_requirements(self):
        cfg = self._make_config({Feature.POWER}, set())
        assert cfg.can_test_feature(Feature.POWER) is True

    def test_skip_reason_none_when_testable(self):
        cfg = self._make_config({Feature.BUTTON}, {Capability.BUTTON})
        assert cfg.skip_reason(Feature.BUTTON) is None

    def test_skip_reason_device_unsupported(self):
        cfg = self._make_config({Feature.POWER}, set())
        reason = cfg.skip_reason(Feature.BUTTON)
        assert reason is not None
        assert "does not support" in reason

    def test_skip_reason_missing_capability(self):
        cfg = self._make_config({Feature.BIOMETRIC}, set())
        reason = cfg.skip_reason(Feature.BIOMETRIC)
        assert reason is not None
        assert "lacks capabilities" in reason
        assert "ppg_servo" in reason

    def test_runnable_features(self):
        cfg = self._make_config(
            {Feature.POWER, Feature.BUTTON, Feature.BIOMETRIC},
            {Capability.BUTTON},
        )
        runnable = cfg.runnable_features
        assert Feature.POWER in runnable
        assert Feature.BUTTON in runnable
        assert Feature.BIOMETRIC not in runnable  # missing PPG caps


# =============================================================================
# Built-in device profiles
# =============================================================================


class TestDeviceProfiles:
    def test_alpha_b0_exists(self):
        assert "alpha_b0" in DEVICE_PROFILES

    def test_alpha_a0_exists(self):
        assert "alpha_a0" in DEVICE_PROFILES

    def test_alpha_b0_has_expected_features(self):
        profile = DEVICE_PROFILES["alpha_b0"]
        assert Feature.POWER in profile.features
        assert Feature.BIOMETRIC in profile.features
        assert Feature.CELLULAR in profile.features

    def test_get_device_profile_known(self):
        profile = get_device_profile("alpha", "b0")
        assert profile is not None
        assert profile.product == "alpha"

    def test_get_device_profile_unknown_returns_none(self):
        assert get_device_profile("unknown", "x0") is None
