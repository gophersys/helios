"""Mock hardware stubs for offline validation testing.

Replaces the live MTIB gRPC client, UART demuxer, and power profiler
with no-op implementations so test suites can run with ``MOCK_MODE=1``
on a workstation without any rig attached.

Tests still use the real :class:`corekinect.fixture.Fixture` subclass
declared by their package — the mock client provides the methods the
``Bound*`` accessors call (``PowerEnable``, ``GpioWrite``, ``AdcRead``,
…) so the same code path runs in both modes.
"""

from __future__ import annotations

from collections import namedtuple
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from corekinect.utils import Logger

log = Logger(log_name="mock_hardware")


# ═══════════════════════════════════════════════════════════════════════
# MockMtibClient — duck-typed stand-in for MtibV1Client
# ═══════════════════════════════════════════════════════════════════════


class MockMtibClient:
    """Drop-in for ``MtibV1Client`` that records calls and returns plausible
    values. Wired to the same ``Bound*`` accessors as the real client.
    """

    def __init__(self) -> None:
        self._powered: bool = False
        self._gpios: dict = {}

    def connect(self):
        return None

    def disconnect(self):
        return None

    def HealthCheck(self):
        return True, [], None

    # Power
    def PowerEnable(self, channel: int, voltage_v: float):
        log.info("MockMtib: PowerEnable(ch=%d, v=%.2f)", channel, voltage_v)
        self._powered = True
        return None

    def PowerDisable(self, channel: int):
        log.info("MockMtib: PowerDisable(ch=%d)", channel)
        self._powered = False
        return None

    def PowerRead(self, channel: int):
        R = namedtuple("R", ["current_ma", "voltage_v", "power_mw"])
        current = 25.0 if self._powered else 0.0
        return R(current_ma=current, voltage_v=4.5, power_mw=current * 4.5), None

    # GPIO
    def GpioConfig(self, gpio: int, direction, resistor):
        log.info("MockMtib: GpioConfig(gpio=%d)", gpio)
        return None

    def GpioWrite(self, gpio: int, state: bool):
        log.info("MockMtib: GpioWrite(gpio=%d, state=%s)", gpio, state)
        self._gpios[gpio] = state
        return None

    def GpioRead(self, gpio: int):
        return self._gpios.get(gpio, False), None

    # ADC
    def AdcRead(self, channel: int):
        # Plausible rail voltages — mostly 3.3 V with 0 V on the rest.
        plausible = {0: 4.5, 1: 4.2, 2: 4.5, 3: 0.01, 7: 3.3}
        return plausible.get(channel, 0.0), None


# ═══════════════════════════════════════════════════════════════════════
# MockUartDemuxer
# ═══════════════════════════════════════════════════════════════════════


class MockUartDemuxer:
    """No-op replacement for UartDemuxer in mock mode."""

    def __init__(self) -> None:
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
    active < 15 mA, idle < 5 mA, motion < 25 mA, peak < 200 mA.
    """

    avg_current_ma: float = 3.0
    peak_current_ma: float = 80.0
    min_current_ma: float = 1.0
    avg_voltage_mv: float = 4200.0
    energy_mwh: float = 0.1
    duration_s: float = 10.0
    samples: int = 100

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

    def __post_init__(self) -> None:
        if not self.samples:
            for i in range(10):
                self.samples.append((float(i), 4200.0, 3.0))
        if self.measurement is None:
            self.measurement = MockPowerMeasurement()


class MockPowerProfiler:
    """No-op replacement for PowerProfiler in mock mode."""

    def __init__(self) -> None:
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
