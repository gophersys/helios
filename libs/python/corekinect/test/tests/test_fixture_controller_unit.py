"""Unit tests for corekinect.test.fixture_controller.

Tests the logic paths of FixtureController without real MTIB hardware.
Uses MagicMock for the MTIB client, verifying GPIO calls, capability
gating, voltage validation, and power channel selection.
"""

from unittest.mock import MagicMock, call

import pytest

from corekinect.errors import HardwareError
from corekinect.test.fixture_controller import FixtureController
from corekinect.capabilities import Capability
from corekinect.test.profiles import (
    ButtonConfig,
    ChargerRelayConfig,
    DutConfig,
    FixtureProfile,
    PeltierConfig,
    PowerConfig,
    PpgSimulatorConfig,
)
from corekinect.test.programmable_fixture import CapabilityNotAvailable
from corekinect.mtib_client.v1.client.types import GpioDirection, GpioResistorConfig


# =============================================================================
# Helpers
# =============================================================================


def _make_profile(
    battery_installed=False,
    capabilities=None,
    button=None,
    peltier=None,
    charger_relay=None,
    ppg_simulator=None,
    station_id="test-bench",
):
    """Build a FixtureProfile with the given parameters."""
    caps = set(capabilities) if capabilities else set()
    return FixtureProfile(
        station_id=station_id,
        product="alpha",
        board="b0",
        mtib_revision="1.2",
        capabilities=caps,
        power=PowerConfig(battery_installed=battery_installed),
        dut=DutConfig(device_id="TESTDEV", snr="0000"),
        button=button,
        ppg_simulator=ppg_simulator,
        peltier=peltier,
        charger_relay=charger_relay,
    )


def _make_mtib():
    """Create a MagicMock MTIB client where all calls return no error."""
    mtib = MagicMock()
    mtib.GpioConfig.return_value = None
    mtib.GpioWrite.return_value = None
    mtib.PowerEnable.return_value = None
    mtib.PowerDisable.return_value = None
    return mtib


# =============================================================================
# _check_error
# =============================================================================


class TestCheckError:
    def test_none_error_does_not_raise(self):
        profile = _make_profile()
        ctrl = FixtureController(_make_mtib(), profile)
        ctrl._check_error(None, "test_op")  # should not raise

    def test_string_error_raises_hardware_error(self):
        profile = _make_profile()
        ctrl = FixtureController(_make_mtib(), profile)
        with pytest.raises(HardwareError, match="test_op failed: something broke"):
            ctrl._check_error("something broke", "test_op")

    def test_empty_string_is_falsy_does_not_raise(self):
        profile = _make_profile()
        ctrl = FixtureController(_make_mtib(), profile)
        # Empty string is falsy, so no raise
        ctrl._check_error("", "test_op")


# =============================================================================
# require_capability / has_capability
# =============================================================================


class TestCapabilityChecks:
    def test_has_capability_true(self):
        profile = _make_profile(capabilities=[Capability.BUTTON])
        ctrl = FixtureController(_make_mtib(), profile)
        assert ctrl.has_capability(Capability.BUTTON) is True

    def test_has_capability_false(self):
        profile = _make_profile(capabilities=[])
        ctrl = FixtureController(_make_mtib(), profile)
        assert ctrl.has_capability(Capability.BUTTON) is False

    def test_require_capability_present_no_raise(self):
        profile = _make_profile(capabilities=[Capability.BUTTON])
        ctrl = FixtureController(_make_mtib(), profile)
        ctrl.require_capability(Capability.BUTTON, "press_button")

    def test_require_capability_missing_raises(self):
        profile = _make_profile(capabilities=[])
        ctrl = FixtureController(_make_mtib(), profile)
        with pytest.raises(CapabilityNotAvailable):
            ctrl.require_capability(Capability.BUTTON, "press_button")

    def test_require_capability_error_contains_details(self):
        profile = _make_profile(capabilities=[], station_id="bench-42")
        ctrl = FixtureController(_make_mtib(), profile)
        with pytest.raises(CapabilityNotAvailable) as exc_info:
            ctrl.require_capability(Capability.PPG_SERVO, "simulate_on_skin")
        assert "bench-42" in str(exc_info.value)
        assert "ppg_servo" in str(exc_info.value)


# =============================================================================
# primary_power_channel
# =============================================================================


class TestPrimaryPowerChannel:
    def test_batteryless_returns_channel_0(self):
        profile = _make_profile(battery_installed=False)
        ctrl = FixtureController(_make_mtib(), profile)
        assert ctrl.primary_power_channel == 0

    def test_battery_returns_channel_1(self):
        profile = _make_profile(battery_installed=True)
        ctrl = FixtureController(_make_mtib(), profile)
        assert ctrl.primary_power_channel == 1


# =============================================================================
# configure_stimulus_gpios
# =============================================================================


class TestConfigureStimulusGpios:
    def test_configures_button_gpio(self):
        button = ButtonConfig(gpio_pin=2, active_low=True)
        profile = _make_profile(
            capabilities=[Capability.BUTTON],
            button=button,
        )
        mtib = _make_mtib()
        ctrl = FixtureController(mtib, profile)
        ctrl.configure_stimulus_gpios()

        # Should configure gpio 2 as OUTPUT
        mtib.GpioConfig.assert_any_call(2, GpioDirection.OUTPUT, GpioResistorConfig.NONE)
        # active_low button: initial state = HIGH (released)
        mtib.GpioWrite.assert_any_call(2, True)

    def test_configures_peltier_gpio(self):
        peltier = PeltierConfig(gpio_pin=4, temp_adc_channel=7)
        profile = _make_profile(
            capabilities=[Capability.PELTIER],
            peltier=peltier,
        )
        mtib = _make_mtib()
        ctrl = FixtureController(mtib, profile)
        ctrl.configure_stimulus_gpios()

        mtib.GpioConfig.assert_any_call(4, GpioDirection.OUTPUT, GpioResistorConfig.NONE)
        mtib.GpioWrite.assert_any_call(4, False)  # peltier OFF initially

    def test_configures_charger_relay_gpio(self):
        relay = ChargerRelayConfig(gpio_pin=5, active_high=True)
        profile = _make_profile(
            capabilities=[Capability.CHARGER_RELAY],
            charger_relay=relay,
        )
        mtib = _make_mtib()
        ctrl = FixtureController(mtib, profile)
        ctrl.configure_stimulus_gpios()

        mtib.GpioConfig.assert_any_call(5, GpioDirection.OUTPUT, GpioResistorConfig.NONE)
        # active_high relay: initial state = not active_high = False (open)
        mtib.GpioWrite.assert_any_call(5, False)

    def test_skips_missing_capabilities(self):
        profile = _make_profile(capabilities=[])
        mtib = _make_mtib()
        ctrl = FixtureController(mtib, profile)
        ctrl.configure_stimulus_gpios()

        mtib.GpioConfig.assert_not_called()
        mtib.GpioWrite.assert_not_called()

    def test_idempotent_after_success(self):
        button = ButtonConfig(gpio_pin=2, active_low=True)
        profile = _make_profile(capabilities=[Capability.BUTTON], button=button)
        mtib = _make_mtib()
        ctrl = FixtureController(mtib, profile)

        ctrl.configure_stimulus_gpios()
        first_call_count = mtib.GpioConfig.call_count

        ctrl.configure_stimulus_gpios()
        assert mtib.GpioConfig.call_count == first_call_count  # not called again

    def test_failure_leaves_unconfigured(self):
        button = ButtonConfig(gpio_pin=2, active_low=True)
        profile = _make_profile(capabilities=[Capability.BUTTON], button=button)
        mtib = _make_mtib()
        mtib.GpioConfig.return_value = "GPIO error"
        ctrl = FixtureController(mtib, profile)

        ctrl.configure_stimulus_gpios()
        assert ctrl._gpios_configured is False

        # Should retry on next call since _gpios_configured is False
        mtib.GpioConfig.return_value = None
        ctrl.configure_stimulus_gpios()
        assert ctrl._gpios_configured is True


# =============================================================================
# power_on voltage validation
# =============================================================================


class TestPowerOnVoltageValidation:
    def test_negative_voltage_raises(self):
        profile = _make_profile()
        ctrl = FixtureController(_make_mtib(), profile)
        with pytest.raises(HardwareError, match="out of safe range"):
            ctrl.power_on(voltage=-1.0)

    def test_too_high_voltage_raises(self):
        profile = _make_profile()
        ctrl = FixtureController(_make_mtib(), profile)
        with pytest.raises(HardwareError, match="out of safe range"):
            ctrl.power_on(voltage=7.0)

    def test_boundary_voltage_zero_ok(self):
        profile = _make_profile()
        mtib = _make_mtib()
        ctrl = FixtureController(mtib, profile)
        ctrl.power_on(voltage=0.0)  # should not raise

    def test_boundary_voltage_six_ok(self):
        profile = _make_profile()
        mtib = _make_mtib()
        ctrl = FixtureController(mtib, profile)
        ctrl.power_on(voltage=6.0)  # should not raise

    def test_default_voltage_from_profile(self):
        profile = _make_profile()
        mtib = _make_mtib()
        ctrl = FixtureController(mtib, profile)
        ctrl.power_on()
        # Profile default is 4.5V — PowerEnable should have been called with it
        calls = mtib.PowerEnable.call_args_list
        assert any(c.kwargs.get("voltage_v") == 4.5 or (len(c.args) > 1 and c.args[1] == 4.5)
                   for c in calls) or any("4.5" in str(c) for c in calls)

    def test_batteryless_does_not_enable_charger(self):
        profile = _make_profile(battery_installed=False)
        mtib = _make_mtib()
        ctrl = FixtureController(mtib, profile)
        ctrl.power_on()
        # Only one PowerEnable call (DUT channel, not charger)
        assert mtib.PowerEnable.call_count == 1

    def test_battery_mode_enables_charger(self):
        profile = _make_profile(battery_installed=True)
        mtib = _make_mtib()
        ctrl = FixtureController(mtib, profile)
        ctrl.power_on()
        # Two PowerEnable calls (DUT + charger)
        assert mtib.PowerEnable.call_count == 2

    def test_power_enable_error_raises(self):
        profile = _make_profile()
        mtib = _make_mtib()
        mtib.PowerEnable.return_value = "channel fault"
        ctrl = FixtureController(mtib, profile)
        with pytest.raises(HardwareError, match="PowerEnable"):
            ctrl.power_on()


# =============================================================================
# power_off
# =============================================================================


class TestPowerOff:
    def test_batteryless_disables_only_dut(self):
        profile = _make_profile(battery_installed=False)
        mtib = _make_mtib()
        ctrl = FixtureController(mtib, profile)
        ctrl.power_off()
        assert mtib.PowerDisable.call_count == 1

    def test_battery_mode_disables_both(self):
        profile = _make_profile(battery_installed=True)
        mtib = _make_mtib()
        ctrl = FixtureController(mtib, profile)
        ctrl.power_off()
        assert mtib.PowerDisable.call_count == 2


# =============================================================================
# _resolve_target
# =============================================================================


class TestResolveTarget:
    def test_valid_targets(self):
        profile = _make_profile()
        ctrl = FixtureController(_make_mtib(), profile)
        # These should not raise
        ctrl._resolve_target("nrf52840")
        ctrl._resolve_target("nrf9151")
        ctrl._resolve_target("NRF52840")  # case insensitive

    def test_invalid_target_raises(self):
        profile = _make_profile()
        ctrl = FixtureController(_make_mtib(), profile)
        with pytest.raises(ValueError, match="Unknown target"):
            ctrl._resolve_target("stm32")
