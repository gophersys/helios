"""Tests for validation profile models.

Tests the core data models:
- FixtureProfile — test bench hardware configuration
- DeviceProfile — DUT feature capabilities
- ValidationConfig — combined config with runnable features
"""

import json
import tempfile
from pathlib import Path

import pytest

from corekinect.test.validation.profiles import (
    Capability,
    Feature,
    FEATURE_REQUIREMENTS,
    FixtureProfile,
    DeviceProfile,
    ValidationConfig,
    PowerConfig,
    DutConfig,
    ButtonConfig,
    get_device_profile,
)


class TestCapability:
    """Tests for Capability enum."""

    def test_capability_values_are_strings(self):
        """Capability values should be lowercase strings for JSON serialization."""
        assert Capability.BUTTON.value == "button"
        assert Capability.PPG_SERVO.value == "ppg_servo"
        assert Capability.MOTION_ACTUATOR.value == "motion_actuator"

    def test_capability_from_string(self):
        """Can create Capability from string value."""
        assert Capability("button") == Capability.BUTTON
        assert Capability("ppg_servo") == Capability.PPG_SERVO


class TestFeature:
    """Tests for Feature enum."""

    def test_feature_values_are_strings(self):
        """Feature values should be lowercase strings."""
        assert Feature.BIOMETRIC.value == "biometric"
        assert Feature.ENVIRONMENTAL.value == "environmental"

    def test_all_features_have_requirements_defined(self):
        """Every feature should have an entry in FEATURE_REQUIREMENTS."""
        for feature in Feature:
            assert feature in FEATURE_REQUIREMENTS, (
                f"Feature {feature.value} missing from FEATURE_REQUIREMENTS"
            )


class TestFixtureProfile:
    """Tests for FixtureProfile."""

    def test_has_capability(self):
        """has_capability returns True only for listed capabilities."""
        profile = FixtureProfile(
            station_id="test",
            product="alpha",
            board="alpha_b0",
            mtib_revision="1.2",
            capabilities={Capability.BUTTON, Capability.PELTIER},
            power=PowerConfig(battery_installed=False),
            dut=DutConfig(device_id="ABC", snr="1234"),
        )

        assert profile.has_capability(Capability.BUTTON)
        assert profile.has_capability(Capability.PELTIER)
        assert not profile.has_capability(Capability.PPG_SERVO)
        assert not profile.has_capability(Capability.MOTION_ACTUATOR)

    def test_has_all_capabilities(self):
        """has_all_capabilities returns True only if ALL listed are present."""
        profile = FixtureProfile(
            station_id="test",
            product="alpha",
            board="alpha_b0",
            mtib_revision="1.2",
            capabilities={Capability.BUTTON, Capability.PELTIER, Capability.CHARGER_RELAY},
            power=PowerConfig(battery_installed=False),
            dut=DutConfig(device_id="ABC", snr="1234"),
        )

        assert profile.has_all_capabilities([Capability.BUTTON])
        assert profile.has_all_capabilities([Capability.BUTTON, Capability.PELTIER])
        assert profile.has_all_capabilities([])  # Empty list always True
        assert not profile.has_all_capabilities([Capability.BUTTON, Capability.PPG_SERVO])

    def test_missing_capabilities(self):
        """missing_capabilities returns list of caps not present."""
        profile = FixtureProfile(
            station_id="test",
            product="alpha",
            board="alpha_b0",
            mtib_revision="1.2",
            capabilities={Capability.BUTTON},
            power=PowerConfig(battery_installed=False),
            dut=DutConfig(device_id="ABC", snr="1234"),
        )

        missing = profile.missing_capabilities([
            Capability.BUTTON,
            Capability.PPG_SERVO,
            Capability.MOTION_ACTUATOR,
        ])
        assert Capability.PPG_SERVO in missing
        assert Capability.MOTION_ACTUATOR in missing
        assert Capability.BUTTON not in missing

    def test_from_dict(self):
        """Can create FixtureProfile from dictionary."""
        data = {
            "station_id": "station-33",
            "product": "alpha",
            "board": "alpha_b0",
            "mtib_revision": "1.2",
            "capabilities": ["button", "peltier"],
            "power": {
                "battery_installed": True,
                "dut_voltage": 4.5,
                "charger_voltage": 5.0,
                "boot_settle_s": 10.0,
            },
            "dut": {
                "device_id": "70B3D584C01E1FCC",
                "snr": "0964",
            },
            "button": {
                "gpio_pin": 2,
                "active_low": True,
            },
            "peltier": {
                "gpio_pin": 4,
                "temp_adc_channel": 7,
            },
        }

        profile = FixtureProfile.from_dict(data)

        assert profile.station_id == "station-33"
        assert profile.product == "alpha"
        assert profile.board == "alpha_b0"
        assert profile.has_capability(Capability.BUTTON)
        assert profile.has_capability(Capability.PELTIER)
        assert not profile.has_capability(Capability.PPG_SERVO)
        assert profile.power.battery_installed is True
        assert profile.dut.device_id == "70B3D584C01E1FCC"
        assert profile.button is not None
        assert profile.button.gpio_pin == 2
        assert profile.peltier is not None
        assert profile.peltier.gpio_pin == 4
        assert profile.ppg_simulator is None  # Not in capabilities

    def test_from_json_file(self):
        """Can load FixtureProfile from JSON file."""
        data = {
            "station_id": "json-test",
            "product": "alpha",
            "board": "alpha_b0",
            "mtib_revision": "1.2",
            "capabilities": ["button"],
            "power": {"battery_installed": False},
            "dut": {"device_id": "TEST123", "snr": "0001"},
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(data, f)
            f.flush()

            profile = FixtureProfile.from_json(f.name)

        assert profile.station_id == "json-test"
        assert profile.has_capability(Capability.BUTTON)

    def test_to_dict_roundtrip(self):
        """to_dict produces dict that can be loaded back."""
        original = FixtureProfile(
            station_id="roundtrip-test",
            product="alpha",
            board="alpha_b0",
            mtib_revision="1.2",
            capabilities={Capability.BUTTON, Capability.PELTIER},
            power=PowerConfig(battery_installed=True, dut_voltage=4.5),
            dut=DutConfig(device_id="ABC123", snr="0964"),
            button=ButtonConfig(gpio_pin=2, active_low=True),
        )

        data = original.to_dict()
        restored = FixtureProfile.from_dict(data)

        assert restored.station_id == original.station_id
        assert restored.capabilities == original.capabilities
        assert restored.power.battery_installed == original.power.battery_installed
        assert restored.dut.device_id == original.dut.device_id


class TestDeviceProfile:
    """Tests for DeviceProfile."""

    def test_has_feature(self):
        """has_feature returns True only for listed features."""
        profile = DeviceProfile(
            product="alpha",
            revision="b0",
            features={Feature.BUTTON, Feature.BIOMETRIC, Feature.ENVIRONMENTAL},
        )

        assert profile.has_feature(Feature.BUTTON)
        assert profile.has_feature(Feature.BIOMETRIC)
        assert not profile.has_feature(Feature.HAPTIC)

    def test_from_dict(self):
        """Can create DeviceProfile from dictionary."""
        data = {
            "product": "alpha",
            "revision": "a0",
            "features": ["button", "led", "cellular"],
            "battery_required": True,
            "device_type": 2,
            "device_variant": 2,
        }

        profile = DeviceProfile.from_dict(data)

        assert profile.product == "alpha"
        assert profile.revision == "a0"
        assert profile.has_feature(Feature.BUTTON)
        assert profile.has_feature(Feature.LED)
        assert profile.has_feature(Feature.CELLULAR)
        assert not profile.has_feature(Feature.BIOMETRIC)
        assert profile.battery_required is True
        assert profile.device_type == 2

    def test_builtin_alpha_b0(self):
        """Built-in alpha_b0 profile has expected features."""
        profile = get_device_profile("alpha", "b0")

        assert profile is not None
        assert profile.has_feature(Feature.BUTTON)
        assert profile.has_feature(Feature.BIOMETRIC)
        assert profile.has_feature(Feature.ENVIRONMENTAL)
        assert profile.has_feature(Feature.MOTION)
        assert profile.has_feature(Feature.NFC)
        assert profile.has_feature(Feature.CELLULAR)


class TestValidationConfig:
    """Tests for ValidationConfig — combined device + fixture."""

    @pytest.fixture
    def full_device(self) -> DeviceProfile:
        """Device with all features."""
        return DeviceProfile(
            product="alpha",
            revision="b0",
            features={
                Feature.POWER,
                Feature.BUTTON,
                Feature.LED,
                Feature.BIOMETRIC,
                Feature.ENVIRONMENTAL,
                Feature.MOTION,
                Feature.NFC,
            },
        )

    @pytest.fixture
    def limited_device(self) -> DeviceProfile:
        """Device with limited features."""
        return DeviceProfile(
            product="alpha",
            revision="a0",
            features={Feature.POWER, Feature.BUTTON, Feature.ENVIRONMENTAL},
        )

    @pytest.fixture
    def full_fixture(self) -> FixtureProfile:
        """Fixture with all capabilities."""
        return FixtureProfile(
            station_id="full-test",
            product="alpha",
            board="alpha_b0",
            mtib_revision="1.2",
            capabilities={
                Capability.BUTTON,
                Capability.PELTIER,
                Capability.PPG_SERVO,
                Capability.PPG_LED,
                Capability.LED_PHOTODIODE,
                Capability.NFC_READER,
                Capability.MOTION_ACTUATOR,
            },
            power=PowerConfig(battery_installed=False),
            dut=DutConfig(device_id="ABC", snr="1234"),
        )

    @pytest.fixture
    def limited_fixture(self) -> FixtureProfile:
        """Fixture with limited capabilities."""
        return FixtureProfile(
            station_id="limited-test",
            product="alpha",
            board="alpha_b0",
            mtib_revision="1.2",
            capabilities={Capability.BUTTON, Capability.PELTIER},
            power=PowerConfig(battery_installed=False),
            dut=DutConfig(device_id="ABC", snr="1234"),
        )

    def test_runnable_features_full_device_full_fixture(
        self, full_device: DeviceProfile, full_fixture: FixtureProfile
    ):
        """Full device + full fixture = all features runnable."""
        config = ValidationConfig(device=full_device, fixture=full_fixture)
        runnable = config.runnable_features

        assert Feature.POWER in runnable
        assert Feature.BUTTON in runnable
        assert Feature.BIOMETRIC in runnable
        assert Feature.MOTION in runnable
        assert Feature.NFC in runnable

    def test_runnable_features_limited_by_device(
        self, limited_device: DeviceProfile, full_fixture: FixtureProfile
    ):
        """Device without feature = feature not runnable even if fixture has capability."""
        config = ValidationConfig(device=limited_device, fixture=full_fixture)
        runnable = config.runnable_features

        # Device has these
        assert Feature.POWER in runnable
        assert Feature.BUTTON in runnable
        assert Feature.ENVIRONMENTAL in runnable

        # Device doesn't have these (even though fixture has capabilities)
        assert Feature.BIOMETRIC not in runnable
        assert Feature.MOTION not in runnable
        assert Feature.NFC not in runnable

    def test_runnable_features_limited_by_fixture(
        self, full_device: DeviceProfile, limited_fixture: FixtureProfile
    ):
        """Fixture without capability = feature not runnable even if device supports it."""
        config = ValidationConfig(device=full_device, fixture=limited_fixture)
        runnable = config.runnable_features

        # These work (device has feature, fixture has capability or no cap needed)
        assert Feature.POWER in runnable  # No capability needed
        assert Feature.BUTTON in runnable  # Has BUTTON capability
        assert Feature.ENVIRONMENTAL in runnable  # No capability needed

        # These don't work (device has feature, but fixture lacks capability)
        assert Feature.BIOMETRIC not in runnable  # Needs PPG_SERVO + PPG_LED
        assert Feature.MOTION not in runnable  # Needs MOTION_ACTUATOR
        assert Feature.NFC not in runnable  # Needs NFC_READER
        assert Feature.LED not in runnable  # Needs LED_PHOTODIODE

    def test_can_test_feature(
        self, full_device: DeviceProfile, limited_fixture: FixtureProfile
    ):
        """can_test_feature returns correct boolean."""
        config = ValidationConfig(device=full_device, fixture=limited_fixture)

        assert config.can_test_feature(Feature.BUTTON) is True
        assert config.can_test_feature(Feature.ENVIRONMENTAL) is True
        assert config.can_test_feature(Feature.BIOMETRIC) is False
        assert config.can_test_feature(Feature.MOTION) is False

    def test_skip_reason_device_missing_feature(
        self, limited_device: DeviceProfile, full_fixture: FixtureProfile
    ):
        """skip_reason explains when device doesn't support feature."""
        config = ValidationConfig(device=limited_device, fixture=full_fixture)

        reason = config.skip_reason(Feature.BIOMETRIC)

        assert reason is not None
        assert "does not support" in reason
        assert "biometric" in reason

    def test_skip_reason_fixture_missing_capability(
        self, full_device: DeviceProfile, limited_fixture: FixtureProfile
    ):
        """skip_reason explains when fixture lacks capability."""
        config = ValidationConfig(device=full_device, fixture=limited_fixture)

        reason = config.skip_reason(Feature.BIOMETRIC)

        assert reason is not None
        assert "lacks capabilities" in reason
        assert "ppg_servo" in reason or "ppg_led" in reason

    def test_skip_reason_none_when_testable(
        self, full_device: DeviceProfile, full_fixture: FixtureProfile
    ):
        """skip_reason returns None when feature is testable."""
        config = ValidationConfig(device=full_device, fixture=full_fixture)

        assert config.skip_reason(Feature.BUTTON) is None
        assert config.skip_reason(Feature.BIOMETRIC) is None
        assert config.skip_reason(Feature.MOTION) is None


class TestFeatureRequirements:
    """Tests for FEATURE_REQUIREMENTS mapping."""

    def test_power_requires_nothing(self):
        """Power feature should have no capability requirements."""
        assert FEATURE_REQUIREMENTS[Feature.POWER] == []

    def test_button_requires_button_capability(self):
        """Button feature requires BUTTON capability."""
        assert Capability.BUTTON in FEATURE_REQUIREMENTS[Feature.BUTTON]

    def test_biometric_requires_ppg_hardware(self):
        """Biometric feature requires PPG servo and LED."""
        reqs = FEATURE_REQUIREMENTS[Feature.BIOMETRIC]
        assert Capability.PPG_SERVO in reqs
        assert Capability.PPG_LED in reqs

    def test_motion_requires_actuator(self):
        """Motion feature requires motion actuator."""
        assert Capability.MOTION_ACTUATOR in FEATURE_REQUIREMENTS[Feature.MOTION]

    def test_nfc_requires_reader(self):
        """NFC feature requires NFC reader."""
        assert Capability.NFC_READER in FEATURE_REQUIREMENTS[Feature.NFC]

    def test_environmental_requires_nothing(self):
        """Environmental feature has no hard requirements (peltier enhances but optional)."""
        assert FEATURE_REQUIREMENTS[Feature.ENVIRONMENTAL] == []

    def test_cellular_requires_nothing(self):
        """Cellular feature uses DUT's own modem, no bench capability needed."""
        assert FEATURE_REQUIREMENTS[Feature.CELLULAR] == []
