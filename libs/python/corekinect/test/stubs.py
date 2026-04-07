"""Configurable stubs for testing validation test logic.

Stubs let you pre-program fixture/power/cloud behavior so you can run
Jared's actual test functions against known scenarios and verify the
test logic correctly detects pass/fail conditions.

Usage:
    fixture = StubFixture()
    fixture.stub_current(avg=20.0)  # Over budget → test should fail
    power = StubPowerProfiler(avg_current_ma=20.0)

    # Run the actual test function and assert it raises AssertionError
    with pytest.raises(AssertionError, match="exceeds.*budget"):
        test_fn(ctx_with_stubs)

This catches bugs in test logic *before* burning time on real hardware.
"""

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple

from corekinect.utils import Logger

log = Logger(log_name="stubs")


# ═══════════════════════════════════════════════════════════════════════
# StubFixtureProfile — matches profiles.FixtureProfile structure
# ═══════════════════════════════════════════════════════════════════════


@dataclass
class StubPowerConfig:
    """Power configuration for stub profile."""
    battery_installed: bool = True
    dut_voltage: float = 4.5
    charger_voltage: float = 5.0
    boot_settle_s: float = 0.01  # Near-instant for stub tests


@dataclass
class StubFixtureProfile:
    """Configurable fixture profile for stub testing.

    Defaults match Alpha B0 battery mode. Override fields to test
    different product configurations.

    Structure matches profiles.FixtureProfile with nested power config.
    """
    product: str = "alpha"
    board: str = "alpha_b0"

    # Nested power config (matches new FixtureProfile structure)
    power: StubPowerConfig = field(default_factory=StubPowerConfig)

    # Button
    button_gpio: int = 2
    button_active_low: bool = True

    # PPG simulator
    ppg_servo_pwm_pin: int = 7
    ppg_servo_blocked_us: int = 1000
    ppg_servo_exposed_us: int = 2000
    ppg_hr_led_gpio: int = 3

    # Charger relay
    charger_relay_gpio: int = 5
    charger_relay_active_high: bool = True

    # Peltier / temperature
    peltier_gpio: int = 4
    peltier_temp_adc: int = 7

    # LED photodiode ADC
    led_red_adc: int = 4
    led_green_adc: int = 5
    led_blue_adc: int = 6

    # Legacy direct access (for backward compat with old tests)
    @property
    def battery_installed(self) -> bool:
        """Battery installed."""
        return self.power.battery_installed


# ═══════════════════════════════════════════════════════════════════════
# StubFixture
# ═══════════════════════════════════════════════════════════════════════


class StubFixture:
    """Configurable fixture stub for testing test logic.

    Unlike MockFixtureController (which returns plausible defaults),
    StubFixture lets you pre-program specific behaviors to verify
    that tests correctly detect both passing and failing conditions.

    Examples:
        # Test should pass with normal current
        stub = StubFixture()
        assert stub.verify_dut_powered()  # True by default

        # Test should fail when device is "off"
        stub = StubFixture(powered=False)
        assert not stub.verify_dut_powered()

        # Pre-program LED readings for button test
        stub = StubFixture()
        stub.stub_led_after_press(red=0.0, green=0.8, blue=0.0)
    """

    def __init__(
        self,
        profile: Optional[StubFixtureProfile] = None,
        powered: bool = True,
        dut_current_ma: float = 10.0,
        charger_current_ma: float = 20.0,
    ):
        """  init  ."""
        self.profile = profile or StubFixtureProfile()
        self._powered = powered
        self._dut_current_ma = dut_current_ma
        self._charger_current_ma = charger_current_ma
        self._peltier_active = False
        self._skin_on = False
        self._button_pressed = False

        # All capabilities available by default (testing test logic, not hardware)
        self._disabled_capabilities: set = set()

        # Configurable responses
        self._led_idle: Dict[str, float] = {"red": 0.0, "green": 0.0, "blue": 0.0}
        self._led_after_press: Dict[str, float] = {"red": 0.0, "green": 0.8, "blue": 0.0}
        self._temp_baseline: float = 2.5
        self._temp_heated: float = 2.8
        self._power_rails: Dict[str, float] = {
            "3v3": 3.30, "batt_sys": 4.20, "vbckp": 3.30, "sys": 4.50,
        }

        # Event log for interaction verification
        self.events: List[str] = []

    # ── Capability API ──

    def has(self, capability: str) -> bool:
        """Stubs have all capabilities by default (testing test logic, not hardware)."""
        cap_str = capability.value if hasattr(capability, "value") else str(capability)
        return cap_str not in self._disabled_capabilities

    def has_capability(self, cap) -> bool:
        """Stubs have all capabilities by default (testing test logic, not hardware)."""
        return self.has(cap)

    def disable_capability(self, cap) -> "StubFixture":
        """Disable a capability for testing skip logic."""
        self._disabled_capabilities.add(cap)
        return self

    def enable_capability(self, cap) -> "StubFixture":
        """Re-enable a previously disabled capability."""
        self._disabled_capabilities.discard(cap)
        return self

    # ── Stubbing API ──

    def stub_current(self, dut_ma: float = 10.0, charger_ma: float = 20.0) -> "StubFixture":
        """Set current readings for power tests."""
        self._dut_current_ma = dut_ma
        self._charger_current_ma = charger_ma
        return self

    def stub_led_after_press(self, red: float = 0.0, green: float = 0.8, blue: float = 0.0) -> "StubFixture":
        """Stub led after press."""
        self._led_after_press = {"red": red, "green": green, "blue": blue}
        return self

    def stub_led_idle(self, red: float = 0.0, green: float = 0.0, blue: float = 0.0) -> "StubFixture":
        """Stub led idle."""
        self._led_idle = {"red": red, "green": green, "blue": blue}
        return self

    def stub_temperature(self, baseline: float = 2.5, heated: float = 2.8) -> "StubFixture":
        """Stub temperature."""
        self._temp_baseline = baseline
        self._temp_heated = heated
        return self

    def stub_power_rails(self, **rails: float) -> "StubFixture":
        """Stub power rails."""
        self._power_rails.update(rails)
        return self

    # ── Primary power channel ──

    @property
    def primary_power_channel(self) -> int:
        """Primary power channel."""
        return 1 if self.profile.battery_installed else 0

    # ── Power methods ──

    def power_on(self, voltage: float = None, with_charger: bool = None) -> None:
        """Power on."""
        self.events.append("power_on")
        self._powered = True
        self._button_pressed = False

    def power_off(self) -> None:
        """Power off."""
        self.events.append("power_off")
        self._powered = False
        self._button_pressed = False

    def power_cycle(self, off_duration_s: float = 2.0) -> None:
        """Power cycle."""
        self.events.append("power_cycle")
        self._powered = True
        self._button_pressed = False

    def verify_dut_powered(self, min_current_ma: float = 5.0, samples: int = 10) -> bool:
        """Verify dut powered."""
        self.events.append("verify_dut_powered")
        return self._powered

    def read_dut_current(self) -> float:
        """Read dut current."""
        return self._dut_current_ma if self._powered else 0.5

    def read_charger_current(self) -> float:
        """Read charger current."""
        return self._charger_current_ma if self._powered else 0.0

    def read_total_current(self) -> float:
        """Read total current."""
        return self.read_dut_current() + self.read_charger_current()

    # ── Button methods ──

    def press_button(self, duration_s: float = 0.5) -> None:
        """Press button."""
        self.events.append(f"press_button({duration_s:.1f}s)")
        self._button_pressed = True

    def long_press_button(self, duration_s: float = 3.0) -> None:
        """Long press button."""
        self.events.append(f"long_press_button({duration_s:.1f}s)")
        if duration_s >= 8.0:
            self._powered = False

    # ── Sensor methods ──

    def simulate_on_skin(self, on: bool = True) -> None:
        """Simulate on skin."""
        self.events.append(f"simulate_on_skin({on})")
        self._skin_on = on

    def simulate_heartbeat(self, bpm: int = 72) -> None:
        """Simulate heartbeat."""
        self.events.append(f"simulate_heartbeat({bpm})")

    def stop_heartbeat(self) -> None:
        """Stop heartbeat."""
        self.events.append("stop_heartbeat")

    def set_peltier(self, on: bool) -> None:
        """Set peltier."""
        self.events.append(f"set_peltier({on})")
        self._peltier_active = on

    def connect_charger(self) -> None:
        """Connect charger."""
        self.events.append("connect_charger")

    def disconnect_charger(self) -> None:
        """Disconnect charger."""
        self.events.append("disconnect_charger")

    # ── ADC reads ──

    def read_led_color(self) -> Dict[str, float]:
        """Read led color."""
        return dict(self._led_after_press if self._button_pressed else self._led_idle)

    def read_temperature(self) -> float:
        """Read temperature."""
        return self._temp_heated if self._peltier_active else self._temp_baseline

    def read_power_rails(self) -> Dict[str, float]:
        """Read power rails."""
        return dict(self._power_rails)

    # ── Motion ──

    def shake(self, duration_s: float = 5.0, speed_mm_s: float = 50.0) -> None:
        """Shake."""
        self.events.append(f"shake({duration_s:.1f}s)")

    def stop_motion(self) -> None:
        """Stop motion."""
        self.events.append("stop_motion")

    # ── Flash ──

    def flash_firmware(self, hex_path: str, target: str = "nrf52840") -> None:
        """Flash firmware."""
        self.events.append(f"flash({hex_path}, {target})")
        self._powered = True
        self._button_pressed = False
        self._peltier_active = False


# ═══════════════════════════════════════════════════════════════════════
# StubPowerProfiler
# ═══════════════════════════════════════════════════════════════════════


@dataclass
class StubPowerMeasurement:
    """Configurable power measurement for testing power budget assertions."""
    avg_current_ma: float = 3.0
    peak_current_ma: float = 80.0
    min_current_ma: float = 1.0
    avg_voltage_mv: float = 4200.0
    energy_mwh: float = 0.1
    duration_s: float = 10.0
    samples: int = 100


@dataclass
class StubPowerTrace:
    """Configurable power trace for testing continuous measurement tests."""
    samples: List[Tuple[float, float, float]] = field(default_factory=list)
    measurement: Optional[StubPowerMeasurement] = None

    def __post_init__(self):
        """  post init  ."""
        if not self.samples:
            self.samples = [(float(i), 4200.0, 3.0) for i in range(10)]
        if self.measurement is None:
            self.measurement = StubPowerMeasurement()


class StubPowerProfiler:
    """Configurable power profiler for testing power budget assertions.

    Pre-program the measurement values to test both pass and fail paths:

        # Normal current → test passes
        power = StubPowerProfiler(avg_current_ma=3.0)

        # Over budget → test should catch it
        power = StubPowerProfiler(avg_current_ma=20.0)
    """

    def __init__(
        self,
        avg_current_ma: float = 3.0,
        peak_current_ma: float = 80.0,
        min_current_ma: float = 1.0,
    ):
        """  init  ."""
        self._measurement = StubPowerMeasurement(
            avg_current_ma=avg_current_ma,
            peak_current_ma=peak_current_ma,
            min_current_ma=min_current_ma,
        )
        self._trace = StubPowerTrace(measurement=self._measurement)

    def stub_measurement(
        self,
        avg_current_ma: float = None,
        peak_current_ma: float = None,
        min_current_ma: float = None,
    ) -> "StubPowerProfiler":
        """Update measurement values."""
        if avg_current_ma is not None:
            self._measurement.avg_current_ma = avg_current_ma
        if peak_current_ma is not None:
            self._measurement.peak_current_ma = peak_current_ma
        if min_current_ma is not None:
            self._measurement.min_current_ma = min_current_ma
        return self

    def stub_trace(self, samples: List[Tuple[float, float, float]]) -> "StubPowerProfiler":
        """Set specific trace samples for anomaly detection tests."""
        self._trace = StubPowerTrace(samples=samples, measurement=self._measurement)
        return self

    def measure(self, channel: int = 0, duration_s: float = 10) -> StubPowerMeasurement:
        """Measure."""
        return StubPowerMeasurement(
            avg_current_ma=self._measurement.avg_current_ma,
            peak_current_ma=self._measurement.peak_current_ma,
            min_current_ma=self._measurement.min_current_ma,
            duration_s=duration_s,
        )

    def start_continuous(self, channel: int = 0) -> None:
        """Start continuous."""
        pass

    def stop_continuous(self) -> StubPowerTrace:
        """Stop continuous."""
        return self._trace


# ═══════════════════════════════════════════════════════════════════════
# StubCloudClient
# ═══════════════════════════════════════════════════════════════════════


@dataclass
class StubMessage:
    """Generic message stub. Set any attributes you need."""

    def __init__(self, **kwargs):
        """  init  ."""
        for k, v in kwargs.items():
            setattr(self, k, v)


class StubCloudClient:
    """Configurable cloud client for testing cloud-dependent test logic.

    Pre-program what messages the "cloud" returns:

        cloud = StubCloudClient()
        cloud.stub_boot(boot_reason=0)
        cloud.stub_biometric(on_body=True, temperature=33.5)
    """

    def __init__(self, device_id: int = 0x70B3D584C01E1FCC):
        """  init  ."""
        self.device_id = device_id
        self._boot_msg: Optional[StubMessage] = StubMessage(
            boot_reason=0, boot_reason_str="COLD_BOOT",
            coprocessor_str="nRF52840",
        )
        self._biometric_msg: Optional[StubMessage] = None
        self._network_msg: Optional[StubMessage] = None
        self._position_msg: Optional[StubMessage] = None
        self._hw_failures: Dict = {"hasFailures": False, "recordId": 0, "failures": []}

    def stub_boot(self, **kwargs) -> "StubCloudClient":
        """Stub boot."""
        self._boot_msg = StubMessage(**kwargs)
        return self

    def stub_biometric(self, **kwargs) -> "StubCloudClient":
        """Stub biometric."""
        self._biometric_msg = StubMessage(**kwargs)
        return self

    def stub_network(self, **kwargs) -> "StubCloudClient":
        """Stub network."""
        self._network_msg = StubMessage(**kwargs)
        return self

    def stub_hw_failures(self, has_failures: bool, failures: List = None) -> "StubCloudClient":
        """Stub hw failures."""
        self._hw_failures = {
            "hasFailures": has_failures,
            "recordId": 1,
            "failures": failures or [],
        }
        return self

    def mark_test_start(self) -> None:
        """Mark test start."""
        pass

    def wait_for_boot(self, boot_reason: int = None, timeout_s: float = 120) -> Optional[StubMessage]:
        """Wait for boot."""
        return self._boot_msg

    def wait_for_biometric(self, predicate: Callable = None, timeout_s: float = 120) -> Optional[StubMessage]:
        """Wait for biometric."""
        if self._biometric_msg is None:
            return None
        if predicate and not predicate(self._biometric_msg):
            return None
        return self._biometric_msg

    def wait_for_network_status(self, timeout_s: float = 120) -> Optional[StubMessage]:
        """Wait for network status."""
        return self._network_msg

    def wait_for_position(self, timeout_s: float = 120) -> Optional[StubMessage]:
        """Wait for position."""
        return self._position_msg

    def check_hw_failures(self, timeout_s: float = 30) -> Dict:
        """Check hw failures."""
        return dict(self._hw_failures)

    def check_comms_hw_failures(self, timeout_s: float = 30) -> Dict:
        """Check comms hw failures."""
        return dict(self._hw_failures)

    def query_messages(self, msg_type: str = None, timeout_s: float = 30) -> List:
        """Query messages."""
        return []


# ═══════════════════════════════════════════════════════════════════════
# StubUartDemuxer
# ═══════════════════════════════════════════════════════════════════════


class StubUartDemuxer:
    """Minimal UART stub."""

    def __init__(self):
        """  init  ."""
        self._lines: List[Tuple[float, str]] = []

    def start(self) -> None:
        """Start."""
        pass

    def stop(self) -> None:
        """Stop."""
        pass

    def clear(self) -> None:
        """Clear."""
        self._lines.clear()

    def get_lines(self) -> List[Tuple[float, str]]:
        """Get lines."""
        return list(self._lines)

    def inject_line(self, timestamp: float, line: str) -> None:
        """Inject a UART line for tests that check debug output."""
        self._lines.append((timestamp, line))

    def dump_to_file(self, path: str) -> None:
        """Dump to file."""
        pass


# ═══════════════════════════════════════════════════════════════════════
# StubTestContext
# ═══════════════════════════════════════════════════════════════════════


class StubTestContext:
    """Pre-configured test context for testing test logic.

    Bundles all stubs into the same shape as TestContext, so Jared's
    tests can run against it unmodified.

    Usage:
        ctx = StubTestContext.passing()
        # Run actual test function — should pass
        TestPower().test_active_mode_current(ctx, "release")

        ctx = StubTestContext.failing_power(avg_current_ma=20.0)
        # Run actual test function — should raise AssertionError
        with pytest.raises(AssertionError):
            TestPower().test_active_mode_current(ctx, "release")
    """

    def __init__(
        self,
        fixture: StubFixture = None,
        power: StubPowerProfiler = None,
        cloud: StubCloudClient = None,
        uart: StubUartDemuxer = None,
    ):
        """  init  ."""
        self.fixture = fixture or StubFixture()
        self.power = power or StubPowerProfiler()
        self.cloud = cloud or StubCloudClient()
        self.uart = uart or StubUartDemuxer()
        self.mtib = None

    def setup_test(self) -> None:
        """Setup test."""
        self.cloud.mark_test_start()
        self.uart.clear()
        if hasattr(self.fixture, '_button_pressed'):
            self.fixture._button_pressed = False

    def teardown_test(self, test_name: str, artifacts_dir: str = None) -> None:
        """Teardown test."""
        pass

    # ── Factory methods for common scenarios ──

    @classmethod
    def passing(cls) -> "StubTestContext":
        """Context where all tests should pass (within all budgets)."""
        return cls(
            fixture=StubFixture(powered=True, dut_current_ma=10.0, charger_current_ma=20.0),
            power=StubPowerProfiler(avg_current_ma=3.0, peak_current_ma=80.0, min_current_ma=1.0),
            cloud=StubCloudClient(),
        )

    @classmethod
    def failing_power(cls, avg_current_ma: float = 20.0, peak_current_ma: float = 250.0) -> "StubTestContext":
        """Context where power tests should fail (over budget)."""
        return cls(
            fixture=StubFixture(powered=True),
            power=StubPowerProfiler(avg_current_ma=avg_current_ma, peak_current_ma=peak_current_ma),
        )

    @classmethod
    def device_off(cls) -> "StubTestContext":
        """Context where device is not powered."""
        return cls(
            fixture=StubFixture(powered=False, dut_current_ma=0.0, charger_current_ma=0.0),
            power=StubPowerProfiler(avg_current_ma=0.0, peak_current_ma=0.0, min_current_ma=0.0),
        )

    @classmethod
    def batteryless(cls) -> "StubTestContext":
        """Context with batteryless fixture profile."""
        profile = StubFixtureProfile(power=StubPowerConfig(battery_installed=False))
        return cls(
            fixture=StubFixture(profile=profile, dut_current_ma=15.0, charger_current_ma=0.0),
            power=StubPowerProfiler(avg_current_ma=8.0),
        )
