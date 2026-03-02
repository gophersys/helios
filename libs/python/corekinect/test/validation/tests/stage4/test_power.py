"""C7: Power budget tests.

Verifies power consumption budgets. Release build measurements are
authoritative; debug build measurements are informational (log overhead
affects current). Uses MTIB PowerMeasure and PowerStream RPCs.

Tests:
    - Active mode current within budget
    - Boot current spike within limit
    - Idle current after settling
    - Current changes with on-skin (sensor activation)
    - Power profile during motion
    - Continuous power trace stability
    - No current anomalies during normal operation
"""

import time
import logging

import pytest

log = logging.getLogger(__name__)

# Power budgets (from firmware design spec)
ACTIVE_CURRENT_LIMIT_MA = 15.0    # Active mode average
BOOT_PEAK_LIMIT_MA = 200.0        # Boot sequence peak
IDLE_CURRENT_LIMIT_MA = 5.0       # Idle (not sleeping, but no active sensor)
MOTION_CURRENT_LIMIT_MA = 25.0    # During motion detection (accelerometer active)


class TestPower:
    """Power budget verification."""

    def test_active_mode_current(self, ctx, firmware_build):
        """Active mode average current draw is within budget."""
        result = ctx.power.measure(channel=0, duration_s=60)
        log.info(
            "Active mode (%s): avg=%.1fmA, peak=%.1fmA, min=%.1fmA",
            firmware_build, result.avg_current_ma,
            result.peak_current_ma, result.min_current_ma,
        )
        if firmware_build == "release":
            assert result.avg_current_ma < ACTIVE_CURRENT_LIMIT_MA, (
                f"Active current {result.avg_current_ma:.1f}mA exceeds "
                f"{ACTIVE_CURRENT_LIMIT_MA}mA budget"
            )

    def test_boot_current_spike(self, ctx, firmware_build):
        """Boot sequence peak current does not exceed limit."""
        # Power cycle and measure during boot
        ctx.fixture.power_off()
        time.sleep(2)
        ctx.power.start_continuous(channel=0)
        ctx.fixture.power_on()
        time.sleep(10)  # Capture boot sequence
        trace = ctx.power.stop_continuous()

        assert trace.measurement is not None
        log.info(
            "Boot current (%s): peak=%.1fmA, avg=%.1fmA, %d samples",
            firmware_build, trace.measurement.peak_current_ma,
            trace.measurement.avg_current_ma, trace.measurement.samples,
        )
        assert trace.measurement.peak_current_ma < BOOT_PEAK_LIMIT_MA, (
            f"Boot peak current {trace.measurement.peak_current_ma:.1f}mA "
            f"exceeds {BOOT_PEAK_LIMIT_MA}mA limit"
        )
        # Re-establish boot for subsequent tests
        ctx.cloud.wait_for_boot(timeout_s=120)

    def test_idle_current(self, ctx, firmware_build):
        """Idle current (no stimulus) is within budget after boot settle."""
        time.sleep(30)  # Wait for device to settle from boot
        result = ctx.power.measure(channel=0, duration_s=30)
        log.info(
            "Idle current (%s): avg=%.1fmA, peak=%.1fmA",
            firmware_build, result.avg_current_ma, result.peak_current_ma,
        )
        if firmware_build == "release":
            assert result.avg_current_ma < IDLE_CURRENT_LIMIT_MA, (
                f"Idle current {result.avg_current_ma:.1f}mA exceeds "
                f"{IDLE_CURRENT_LIMIT_MA}mA budget"
            )

    def test_on_skin_power_impact(self, ctx, firmware_build):
        """Current increases when on-skin sensor activates (biometric sensors engage)."""
        # Measure baseline
        baseline = ctx.power.measure(channel=0, duration_s=10)
        # Activate on-skin
        ctx.fixture.simulate_on_skin(on=True)
        time.sleep(10)  # Let sensors stabilize
        active = ctx.power.measure(channel=0, duration_s=10)
        ctx.fixture.simulate_on_skin(on=False)

        log.info(
            "On-skin power (%s): baseline=%.1fmA, active=%.1fmA, delta=%.1fmA",
            firmware_build, baseline.avg_current_ma,
            active.avg_current_ma, active.avg_current_ma - baseline.avg_current_ma,
        )
        # Sensors should draw some additional current when active
        # (informational — just verify it's still within limits)
        if firmware_build == "release":
            assert active.avg_current_ma < ACTIVE_CURRENT_LIMIT_MA, (
                f"On-skin current {active.avg_current_ma:.1f}mA exceeds budget"
            )

    def test_motion_power_impact(self, ctx, firmware_build):
        """Current during motion detection is within budget."""
        ctx.fixture.shake(duration_s=20, speed_mm_s=50)
        result = ctx.power.measure(channel=0, duration_s=15)
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

    def test_continuous_trace_stability(self, ctx, firmware_build):
        """Power trace over 60s shows no anomalous spikes or drops."""
        ctx.power.start_continuous(channel=0)
        time.sleep(60)
        trace = ctx.power.stop_continuous()

        assert trace is not None
        assert trace.measurement is not None
        assert len(trace.samples) > 0, "No power samples collected"

        log.info(
            "60s trace (%s): %d samples, avg=%.1fmA, peak=%.1fmA, min=%.1fmA",
            firmware_build, len(trace.samples),
            trace.measurement.avg_current_ma,
            trace.measurement.peak_current_ma,
            trace.measurement.min_current_ma,
        )

        # Check for anomalous values (negative current or extreme spikes)
        for ts, voltage_mv, current_ma in trace.samples:
            assert current_ma >= -1.0, f"Negative current at t={ts:.1f}s: {current_ma}mA"
            assert current_ma < 500, f"Anomalous spike at t={ts:.1f}s: {current_ma}mA"

    def test_no_current_anomalies(self, ctx, firmware_build):
        """Normal operation shows stable current without drops to zero."""
        result = ctx.power.measure(channel=0, duration_s=30)
        assert result.min_current_ma > 0.5, (
            f"Current dropped to {result.min_current_ma:.1f}mA — "
            "possible brown-out or power glitch"
        )
        log.info(
            "Current stability (%s): min=%.1fmA, avg=%.1fmA",
            firmware_build, result.min_current_ma, result.avg_current_ma,
        )
