"""C7: Power budget tests for Sigma5.

Sigma5 is an asset tracker - power budgets are optimized for long battery life.
No biometric sensors means lower active current than Alpha.

Tests:
    - Active mode current within budget
    - Boot current spike within limit
    - Idle current after settling
    - Motion detection power impact
    - GPS acquisition power impact
    - Continuous power trace stability
"""

import time
import logging

import pytest

from corekinect.test.validation import Capability, requires_capability

log = logging.getLogger(__name__)

# Sigma5 power budgets (asset tracker - optimized for battery life)
ACTIVE_CURRENT_LIMIT_MA = 10.0     # Active mode average (no biometrics = lower)
BOOT_PEAK_LIMIT_MA = 150.0         # Boot sequence peak
IDLE_CURRENT_LIMIT_MA = 3.0        # Idle (sleep mode)
MOTION_CURRENT_LIMIT_MA = 15.0     # During motion detection
GPS_CURRENT_LIMIT_MA = 40.0        # During GPS acquisition


class TestPower:
    """Power budget verification for Sigma5."""

    def test_active_mode_current(self, ctx, firmware_build):
        """PRDTST-S5-101: Active mode average current within budget."""
        ch = 1 if ctx.fixture.profile.battery_installed else 0
        result = ctx.power.measure(channel=ch, duration_s=60)
        log.info(
            "Active mode (%s) ch%d: avg=%.1fmA, peak=%.1fmA, min=%.1fmA",
            firmware_build, ch, result.avg_current_ma,
            result.peak_current_ma, result.min_current_ma,
        )
        if firmware_build == "release":
            assert result.avg_current_ma < ACTIVE_CURRENT_LIMIT_MA, (
                f"Active current {result.avg_current_ma:.1f}mA exceeds "
                f"{ACTIVE_CURRENT_LIMIT_MA}mA budget"
            )

    def test_boot_current_spike(self, ctx, firmware_build):
        """PRDTST-S5-102: Boot peak current within limit."""
        ctx.fixture.power_off()
        time.sleep(2)
        ctx.power.start_continuous(channel=0)
        ctx.fixture.power_on()
        time.sleep(10)
        trace = ctx.power.stop_continuous()

        assert trace.measurement is not None
        log.info(
            "Boot current (%s): peak=%.1fmA, avg=%.1fmA, %d samples",
            firmware_build, trace.measurement.peak_current_ma,
            trace.measurement.avg_current_ma, trace.measurement.samples,
        )
        assert trace.measurement.peak_current_ma < BOOT_PEAK_LIMIT_MA, (
            f"Boot peak {trace.measurement.peak_current_ma:.1f}mA "
            f"exceeds {BOOT_PEAK_LIMIT_MA}mA"
        )

    def test_idle_current(self, ctx, firmware_build):
        """PRDTST-S5-103: Idle current within budget after boot settle."""
        time.sleep(30)
        ch = 1 if ctx.fixture.profile.battery_installed else 0
        result = ctx.power.measure(channel=ch, duration_s=30)
        log.info(
            "Idle current (%s) ch%d: avg=%.1fmA, peak=%.1fmA",
            firmware_build, ch, result.avg_current_ma, result.peak_current_ma,
        )
        if firmware_build == "release":
            assert result.avg_current_ma < IDLE_CURRENT_LIMIT_MA, (
                f"Idle current {result.avg_current_ma:.1f}mA exceeds "
                f"{IDLE_CURRENT_LIMIT_MA}mA budget"
            )

    @requires_capability(Capability.MOTION_ACTUATOR)
    def test_motion_power_impact(self, ctx, firmware_build):
        """PRDTST-S5-104: Current during motion detection within budget."""
        ctx.fixture.shake(duration_s=20, speed_mm_s=50)
        ch = 1 if ctx.fixture.profile.battery_installed else 0
        result = ctx.power.measure(channel=ch, duration_s=15)
        ctx.fixture.stop_motion()
        log.info(
            "Motion current (%s): avg=%.1fmA, peak=%.1fmA",
            firmware_build, result.avg_current_ma, result.peak_current_ma,
        )
        if firmware_build == "release":
            assert result.avg_current_ma < MOTION_CURRENT_LIMIT_MA, (
                f"Motion current {result.avg_current_ma:.1f}mA exceeds "
                f"{MOTION_CURRENT_LIMIT_MA}mA budget"
            )

    @pytest.mark.gps
    @pytest.mark.xfail(reason="GPS simulation not implemented")
    def test_gps_acquisition_power(self, ctx, firmware_build):
        """PRDTST-S5-105: Current during GPS cold start acquisition."""
        # Trigger GPS acquisition (implementation TBD)
        ch = 1 if ctx.fixture.profile.battery_installed else 0
        result = ctx.power.measure(channel=ch, duration_s=60)
        log.info(
            "GPS acquisition (%s): avg=%.1fmA, peak=%.1fmA",
            firmware_build, result.avg_current_ma, result.peak_current_ma,
        )
        if firmware_build == "release":
            assert result.avg_current_ma < GPS_CURRENT_LIMIT_MA, (
                f"GPS current {result.avg_current_ma:.1f}mA exceeds "
                f"{GPS_CURRENT_LIMIT_MA}mA budget"
            )

    def test_continuous_trace_stability(self, ctx, firmware_build):
        """PRDTST-S5-106: Power trace shows no anomalous spikes."""
        ch = 1 if ctx.fixture.profile.battery_installed else 0
        ctx.power.start_continuous(channel=ch)
        time.sleep(60)
        trace = ctx.power.stop_continuous()

        assert trace is not None
        assert trace.measurement is not None
        assert len(trace.samples) > 0, "No power samples collected"

        log.info(
            "60s trace (%s): %d samples, avg=%.1fmA, peak=%.1fmA",
            firmware_build, len(trace.samples),
            trace.measurement.avg_current_ma,
            trace.measurement.peak_current_ma,
        )

        for ts, voltage_mv, current_ma in trace.samples:
            assert current_ma >= -1.0, f"Negative current at t={ts:.1f}s"
            assert current_ma < 300, f"Anomalous spike at t={ts:.1f}s: {current_ma}mA"

    def test_no_current_anomalies(self, ctx, firmware_build):
        """PRDTST-S5-107: Stable current without drops to zero."""
        ch = 1 if ctx.fixture.profile.battery_installed else 0
        result = ctx.power.measure(channel=ch, duration_s=30)
        log.info(
            "Stability (%s) ch%d: min=%.1fmA, avg=%.1fmA, peak=%.1fmA",
            firmware_build, ch, result.min_current_ma,
            result.avg_current_ma, result.peak_current_ma,
        )
        assert result.min_current_ma >= -1.0, (
            f"Negative current {result.min_current_ma:.1f}mA"
        )
        assert result.avg_current_ma > 0, (
            f"Average current is {result.avg_current_ma:.1f}mA - device not running?"
        )
