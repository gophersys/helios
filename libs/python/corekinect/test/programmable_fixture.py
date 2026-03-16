"""Programmable fixture stub for unit testing validation tests.

This module provides a fully programmable fixture that can simulate
any hardware behavior, including:
- Capability-based method gating (raises if capability missing)
- Configurable return values for all methods
- Event logging for interaction verification
- Scenario injection for complex multi-step tests

The goal is to test the test logic itself without real hardware.
When you run tests against this stub, you verify that:
1. Tests correctly check capabilities before calling methods
2. Tests correctly interpret return values
3. Tests correctly handle edge cases and failures

Usage:
    from corekinect.test.programmable_fixture import (
        ProgrammableFixture, FixtureBuilder
    )

    # Create fixture with specific capabilities
    fixture = (
        FixtureBuilder()
        .with_capability(Capability.BUTTON)
        .with_capability(Capability.PELTIER)
        .with_dut_current(15.0)
        .with_led_response(red=0.0, green=0.8, blue=0.0)
        .build()
    )

    # Test that button press works
    fixture.press_button(0.5)
    assert "press_button" in fixture.event_log[-1]

    # Test that PPG fails without capability
    with pytest.raises(CapabilityNotAvailable):
        fixture.simulate_on_skin(True)
"""

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Set, Tuple, Any
from enum import Enum
import time

from .profiles import (
    Capability,
    Feature,
    FixtureProfile,
    PowerConfig,
    DutConfig,
    ButtonConfig,
    PpgSimulatorConfig,
    PeltierConfig,
    ChargerRelayConfig,
    LedSensorConfig,
    NfcReaderConfig,
    MotionConfig,
)


class CapabilityNotAvailable(Exception):
    """Raised when a method requires a capability the fixture doesn't have."""

    def __init__(self, capability: Capability, method: str, station_id: str = "stub"):
        self.capability = capability
        self.method = method
        self.station_id = station_id
        super().__init__(
            f"Fixture '{station_id}' cannot call {method}() — "
            f"missing capability: {capability.value}"
        )


@dataclass
class PowerReading:
    """Power measurement result."""

    current_ma: float
    voltage_v: float = 4.5
    power_mw: float = 0.0

    def __post_init__(self):
        if self.power_mw == 0.0:
            self.power_mw = self.current_ma * self.voltage_v


@dataclass
class LedReading:
    """LED color measurement result."""

    red: float
    green: float
    blue: float

    def to_dict(self) -> Dict[str, float]:
        return {"red": self.red, "green": self.green, "blue": self.blue}


@dataclass
class Event:
    """Recorded fixture interaction event."""

    timestamp: float
    method: str
    args: Tuple
    kwargs: Dict
    result: Any = None
    error: Optional[Exception] = None

    def __str__(self) -> str:
        args_str = ", ".join(repr(a) for a in self.args)
        kwargs_str = ", ".join(f"{k}={v!r}" for k, v in self.kwargs.items())
        all_args = ", ".join(filter(None, [args_str, kwargs_str]))
        return f"{self.method}({all_args})"


class ProgrammableFixture:
    """Fully programmable fixture stub for testing validation test logic.

    Key features:
    1. Capability checking — methods raise CapabilityNotAvailable if
       the fixture doesn't have the required capability
    2. Configurable responses — pre-program what methods return
    3. Event logging — track all method calls for verification
    4. State tracking — internal state changes based on method calls

    This enables testing the tests themselves:
    - Verify tests skip when capabilities are missing
    - Verify tests pass with good values
    - Verify tests fail with bad values
    - Verify tests call methods in correct order
    """

    def __init__(self, profile: FixtureProfile):
        self._profile = profile
        self._events: List[Event] = []

        # Internal state
        self._powered = True
        self._peltier_active = False
        self._skin_on = False
        self._button_pressed = False
        self._charger_connected = False
        self._motion_active = False

        # Configurable responses
        self._dut_current_ma = 15.0
        self._charger_current_ma = 20.0
        self._dut_voltage_v = 4.5
        self._led_idle = LedReading(0.0, 0.0, 0.0)
        self._led_after_press = LedReading(0.0, 0.8, 0.0)
        self._temp_baseline = 2.5
        self._temp_heated = 2.8
        self._power_rails = {"3v3": 3.30, "batt_sys": 4.20, "vbckp": 3.30, "sys": 4.50}

        # Callback hooks for advanced scenarios
        self._on_power_on: Optional[Callable[[], None]] = None
        self._on_power_off: Optional[Callable[[], None]] = None
        self._on_button_press: Optional[Callable[[float], None]] = None

    @property
    def profile(self) -> FixtureProfile:
        return self._profile

    @property
    def events(self) -> List[Event]:
        return list(self._events)

    @property
    def event_log(self) -> List[str]:
        """Simple string log of events for quick assertions."""
        return [str(e) for e in self._events]

    def clear_events(self) -> None:
        """Clear the event log."""
        self._events.clear()

    # ═══════════════════════════════════════════════════════════════════════
    # Capability checking
    # ═══════════════════════════════════════════════════════════════════════

    def has_capability(self, cap: Capability) -> bool:
        """Check if this fixture has a specific capability."""
        return self._profile.has_capability(cap)

    def require_capability(self, cap: Capability, method: str) -> None:
        """Raise if capability is missing."""
        if not self.has_capability(cap):
            raise CapabilityNotAvailable(cap, method, self._profile.station_id)

    def _record(self, method: str, *args, result=None, error=None, **kwargs) -> Event:
        """Record a method call."""
        event = Event(
            timestamp=time.time(),
            method=method,
            args=args,
            kwargs=kwargs,
            result=result,
            error=error,
        )
        self._events.append(event)
        return event

    # ═══════════════════════════════════════════════════════════════════════
    # Configuration API — pre-program responses
    # ═══════════════════════════════════════════════════════════════════════

    def configure_current(
        self, dut_ma: float = 15.0, charger_ma: float = 20.0
    ) -> "ProgrammableFixture":
        """Set current readings for power tests."""
        self._dut_current_ma = dut_ma
        self._charger_current_ma = charger_ma
        return self

    def configure_led_idle(
        self, red: float = 0.0, green: float = 0.0, blue: float = 0.0
    ) -> "ProgrammableFixture":
        """Set LED reading when button not pressed."""
        self._led_idle = LedReading(red, green, blue)
        return self

    def configure_led_after_press(
        self, red: float = 0.0, green: float = 0.8, blue: float = 0.0
    ) -> "ProgrammableFixture":
        """Set LED reading after button press."""
        self._led_after_press = LedReading(red, green, blue)
        return self

    def configure_temperature(
        self, baseline: float = 2.5, heated: float = 2.8
    ) -> "ProgrammableFixture":
        """Set temperature readings (baseline and with peltier active)."""
        self._temp_baseline = baseline
        self._temp_heated = heated
        return self

    def configure_power_rails(self, **rails: float) -> "ProgrammableFixture":
        """Set power rail voltage readings."""
        self._power_rails.update(rails)
        return self

    def configure_powered(self, powered: bool) -> "ProgrammableFixture":
        """Set initial power state."""
        self._powered = powered
        return self

    def on_power_on(self, callback: Callable[[], None]) -> "ProgrammableFixture":
        """Register callback for power_on events."""
        self._on_power_on = callback
        return self

    def on_power_off(self, callback: Callable[[], None]) -> "ProgrammableFixture":
        """Register callback for power_off events."""
        self._on_power_off = callback
        return self

    def on_button_press(
        self, callback: Callable[[float], None]
    ) -> "ProgrammableFixture":
        """Register callback for button press events."""
        self._on_button_press = callback
        return self

    # ═══════════════════════════════════════════════════════════════════════
    # Power methods (always available)
    # ═══════════════════════════════════════════════════════════════════════

    @property
    def primary_power_channel(self) -> int:
        """Return the power channel that carries DUT current."""
        return 1 if self._profile.power.battery_installed else 0

    @property
    def battery_installed(self) -> bool:
        """Check if battery mode is enabled."""
        return self._profile.power.battery_installed

    def power_on(
        self, voltage: Optional[float] = None, with_charger: Optional[bool] = None
    ) -> None:
        """Enable DUT power."""
        self._record("power_on", voltage=voltage, with_charger=with_charger)
        self._powered = True
        self._button_pressed = False
        if self._on_power_on:
            self._on_power_on()

    def power_off(self) -> None:
        """Disable DUT power."""
        self._record("power_off")
        self._powered = False
        self._button_pressed = False
        if self._on_power_off:
            self._on_power_off()

    def power_cycle(self, off_duration_s: float = 2.0) -> None:
        """Power off, wait, power on."""
        self._record("power_cycle", off_duration_s=off_duration_s)
        self._powered = True
        self._button_pressed = False

    def verify_dut_powered(
        self, min_current_ma: float = 5.0, samples: int = 10
    ) -> bool:
        """Verify DUT is drawing expected current."""
        result = self._powered and self._dut_current_ma >= min_current_ma
        self._record(
            "verify_dut_powered",
            min_current_ma=min_current_ma,
            samples=samples,
            result=result,
        )
        return result

    def read_dut_current(self) -> float:
        """Read DUT power rail current in mA."""
        current = self._dut_current_ma if self._powered else 0.5
        self._record("read_dut_current", result=current)
        return current

    def read_charger_current(self) -> float:
        """Read charger rail current in mA."""
        current = self._charger_current_ma if self._powered else 0.0
        self._record("read_charger_current", result=current)
        return current

    def read_total_current(self) -> float:
        """Read total current (DUT + charger) in mA."""
        total = self.read_dut_current() + self.read_charger_current()
        # Don't double-record — the individual reads already recorded
        return total

    def read_power_rails(self) -> Dict[str, float]:
        """Read manufacturing ADC rail voltages."""
        self._record("read_power_rails", result=self._power_rails)
        return dict(self._power_rails)

    # ═══════════════════════════════════════════════════════════════════════
    # Button methods (requires BUTTON capability)
    # ═══════════════════════════════════════════════════════════════════════

    def press_button(self, duration_s: float = 0.5) -> None:
        """Simulate button press."""
        self.require_capability(Capability.BUTTON, "press_button")
        self._record("press_button", duration_s=duration_s)
        self._button_pressed = True
        if self._on_button_press:
            self._on_button_press(duration_s)

    def long_press_button(self, duration_s: float = 3.0) -> None:
        """Simulate long button press."""
        self.require_capability(Capability.BUTTON, "long_press_button")
        self._record("long_press_button", duration_s=duration_s)
        # 8s+ press triggers power off (device behavior)
        if duration_s >= 8.0:
            self._powered = False

    # ═══════════════════════════════════════════════════════════════════════
    # LED methods (requires LED_PHOTODIODE capability)
    # ═══════════════════════════════════════════════════════════════════════

    def read_led_color(self) -> Dict[str, float]:
        """Read LED photodiode ADC channels."""
        self.require_capability(Capability.LED_PHOTODIODE, "read_led_color")
        reading = self._led_after_press if self._button_pressed else self._led_idle
        result = reading.to_dict()
        self._record("read_led_color", result=result)
        return result

    # ═══════════════════════════════════════════════════════════════════════
    # PPG Simulator methods (requires PPG_SERVO + PPG_LED capabilities)
    # ═══════════════════════════════════════════════════════════════════════

    def simulate_on_skin(self, on: bool = True) -> None:
        """Simulate skin contact by moving PPG IR blocker servo."""
        self.require_capability(Capability.PPG_SERVO, "simulate_on_skin")
        self.require_capability(Capability.PPG_LED, "simulate_on_skin")
        self._record("simulate_on_skin", on=on)
        self._skin_on = on

    def simulate_heartbeat(self, bpm: int = 72) -> None:
        """Start pulsing green LED array at heart-rate frequency."""
        self.require_capability(Capability.PPG_LED, "simulate_heartbeat")
        self._record("simulate_heartbeat", bpm=bpm)

    def stop_heartbeat(self) -> None:
        """Stop pulsing green LED array."""
        self.require_capability(Capability.PPG_LED, "stop_heartbeat")
        self._record("stop_heartbeat")

    # ═══════════════════════════════════════════════════════════════════════
    # Peltier methods (requires PELTIER capability)
    # ═══════════════════════════════════════════════════════════════════════

    def set_peltier(self, on: bool) -> None:
        """Drive peltier heater element."""
        self.require_capability(Capability.PELTIER, "set_peltier")
        self._record("set_peltier", on=on)
        self._peltier_active = on

    def read_temperature(self) -> float:
        """Read thermistor ADC channel."""
        # Temperature reading doesn't strictly require peltier capability
        # — the ADC channel exists regardless
        temp = self._temp_heated if self._peltier_active else self._temp_baseline
        self._record("read_temperature", result=temp)
        return temp

    # ═══════════════════════════════════════════════════════════════════════
    # Charger methods (requires CHARGER_RELAY capability)
    # ═══════════════════════════════════════════════════════════════════════

    def connect_charger(self) -> None:
        """Close charger relay."""
        self.require_capability(Capability.CHARGER_RELAY, "connect_charger")
        self._record("connect_charger")
        self._charger_connected = True

    def disconnect_charger(self) -> None:
        """Open charger relay."""
        self.require_capability(Capability.CHARGER_RELAY, "disconnect_charger")
        self._record("disconnect_charger")
        self._charger_connected = False

    def charger_power_on(self) -> None:
        """Enable charger power rail."""
        self.require_capability(Capability.CHARGER_RELAY, "charger_power_on")
        self._record("charger_power_on")

    def charger_power_off(self) -> None:
        """Disable charger power rail."""
        self.require_capability(Capability.CHARGER_RELAY, "charger_power_off")
        self._record("charger_power_off")

    # ═══════════════════════════════════════════════════════════════════════
    # Motion methods (requires MOTION_ACTUATOR capability)
    # ═══════════════════════════════════════════════════════════════════════

    def shake(self, duration_s: float = 5.0, speed_mm_s: float = 50.0) -> None:
        """Drive linear actuator for motion simulation."""
        self.require_capability(Capability.MOTION_ACTUATOR, "shake")
        self._record("shake", duration_s=duration_s, speed_mm_s=speed_mm_s)
        self._motion_active = True

    def stop_motion(self) -> None:
        """Stop linear actuator."""
        self.require_capability(Capability.MOTION_ACTUATOR, "stop_motion")
        self._record("stop_motion")
        self._motion_active = False

    # ═══════════════════════════════════════════════════════════════════════
    # Firmware flash (always available — uses J-Link via MTIB)
    # ═══════════════════════════════════════════════════════════════════════

    def flash_firmware(self, hex_path: str, target: str = "nrf52840") -> None:
        """Flash firmware via J-Link."""
        self._record("flash_firmware", hex_path=hex_path, target=target)
        # Flash resets all transient state
        self._powered = True
        self._button_pressed = False
        self._peltier_active = False
        self._skin_on = False
        self._motion_active = False

    def upload_firmware(self, local_path: str, target: str = "nrf52840") -> None:
        """Upload firmware file to MTIB server."""
        self._record("upload_firmware", local_path=local_path, target=target)


class FixtureBuilder:
    """Builder for creating ProgrammableFixture instances.

    Provides a fluent API for constructing fixtures with specific
    capabilities and configurations.

    Usage:
        fixture = (
            FixtureBuilder()
            .with_station_id("test-station")
            .with_product("alpha", "b0")
            .with_capability(Capability.BUTTON)
            .with_capability(Capability.PELTIER)
            .with_dut_current(15.0)
            .build()
        )
    """

    def __init__(self):
        self._station_id = "stub-fixture"
        self._product = "alpha"
        self._board = "alpha_b0"
        self._mtib_revision = "1.2"
        self._capabilities: Set[Capability] = set()
        self._battery_installed = False
        self._dut_voltage = 4.5
        self._charger_voltage = 5.0
        self._boot_settle_s = 0.01  # Fast for tests
        self._device_id = "70B3D584C01E1FCC"
        self._snr = "0000"

        # Hardware configs
        self._button_gpio = 2
        self._button_active_low = True
        self._ppg_servo_pwm_pin = 7
        self._ppg_servo_blocked_us = 1000
        self._ppg_servo_exposed_us = 2000
        self._ppg_hr_led_gpio = 3
        self._peltier_gpio = 4
        self._peltier_temp_adc = 7
        self._charger_relay_gpio = 5
        self._charger_relay_active_high = True
        self._led_red_adc = 4
        self._led_green_adc = 5
        self._led_blue_adc = 6

        # Programmable values
        self._dut_current_ma = 15.0
        self._charger_current_ma = 20.0
        self._powered = True

    def with_station_id(self, station_id: str) -> "FixtureBuilder":
        self._station_id = station_id
        return self

    def with_product(self, product: str, board: str) -> "FixtureBuilder":
        self._product = product
        self._board = board
        return self

    def with_mtib_revision(self, revision: str) -> "FixtureBuilder":
        self._mtib_revision = revision
        return self

    def with_capability(self, cap: Capability) -> "FixtureBuilder":
        self._capabilities.add(cap)
        return self

    def with_capabilities(self, *caps: Capability) -> "FixtureBuilder":
        self._capabilities.update(caps)
        return self

    def with_battery(self, installed: bool = True) -> "FixtureBuilder":
        self._battery_installed = installed
        return self

    def with_power(
        self,
        dut_voltage: float = 4.5,
        charger_voltage: float = 5.0,
        boot_settle_s: float = 0.01,
    ) -> "FixtureBuilder":
        self._dut_voltage = dut_voltage
        self._charger_voltage = charger_voltage
        self._boot_settle_s = boot_settle_s
        return self

    def with_dut(self, device_id: str, snr: str) -> "FixtureBuilder":
        self._device_id = device_id
        self._snr = snr
        return self

    def with_dut_current(self, current_ma: float) -> "FixtureBuilder":
        self._dut_current_ma = current_ma
        return self

    def with_charger_current(self, current_ma: float) -> "FixtureBuilder":
        self._charger_current_ma = current_ma
        return self

    def with_powered(self, powered: bool) -> "FixtureBuilder":
        self._powered = powered
        return self

    def build(self) -> ProgrammableFixture:
        """Build the ProgrammableFixture instance."""
        # Build hardware configs based on capabilities
        button = None
        if Capability.BUTTON in self._capabilities:
            button = ButtonConfig(
                gpio_pin=self._button_gpio, active_low=self._button_active_low
            )

        ppg_simulator = None
        if (
            Capability.PPG_SERVO in self._capabilities
            or Capability.PPG_LED in self._capabilities
        ):
            ppg_simulator = PpgSimulatorConfig(
                servo_pwm_pin=self._ppg_servo_pwm_pin,
                servo_blocked_duty_us=self._ppg_servo_blocked_us,
                servo_exposed_duty_us=self._ppg_servo_exposed_us,
                hr_led_gpio_pin=self._ppg_hr_led_gpio,
            )

        peltier = None
        if Capability.PELTIER in self._capabilities:
            peltier = PeltierConfig(
                gpio_pin=self._peltier_gpio, temp_adc_channel=self._peltier_temp_adc
            )

        charger_relay = None
        if Capability.CHARGER_RELAY in self._capabilities:
            charger_relay = ChargerRelayConfig(
                gpio_pin=self._charger_relay_gpio,
                active_high=self._charger_relay_active_high,
            )

        led_sensor = None
        if Capability.LED_PHOTODIODE in self._capabilities:
            led_sensor = LedSensorConfig(
                red_adc_channel=self._led_red_adc,
                green_adc_channel=self._led_green_adc,
                blue_adc_channel=self._led_blue_adc,
            )

        motion = None
        if Capability.MOTION_ACTUATOR in self._capabilities:
            motion = MotionConfig(enabled=True)

        profile = FixtureProfile(
            station_id=self._station_id,
            product=self._product,
            board=self._board,
            mtib_revision=self._mtib_revision,
            capabilities=self._capabilities,
            power=PowerConfig(
                battery_installed=self._battery_installed,
                dut_voltage=self._dut_voltage,
                charger_voltage=self._charger_voltage,
                boot_settle_s=self._boot_settle_s,
            ),
            dut=DutConfig(device_id=self._device_id, snr=self._snr),
            button=button,
            ppg_simulator=ppg_simulator,
            peltier=peltier,
            charger_relay=charger_relay,
            led_sensor=led_sensor,
            motion=motion,
        )

        fixture = ProgrammableFixture(profile)
        fixture.configure_current(self._dut_current_ma, self._charger_current_ma)
        fixture.configure_powered(self._powered)

        return fixture


# ═══════════════════════════════════════════════════════════════════════════════
# Pre-built fixture configurations for common test scenarios
# ═══════════════════════════════════════════════════════════════════════════════


class FixturePresets:
    """Pre-built fixture configurations for common scenarios."""

    @staticmethod
    def minimal() -> ProgrammableFixture:
        """Minimal fixture with only power monitoring (no capabilities)."""
        return FixtureBuilder().build()

    @staticmethod
    def button_only() -> ProgrammableFixture:
        """Fixture with only button capability."""
        return FixtureBuilder().with_capability(Capability.BUTTON).build()

    @staticmethod
    def alpha_b0_basic() -> ProgrammableFixture:
        """Alpha B0 fixture with basic capabilities (button, peltier, charger)."""
        return (
            FixtureBuilder()
            .with_product("alpha", "b0")
            .with_capabilities(
                Capability.BUTTON, Capability.PELTIER, Capability.CHARGER_RELAY
            )
            .build()
        )

    @staticmethod
    def alpha_b0_full() -> ProgrammableFixture:
        """Alpha B0 fixture with all capabilities wired."""
        return (
            FixtureBuilder()
            .with_product("alpha", "b0")
            .with_capabilities(
                Capability.BUTTON,
                Capability.PELTIER,
                Capability.CHARGER_RELAY,
                Capability.PPG_SERVO,
                Capability.PPG_LED,
                Capability.LED_PHOTODIODE,
                Capability.NFC_READER,
                Capability.MOTION_ACTUATOR,
            )
            .build()
        )

    @staticmethod
    def device_off() -> ProgrammableFixture:
        """Fixture simulating a powered-off device."""
        return (
            FixtureBuilder()
            .with_capability(Capability.BUTTON)
            .with_powered(False)
            .with_dut_current(0.0)
            .build()
        )

    @staticmethod
    def over_budget() -> ProgrammableFixture:
        """Fixture simulating over-budget current draw."""
        return (
            FixtureBuilder()
            .with_capability(Capability.BUTTON)
            .with_dut_current(50.0)  # Way over typical budget
            .build()
        )
