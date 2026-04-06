"""Mock hardware stubs for offline validation testing.

Provides no-op replacements for FixtureController, UartDemuxer,
and PowerProfiler when running tests with MOCK_CLOUD=1.

All methods log their calls but perform no hardware interaction.
Power/measurement methods return plausible default values.
"""

import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from corekinect.utils import Logger

log = Logger(log_name="mock_hardware")


# ═══════════════════════════════════════════════════════════════════════
# MockFixtureController
# ═══════════════════════════════════════════════════════════════════════


@dataclass
class MockDutConfig:
    """Mock DUT identity matching DutConfig fields."""
    device_id: str = "70B3D584C01E1DDD"
    snr: str = "09J5"
    imei: Optional[str] = "355025931651952"
    iccids: Optional[List[str]] = None

    def __post_init__(self):
        if self.iccids is None:
            object.__setattr__(self, 'iccids', ["89148000009808560116", "89457300000037581199"])


@dataclass
class MockFixtureProfile:
    """Mock fixture profile matching all FixtureProfile fields."""
    product: str = "alpha"
    board: str = "alpha_b0"

    # DUT identity
    dut: Optional[MockDutConfig] = None

    # Button simulation
    button_gpio: int = 2
    button_active_low: bool = True

    def __post_init__(self):
        if self.dut is None:
            object.__setattr__(self, 'dut', MockDutConfig())

    # PPG simulator — servo + green LED array
    ppg_servo_pwm_pin: int = 7   # PwmPin.PWM_1
    ppg_servo_blocked_us: int = 1000
    ppg_servo_exposed_us: int = 2000
    ppg_hr_led_gpio: int = 3

    # Charger relay
    charger_relay_gpio: int = 5
    charger_relay_active_high: bool = True

    # Peltier / temperature
    peltier_gpio: int = 4
    peltier_temp_adc: int = 7

    # LED photodiode ADC channels
    led_red_adc: int = 4
    led_green_adc: int = 5
    led_blue_adc: int = 6

    # Power defaults
    battery_installed: bool = False
    dut_voltage: float = 4.5
    charger_voltage: float = 5.0
    boot_settle_s: float = 3.0


class MockFixtureController:
    """No-op replacement for FixtureController in mock mode.

    All hardware methods log their calls and return plausible values.
    Tests that rely on actual hardware stimulus will pass through but
    produce no real effect — pair with MockCloudClient scenario injection
    to simulate the device responses.
    """

    def __init__(self, profile: Optional[MockFixtureProfile] = None):
        self.profile = profile or MockFixtureProfile()
        self._powered = True
        self._peltier_active = False
        self._button_pressed = False
        self._mtib = _MockMtibStub(fixture=self)

    def has(self, capability: str) -> bool:
        """Mock has all capabilities by default (testing test logic, not hardware)."""
        return True

    def has_capability(self, cap) -> bool:
        """Mock has all capabilities by default (testing test logic, not hardware)."""
        return True

    def power_on(self) -> None:
        log.info("MockFixture: power_on()")
        self._powered = True
        self._button_pressed = False

    def power_off(self) -> None:
        log.info("MockFixture: power_off()")
        self._powered = False
        self._button_pressed = False

    def power_cycle(self, off_time_s: float = 2.0, boot_time_s: float = 5.0) -> None:
        log.info("MockFixture: power_cycle(off=%.1fs, boot=%.1fs)", off_time_s, boot_time_s)
        self._powered = True
        self._button_pressed = False

    def verify_dut_powered(self) -> bool:
        log.info("MockFixture: verify_dut_powered() -> %s", self._powered)
        return self._powered

    def read_dut_current(self) -> float:
        """Return plausible current in mA."""
        current = 10.0 if self._powered else 0.5  # 0.5mA leakage when off
        log.info("MockFixture: read_dut_current() -> %.1f mA", current)
        return current

    def read_charger_current(self) -> float:
        """Return plausible charger current in mA."""
        current = 20.0 if self._powered else 0.0
        log.info("MockFixture: read_charger_current() -> %.1f mA", current)
        return current

    def read_current(self, channel: int = 0) -> float:
        """Return plausible current for a specific channel in mA."""
        current = 10.0 if self._powered else 0.5
        log.info("MockFixture: read_current(ch=%d) -> %.1f mA", channel, current)
        return current

    def read_total_current(self) -> float:
        """Return plausible total current (ch0+ch1) in mA."""
        current = 10.0 if self._powered else 0.5
        log.info("MockFixture: read_total_current() -> %.1f mA", current)
        return current

    @property
    def primary_power_channel(self) -> int:
        """Return the power channel that carries DUT current."""
        return 1 if self.profile.battery_installed else 0

    def set_peltier(self, on: bool) -> None:
        log.info("MockFixture: set_peltier(%s)", on)
        self._peltier_active = on

    def simulate_on_skin(self, on: bool = True) -> None:
        log.info("MockFixture: simulate_on_skin(on=%s)", on)

    def simulate_heartbeat(self, bpm: int = 72) -> None:
        log.info("MockFixture: simulate_heartbeat(bpm=%d)", bpm)

    def stop_heartbeat(self) -> None:
        log.info("MockFixture: stop_heartbeat()")

    def connect_charger(self) -> None:
        log.info("MockFixture: connect_charger()")

    def disconnect_charger(self) -> None:
        log.info("MockFixture: disconnect_charger()")

    def charger_power_on(self) -> None:
        log.info("MockFixture: charger_power_on()")

    def charger_power_off(self) -> None:
        log.info("MockFixture: charger_power_off()")

    def shake(self, duration_s: float = 10, speed_mm_s: float = 50) -> None:
        log.info("MockFixture: shake(duration=%.1fs, speed=%.0f mm/s)", duration_s, speed_mm_s)

    def stop_motion(self) -> None:
        log.info("MockFixture: stop_motion()")

    def press_button(self, duration_s: float = 0.5) -> None:
        log.info("MockFixture: press_button(duration=%.1fs)", duration_s)
        self._button_pressed = True

    def button_press(self, duration_s: float = 0.5) -> None:
        """Alias for press_button (used by regression tests)."""
        self.press_button(duration_s=duration_s)

    def long_press_button(self, duration_s: float = 3.0) -> None:
        log.info("MockFixture: long_press_button(duration=%.1fs)", duration_s)
        # >= 8s press simulates power off (device behavior)
        if duration_s >= 8.0:
            self._powered = False

    def read_led_color(self) -> Dict[str, float]:
        """Return plausible LED color reading.

        Keys match the real FixtureController: "red", "green", "blue".
        Returns a lit LED (green) if button was recently pressed,
        otherwise returns off (all zeros).
        """
        if self._button_pressed:
            color = {"red": 0.0, "green": 0.8, "blue": 0.0}  # Green = status
        else:
            color = {"red": 0.0, "green": 0.0, "blue": 0.0}  # Off
        log.info("MockFixture: read_led_color() -> %s", color)
        return color

    def read_temperature(self) -> float:
        """Return plausible ADC temperature reading.

        Returns a different value when the Peltier is active to simulate
        actual temperature change.
        """
        val = 2.8 if self._peltier_active else 2.5
        log.info("MockFixture: read_temperature() -> %.3fV (peltier=%s)", val, self._peltier_active)
        return val

    def read_power_rails(self) -> Dict[str, float]:
        """Return plausible power rail voltages.

        Keys match the manufacturing test patterns used by Stage 4 tests:
        3v3, batt_sys, vbckp, sys.
        """
        log.info("MockFixture: read_power_rails()")
        return {"3v3": 3.30, "batt_sys": 4.20, "vbckp": 3.30, "sys": 4.50}

    def flash_firmware(self, hex_path: str, target: str = "nrf52840") -> None:
        log.info("MockFixture: flash_firmware(%s, target=%s)", hex_path, target)
        # Flashing implies power cycle — reset all transient state
        self._powered = True
        self._button_pressed = False
        self._peltier_active = False


class _MockMtibStub:
    """Minimal MTIB stub so ctx.fixture._mtib.GpioWrite() doesn't crash."""

    def __init__(self, fixture: Optional["MockFixtureController"] = None):
        self._fixture = fixture

    def GpioWrite(self, gpio: int, state: bool) -> None:
        log.info("MockMtib: GpioWrite(gpio=%d, state=%s)", gpio, state)
        # Track peltier state for temperature simulation
        if self._fixture and gpio == self._fixture.profile.peltier_gpio:
            self._fixture._peltier_active = state

    def GpioConfig(self, gpio: int, **kwargs) -> None:
        log.info("MockMtib: GpioConfig(gpio=%d)", gpio)

    def GpioRead(self, gpio: int) -> bool:
        log.info("MockMtib: GpioRead(gpio=%d)", gpio)
        return False


# ═══════════════════════════════════════════════════════════════════════
# MockUartDemuxer
# ═══════════════════════════════════════════════════════════════════════


class MockUartDemuxer:
    """No-op replacement for UartDemuxer in mock mode."""

    def __init__(self):
        self._log_buffer: List[Tuple[float, str]] = []

    def start(self) -> None:
        log.info("MockUart: start()")

    def stop(self) -> None:
        log.info("MockUart: stop()")

    def clear(self) -> None:
        self._log_buffer.clear()

    def get_lines(self) -> List[Tuple[float, str]]:
        return list(self._log_buffer)

    def dump_to_file(self, path: str) -> None:
        log.info("MockUart: dump_to_file(%s) — no data in mock mode", path)


# ═══════════════════════════════════════════════════════════════════════
# MockPowerProfiler
# ═══════════════════════════════════════════════════════════════════════


@dataclass
class MockPowerMeasurement:
    """Plausible power measurement result.

    Defaults are within all Stage 4 power budget limits:
    active < 15mA, idle < 5mA, motion < 25mA, peak < 200mA.
    """
    avg_current_ma: float = 3.0
    peak_current_ma: float = 80.0
    min_current_ma: float = 1.0
    avg_voltage_mv: float = 4200.0
    energy_mwh: float = 0.1
    duration_s: float = 10.0
    samples: int = 100

    # Aliases used by PowerProfiler
    @property
    def average_ma(self) -> float:
        return self.avg_current_ma

    @property
    def max_ma(self) -> float:
        return self.peak_current_ma

    @property
    def min_ma(self) -> float:
        return self.min_current_ma

    @property
    def average_mv(self) -> float:
        return self.avg_voltage_mv

    @property
    def sample_count(self) -> int:
        return self.samples


@dataclass
class MockPowerTrace:
    """Plausible power trace result."""
    samples: List[Tuple[float, float, float]] = field(default_factory=list)
    measurement: Optional[MockPowerMeasurement] = None

    def __post_init__(self):
        if not self.samples:
            # Generate 10 plausible samples
            for i in range(10):
                self.samples.append((float(i), 4200.0, 3.0))
        if self.measurement is None:
            self.measurement = MockPowerMeasurement()


class MockPowerProfiler:
    """No-op replacement for PowerProfiler in mock mode."""

    def __init__(self):
        self._continuous = False

    def measure(self, channel: int = 0, duration_s: float = 10) -> MockPowerMeasurement:
        log.info("MockPower: measure(ch=%d, duration=%.1fs)", channel, duration_s)
        return MockPowerMeasurement(duration_s=duration_s)

    def start_continuous(self, channel: int = 0) -> None:
        log.info("MockPower: start_continuous(ch=%d)", channel)
        self._continuous = True

    def stop_continuous(self) -> MockPowerTrace:
        log.info("MockPower: stop_continuous()")
        self._continuous = False
        return MockPowerTrace()
