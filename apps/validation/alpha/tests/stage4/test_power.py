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

from corekinect.test.validation import Capability, requires_capability

log = logging.getLogger(__name__)

# Power budgets (from firmware design spec)
ACTIVE_CURRENT_LIMIT_MA = 15.0    # Active mode average
BOOT_PEAK_LIMIT_MA = 200.0        # Boot sequence peak
IDLE_CURRENT_LIMIT_MA = 5.0       # Idle (not sleeping, but no active sensor)
MOTION_CURRENT_LIMIT_MA = 25.0    # During motion detection (accelerometer active)


class TestPower:
    """Power budget verification."""

    def test_active_mode_current(self, ctx, firmware_build):
        """PRDTST-341, PRDTST-404: Active mode average current draw is within budget."""
        # With battery installed, charger (ch1) carries most current after
        # BQ25180 takeover. Measure ch1 for battery mode, ch0 otherwise.
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
        """PRDTST-341: Boot sequence peak current does not exceed limit."""
        # Power cycle and measure during boot (ch0 carries initial boot current
        # before BQ25180 charger takeover in battery mode)
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

    def test_idle_current(self, ctx, firmware_build):
        """PRDTST-348: Idle current (no stimulus) is within budget after boot settle."""
        time.sleep(30)  # Wait for device to settle from boot
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

    @requires_capability(Capability.PPG_SERVO, Capability.PPG_LED)
    def test_on_skin_power_impact(self, ctx, firmware_build):
        """PRDTST-327: Current increases when on-skin sensor activates (biometric sensors engage)."""
        ch = 1 if ctx.fixture.profile.battery_installed else 0
        # Measure baseline
        baseline = ctx.power.measure(channel=ch, duration_s=10)
        # Activate on-skin
        ctx.fixture.simulate_on_skin(on=True)
        time.sleep(10)  # Let sensors stabilize
        active = ctx.power.measure(channel=ch, duration_s=10)
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

    @requires_capability(Capability.MOTION_ACTUATOR)
    def test_motion_power_impact(self, ctx, firmware_build):
        """PRDTST-326: Current during motion detection is within budget."""
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

    def test_continuous_trace_stability(self, ctx, firmware_build):
        """Operational: Power trace over 60s shows no anomalous spikes or drops."""
        ch = 1 if ctx.fixture.profile.battery_installed else 0
        ctx.power.start_continuous(channel=ch)
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
        """Operational: Normal operation shows stable current without drops to zero.

        In battery mode, the device sleeps between modem bursts so min
        current CAN be 0mA. We check average > 0 and no negative readings.
        """
        ch = 1 if ctx.fixture.profile.battery_installed else 0
        result = ctx.power.measure(channel=ch, duration_s=30)
        log.info(
            "Current stability (%s) ch%d: min=%.1fmA, avg=%.1fmA, peak=%.1fmA",
            firmware_build, ch, result.min_current_ma,
            result.avg_current_ma, result.peak_current_ma,
        )
        assert result.min_current_ma >= -1.0, (
            f"Negative current {result.min_current_ma:.1f}mA — "
            "possible measurement error or brown-out"
        )
        assert result.avg_current_ma > 0, (
            f"Average current is {result.avg_current_ma:.1f}mA — "
            "device may not be running"
        )
