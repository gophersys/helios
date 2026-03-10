"""Tests for ProgrammableFixture — the test infrastructure stub.

These tests verify that the programmable fixture correctly:
1. Enforces capability checks (raises when capability missing)
2. Returns configured values
3. Tracks events for verification
4. Maintains correct internal state
"""

import pytest

from corekinect.test.validation.profiles import Capability, Feature
from corekinect.test.validation.programmable_fixture import (
    ProgrammableFixture,
    FixtureBuilder,
    FixturePresets,
    CapabilityNotAvailable,
)


class TestCapabilityEnforcement:
    """Tests that methods raise CapabilityNotAvailable when capability missing."""

    def test_button_requires_capability(self):
        """press_button raises without BUTTON capability."""
        fixture = FixtureBuilder().build()  # No capabilities

        with pytest.raises(CapabilityNotAvailable) as exc:
            fixture.press_button(0.5)

        assert exc.value.capability == Capability.BUTTON
        assert "press_button" in exc.value.method

    def test_button_works_with_capability(self):
        """press_button succeeds with BUTTON capability."""
        fixture = FixtureBuilder().with_capability(Capability.BUTTON).build()

        fixture.press_button(0.5)  # Should not raise

        assert "press_button" in fixture.event_log[-1]

    def test_long_press_requires_capability(self):
        """long_press_button raises without BUTTON capability."""
        fixture = FixtureBuilder().build()

        with pytest.raises(CapabilityNotAvailable):
            fixture.long_press_button(3.0)

    def test_led_read_requires_capability(self):
        """read_led_color raises without LED_PHOTODIODE capability."""
        fixture = FixtureBuilder().build()

        with pytest.raises(CapabilityNotAvailable) as exc:
            fixture.read_led_color()

        assert exc.value.capability == Capability.LED_PHOTODIODE

    def test_led_read_works_with_capability(self):
        """read_led_color succeeds with LED_PHOTODIODE capability."""
        fixture = FixtureBuilder().with_capability(Capability.LED_PHOTODIODE).build()

        result = fixture.read_led_color()

        assert "red" in result
        assert "green" in result
        assert "blue" in result

    def test_simulate_on_skin_requires_ppg_servo(self):
        """simulate_on_skin raises without PPG_SERVO capability."""
        fixture = FixtureBuilder().with_capability(Capability.PPG_LED).build()

        with pytest.raises(CapabilityNotAvailable) as exc:
            fixture.simulate_on_skin(True)

        assert exc.value.capability == Capability.PPG_SERVO

    def test_simulate_on_skin_requires_ppg_led(self):
        """simulate_on_skin raises without PPG_LED capability."""
        fixture = FixtureBuilder().with_capability(Capability.PPG_SERVO).build()

        with pytest.raises(CapabilityNotAvailable) as exc:
            fixture.simulate_on_skin(True)

        assert exc.value.capability == Capability.PPG_LED

    def test_simulate_on_skin_works_with_both_capabilities(self):
        """simulate_on_skin succeeds with both PPG capabilities."""
        fixture = (
            FixtureBuilder()
            .with_capability(Capability.PPG_SERVO)
            .with_capability(Capability.PPG_LED)
            .build()
        )

        fixture.simulate_on_skin(True)  # Should not raise

    def test_peltier_requires_capability(self):
        """set_peltier raises without PELTIER capability."""
        fixture = FixtureBuilder().build()

        with pytest.raises(CapabilityNotAvailable):
            fixture.set_peltier(True)

    def test_motion_requires_capability(self):
        """shake raises without MOTION_ACTUATOR capability."""
        fixture = FixtureBuilder().build()

        with pytest.raises(CapabilityNotAvailable):
            fixture.shake(5.0)

    def test_charger_requires_capability(self):
        """connect_charger raises without CHARGER_RELAY capability."""
        fixture = FixtureBuilder().build()

        with pytest.raises(CapabilityNotAvailable):
            fixture.connect_charger()


class TestPowerMethods:
    """Tests for power methods (always available, no capability check)."""

    def test_power_on_always_available(self):
        """power_on works without any capabilities."""
        fixture = FixtureBuilder().build()

        fixture.power_on()

        assert "power_on" in fixture.event_log[-1]

    def test_power_off_always_available(self):
        """power_off works without any capabilities."""
        fixture = FixtureBuilder().build()

        fixture.power_off()

        assert "power_off" in fixture.event_log[-1]

    def test_verify_dut_powered_returns_configured_state(self):
        """verify_dut_powered returns configured power state."""
        powered_fixture = FixtureBuilder().with_powered(True).build()
        unpowered_fixture = FixtureBuilder().with_powered(False).build()

        assert powered_fixture.verify_dut_powered() is True
        assert unpowered_fixture.verify_dut_powered() is False

    def test_read_dut_current_returns_configured_value(self):
        """read_dut_current returns pre-configured current."""
        fixture = FixtureBuilder().with_dut_current(25.0).build()

        current = fixture.read_dut_current()

        assert current == 25.0

    def test_read_dut_current_zero_when_off(self):
        """read_dut_current returns near-zero when device is off."""
        fixture = FixtureBuilder().with_powered(False).with_dut_current(25.0).build()

        current = fixture.read_dut_current()

        assert current < 1.0  # Leakage current

    def test_read_total_current_sums_channels(self):
        """read_total_current returns sum of DUT + charger current."""
        fixture = (
            FixtureBuilder()
            .with_dut_current(15.0)
            .with_charger_current(20.0)
            .with_powered(True)
            .build()
        )

        total = fixture.read_total_current()

        assert total == 35.0

    def test_primary_power_channel_battery_mode(self):
        """primary_power_channel returns 1 in battery mode."""
        fixture = FixtureBuilder().with_battery(installed=True).build()

        assert fixture.primary_power_channel == 1

    def test_primary_power_channel_batteryless_mode(self):
        """primary_power_channel returns 0 in batteryless mode."""
        fixture = FixtureBuilder().with_battery(installed=False).build()

        assert fixture.primary_power_channel == 0


class TestConfigurableResponses:
    """Tests for configuring fixture responses."""

    def test_configure_led_idle(self):
        """Can configure LED reading when button not pressed."""
        fixture = (
            FixtureBuilder()
            .with_capability(Capability.LED_PHOTODIODE)
            .build()
        )
        fixture.configure_led_idle(red=0.1, green=0.2, blue=0.3)

        # Button not pressed — should return idle colors
        result = fixture.read_led_color()

        assert result["red"] == 0.1
        assert result["green"] == 0.2
        assert result["blue"] == 0.3

    def test_configure_led_after_press(self):
        """Can configure LED reading after button press."""
        fixture = (
            FixtureBuilder()
            .with_capability(Capability.BUTTON)
            .with_capability(Capability.LED_PHOTODIODE)
            .build()
        )
        fixture.configure_led_after_press(red=0.9, green=0.1, blue=0.0)

        fixture.press_button(0.5)
        result = fixture.read_led_color()

        assert result["red"] == 0.9
        assert result["green"] == 0.1
        assert result["blue"] == 0.0

    def test_configure_temperature(self):
        """Can configure temperature readings."""
        fixture = FixtureBuilder().with_capability(Capability.PELTIER).build()
        fixture.configure_temperature(baseline=2.0, heated=3.5)

        # Not heated — baseline
        assert fixture.read_temperature() == 2.0

        # Heat on
        fixture.set_peltier(True)
        assert fixture.read_temperature() == 3.5

    def test_configure_power_rails(self):
        """Can configure power rail readings."""
        fixture = FixtureBuilder().build()
        fixture.configure_power_rails(sys=4.2, batt_sys=3.8)

        rails = fixture.read_power_rails()

        assert rails["sys"] == 4.2
        assert rails["batt_sys"] == 3.8


class TestEventLogging:
    """Tests for event logging functionality."""

    def test_events_logged_in_order(self):
        """Events are logged in call order."""
        fixture = FixtureBuilder().with_capability(Capability.BUTTON).build()

        fixture.power_on()
        fixture.press_button(0.5)
        fixture.power_off()

        assert len(fixture.events) == 3
        assert fixture.events[0].method == "power_on"
        assert fixture.events[1].method == "press_button"
        assert fixture.events[2].method == "power_off"

    def test_event_log_strings(self):
        """event_log provides simple string representation."""
        fixture = FixtureBuilder().with_capability(Capability.BUTTON).build()

        fixture.press_button(0.5)

        assert "press_button" in fixture.event_log[0]
        assert "0.5" in fixture.event_log[0]

    def test_clear_events(self):
        """clear_events empties the event log."""
        fixture = FixtureBuilder().build()

        fixture.power_on()
        fixture.power_off()
        assert len(fixture.events) == 2

        fixture.clear_events()
        assert len(fixture.events) == 0


class TestStateTracking:
    """Tests for internal state tracking."""

    def test_power_on_sets_powered_state(self):
        """power_on sets internal powered state to True."""
        fixture = FixtureBuilder().with_powered(False).build()

        assert fixture.verify_dut_powered() is False

        fixture.power_on()

        assert fixture.verify_dut_powered() is True

    def test_power_off_clears_powered_state(self):
        """power_off sets internal powered state to False."""
        fixture = FixtureBuilder().with_powered(True).build()

        fixture.power_off()

        assert fixture.verify_dut_powered() is False

    def test_long_press_8s_powers_off(self):
        """8s+ button press triggers power off (device behavior)."""
        fixture = (
            FixtureBuilder()
            .with_capability(Capability.BUTTON)
            .with_powered(True)
            .build()
        )

        fixture.long_press_button(8.0)

        assert fixture.verify_dut_powered() is False

    def test_long_press_3s_does_not_power_off(self):
        """3s button press does not power off."""
        fixture = (
            FixtureBuilder()
            .with_capability(Capability.BUTTON)
            .with_powered(True)
            .build()
        )

        fixture.long_press_button(3.0)

        assert fixture.verify_dut_powered() is True

    def test_flash_firmware_resets_state(self):
        """flash_firmware resets all transient state."""
        fixture = (
            FixtureBuilder()
            .with_capability(Capability.BUTTON)
            .with_capability(Capability.PELTIER)
            .with_powered(False)
            .build()
        )
        fixture._peltier_active = True
        fixture._button_pressed = True

        fixture.flash_firmware("test.hex")

        assert fixture.verify_dut_powered() is True
        assert fixture._peltier_active is False
        assert fixture._button_pressed is False


class TestFixtureBuilder:
    """Tests for FixtureBuilder fluent API."""

    def test_builder_default_values(self):
        """Builder produces fixture with sensible defaults."""
        fixture = FixtureBuilder().build()

        assert fixture.profile.station_id == "stub-fixture"
        assert fixture.profile.product == "alpha"
        assert len(fixture.profile.capabilities) == 0

    def test_builder_with_station_id(self):
        """Can set station ID via builder."""
        fixture = FixtureBuilder().with_station_id("station-99").build()

        assert fixture.profile.station_id == "station-99"

    def test_builder_with_product(self):
        """Can set product and board via builder."""
        fixture = FixtureBuilder().with_product("sigma5", "sigma5_c0").build()

        assert fixture.profile.product == "sigma5"
        assert fixture.profile.board == "sigma5_c0"

    def test_builder_with_multiple_capabilities(self):
        """Can add multiple capabilities via builder."""
        fixture = (
            FixtureBuilder()
            .with_capabilities(
                Capability.BUTTON,
                Capability.PELTIER,
                Capability.CHARGER_RELAY,
            )
            .build()
        )

        assert fixture.has_capability(Capability.BUTTON)
        assert fixture.has_capability(Capability.PELTIER)
        assert fixture.has_capability(Capability.CHARGER_RELAY)
        assert not fixture.has_capability(Capability.PPG_SERVO)

    def test_builder_with_dut(self):
        """Can set DUT identity via builder."""
        fixture = FixtureBuilder().with_dut("ABCD1234", "9999").build()

        assert fixture.profile.dut.device_id == "ABCD1234"
        assert fixture.profile.dut.snr == "9999"

    def test_builder_creates_hardware_configs_from_capabilities(self):
        """Builder auto-creates hardware configs based on capabilities."""
        fixture = (
            FixtureBuilder()
            .with_capability(Capability.BUTTON)
            .with_capability(Capability.PELTIER)
            .build()
        )

        assert fixture.profile.button is not None
        assert fixture.profile.button.gpio_pin == 2
        assert fixture.profile.peltier is not None
        assert fixture.profile.peltier.gpio_pin == 4
        assert fixture.profile.ppg_simulator is None  # Not in capabilities


class TestFixturePresets:
    """Tests for pre-built fixture configurations."""

    def test_minimal_has_no_capabilities(self):
        """minimal() creates fixture with no capabilities."""
        fixture = FixturePresets.minimal()

        assert len(fixture.profile.capabilities) == 0

    def test_button_only_has_button(self):
        """button_only() creates fixture with only BUTTON capability."""
        fixture = FixturePresets.button_only()

        assert fixture.has_capability(Capability.BUTTON)
        assert not fixture.has_capability(Capability.PELTIER)

    def test_alpha_b0_basic_has_expected_capabilities(self):
        """alpha_b0_basic() has button, peltier, charger_relay."""
        fixture = FixturePresets.alpha_b0_basic()

        assert fixture.has_capability(Capability.BUTTON)
        assert fixture.has_capability(Capability.PELTIER)
        assert fixture.has_capability(Capability.CHARGER_RELAY)
        assert not fixture.has_capability(Capability.PPG_SERVO)

    def test_alpha_b0_full_has_all_capabilities(self):
        """alpha_b0_full() has all possible capabilities."""
        fixture = FixturePresets.alpha_b0_full()

        assert fixture.has_capability(Capability.BUTTON)
        assert fixture.has_capability(Capability.PELTIER)
        assert fixture.has_capability(Capability.PPG_SERVO)
        assert fixture.has_capability(Capability.PPG_LED)
        assert fixture.has_capability(Capability.LED_PHOTODIODE)
        assert fixture.has_capability(Capability.NFC_READER)
        assert fixture.has_capability(Capability.MOTION_ACTUATOR)

    def test_device_off_simulates_unpowered(self):
        """device_off() creates fixture with powered=False."""
        fixture = FixturePresets.device_off()

        assert fixture.verify_dut_powered() is False
        assert fixture.read_dut_current() < 1.0

    def test_over_budget_simulates_high_current(self):
        """over_budget() creates fixture with high current draw."""
        fixture = FixturePresets.over_budget()

        current = fixture.read_dut_current()

        assert current > 40.0  # Way over typical budget


class TestCallbackHooks:
    """Tests for callback hooks on fixture events."""

    def test_on_power_on_callback(self):
        """on_power_on callback is invoked on power_on."""
        fixture = FixtureBuilder().build()
        callback_called = []

        fixture.on_power_on(lambda: callback_called.append("power_on"))
        fixture.power_on()

        assert "power_on" in callback_called

    def test_on_power_off_callback(self):
        """on_power_off callback is invoked on power_off."""
        fixture = FixtureBuilder().build()
        callback_called = []

        fixture.on_power_off(lambda: callback_called.append("power_off"))
        fixture.power_off()

        assert "power_off" in callback_called

    def test_on_button_press_callback_receives_duration(self):
        """on_button_press callback receives duration argument."""
        fixture = FixtureBuilder().with_capability(Capability.BUTTON).build()
        durations = []

        fixture.on_button_press(lambda d: durations.append(d))
        fixture.press_button(2.5)

        assert durations == [2.5]
