"""Timing constants and helpers for validation tests.

All timeouts are defined here to ensure consistency across stages
and make timing budgets visible and adjustable.

Usage:
    from tests.common import Timing

    @pytest.mark.timeout(Timing.GATE_FLASH)
    def test_flash_firmware():
        ...
"""

import functools
import time
from dataclasses import dataclass
from typing import Callable, TypeVar

import pytest

F = TypeVar("F", bound=Callable)


@dataclass(frozen=True)
class _GateTiming:
    """Gate (Stage 5) timing budget - TOTAL < 15 min."""

    TOTAL: int = 900  # 15 min hard limit

    # Individual step timeouts
    FLASH_APP: int = 40  # nRF52840 flash
    FLASH_MODEM: int = 55  # Modem flash
    FLASH_COMMS: int = 40  # nRF9151 flash
    FLASH_ALL: int = 150  # All 3 targets (2.5 min)

    BOOT_VERIFY: int = 30  # Power cycle + current check
    BOOT_SETTLE: int = 10  # Time to wait after power-on

    PERSONALIZE: int = 120  # Shell lock + EC keygen + upload (2 min)
    SHELL_LOCK_WINDOW: float = 2.0  # Shell auto-deactivates after this

    CLOUD_CHECKIN: int = 150  # Wait for device to report (2.5 min)
    CLOUD_POLL_INTERVAL: int = 10  # Poll frequency

    FUOTA_UPLOAD: int = 60  # CFW upload to server
    FUOTA_PLAN: int = 30  # Plan creation + assignment
    FUOTA_DELIVERY: int = 480  # Device download + apply (8 min)
    FUOTA_POLL_INTERVAL: int = 10  # Poll frequency

    POST_BOOT: int = 30  # Post-FUOTA boot verification
    CLEANUP: int = 15  # FUOTA cleanup


@dataclass(frozen=True)
class _NightlyTiming:
    """Nightly (Stage 4) timing budget - TOTAL 30-60 min."""

    TOTAL: int = 3600  # 60 min max

    # Power profiling
    POWER_SLEEP_WAIT: int = 60  # Wait for device to enter sleep
    POWER_SAMPLE_DURATION: int = 30  # Sampling window
    POWER_PROFILE: int = 300  # Full power profiling (5 min)

    # Sensor tests
    SENSOR_SETTLE: int = 10  # Sensor warm-up
    SENSOR_SWEEP: int = 600  # All sensors (10 min)

    # GPS tests
    GPS_COLD_START: int = 120  # Cold start TTFF
    GPS_WARM_START: int = 30  # Warm start TTFF
    GPS_FULL: int = 900  # Full GPS tests (15 min)

    # Charger tests
    CHARGER_DETECT: int = 30  # Plug/unplug detection
    CHARGER_FULL: int = 600  # Full charger tests (10 min)

    # Stimulus tests
    STIMULUS_SETTLE: int = 5  # Wait after stimulus
    STIMULUS_FULL: int = 600  # Full stimulus tests (10 min)

    # Cloud tests
    CLOUD_MESSAGE_WAIT: int = 120  # Wait for specific message
    CLOUD_HEARTBEAT: int = 14400  # Full heartbeat cycle (4 hours)


@dataclass(frozen=True)
class _IntegrationTiming:
    """Integration (Stage 3) timing budget - TOTAL 15-30 min."""

    TOTAL: int = 1800  # 30 min max

    HARNESS_CONNECT: int = 30  # Connect to harness shell
    HARNESS_COMMAND: int = 10  # Single harness command
    STATE_TRANSITION: int = 30  # Wait for state machine transition
    IPC_MESSAGE: int = 10  # IPC message round-trip


@dataclass(frozen=True)
class _CommonTiming:
    """Common timing constants used across all stages."""

    POWER_CYCLE_OFF: float = 2.0  # Time to stay powered off
    POWER_CYCLE_ON: float = 10.0  # Time to wait after power-on
    UART_SETTLE: float = 0.5  # UART buffer settle time
    MTIB_CONNECT: int = 10  # MTIB gRPC connection


class Timing:
    """All timing constants for validation tests.

    Usage:
        from tests.common import Timing

        @pytest.mark.timeout(Timing.GATE.FLASH_ALL)
        def test_flash():
            ...

        time.sleep(Timing.COMMON.POWER_CYCLE_OFF)
    """

    GATE = _GateTiming()
    NIGHTLY = _NightlyTiming()
    INTEGRATION = _IntegrationTiming()
    COMMON = _CommonTiming()


def timeout(seconds: int) -> Callable[[F], F]:
    """Decorator to set pytest timeout on a test function.

    Usage:
        @timeout(Timing.GATE.FLASH_ALL)
        def test_flash():
            ...
    """

    def decorator(func: F) -> F:
        return pytest.mark.timeout(seconds)(func)

    return decorator


def wait_with_progress(
    duration_s: float,
    message: str = "Waiting",
    interval_s: float = 10.0,
    logger=None,
) -> None:
    """Wait with progress logging.

    Args:
        duration_s: Total wait time in seconds.
        message: Log message prefix.
        interval_s: Log interval.
        logger: Logger instance (uses print if None).
    """
    log = logger.info if logger else print
    start = time.time()
    elapsed = 0.0

    while elapsed < duration_s:
        remaining = duration_s - elapsed
        log(f"{message}: {elapsed:.0f}s / {duration_s:.0f}s ({remaining:.0f}s remaining)")
        time.sleep(min(interval_s, remaining))
        elapsed = time.time() - start

    log(f"{message}: complete ({elapsed:.1f}s)")
