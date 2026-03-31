"""Timing constants and helpers for Alpha validation tests.

All timeouts are defined here to ensure consistency across stages
and make timing budgets visible and adjustable.

Base utilities (CommonTiming, timeout, wait_with_progress) are
imported from the corekinect.test framework. Alpha-specific timing
constants are defined here.

Usage:
    from tests.common import Timing

    @pytest.mark.timeout(Timing.FUOTA.FLASH_ALL)
    def test_flash_firmware():
        ...
"""

from dataclasses import dataclass

# Re-export framework utilities so existing imports work
from corekinect.test.timing import (  # noqa: F401
    CommonTiming,
    timeout,
    wait_with_progress,
)


@dataclass(frozen=True)
class _FuotaTiming:
    """FUOTA (Stage 5) timing budget - TOTAL < 15 min."""

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


class Timing:
    """All timing constants for Alpha validation tests.

    Usage:
        from tests.common import Timing

        @pytest.mark.timeout(Timing.FUOTA.FLASH_ALL)
        def test_flash():
            ...

        time.sleep(Timing.COMMON.POWER_CYCLE_OFF)
    """

    FUOTA = _FuotaTiming()
    GATE = _FuotaTiming()  # Backward compat alias
    NIGHTLY = _NightlyTiming()
    INTEGRATION = _IntegrationTiming()
    COMMON = CommonTiming()  # From framework
