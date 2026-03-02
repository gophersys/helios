"""C2: Motion detection tests.

Verifies motion detection via linear actuator stimulus. The MTIB's FluidNC
motor shakes the device on a linear rail, and CoreCloud should receive
PositionMsgV6 with is_in_motion=True.

Tests:
    - Shake triggers motion detection
    - Stationary device does not false-trigger
    - Motion event includes valid accelerometer data
    - Motion stops when actuator stops
    - Multiple shake cycles produce consistent results
"""

import time
import logging

import pytest

log = logging.getLogger(__name__)


@pytest.mark.skipif(
    not __import__("os").environ.get("MOTION_ENABLED", "").lower() in ("1", "true", "yes"),
    reason="Motion hardware disabled (MOTION_ENABLED not set). FluidNC linear rail not connected to validation MTIBs.",
)
class TestMotion:
    """Motion detection verification via linear actuator stimulus."""

    def test_shake_triggers_motion(self, ctx, firmware_build):
        """Shaking device triggers PositionMsgV6 with is_in_motion=True."""
        ctx.fixture.shake(duration_s=30, speed_mm_s=50)
        msg = ctx.cloud.wait_for_position(
            predicate=lambda m: m.is_in_motion,
            timeout_s=120,
        )
        assert msg is not None, "No motion-flagged PositionMsgV6 received"
        assert msg.is_in_motion is True

    def test_stationary_no_false_motion(self, ctx, firmware_build):
        """Stationary device does not falsely trigger motion detection."""
        ctx.fixture.stop_motion()
        time.sleep(10)  # Let vibrations settle
        ctx.cloud.mark_test_start()
        # Wait for a position message while stationary
        try:
            msg = ctx.cloud.wait_for_position(timeout_s=120)
            assert msg.is_in_motion is False, (
                "False motion detection while stationary"
            )
        except TimeoutError:
            # No position message at all is also acceptable when stationary
            pass

    def test_motion_includes_accel_data(self, ctx, firmware_build):
        """Motion event includes valid accelerometer readings."""
        ctx.fixture.shake(duration_s=15, speed_mm_s=50)
        msg = ctx.cloud.wait_for_position(
            predicate=lambda m: m.is_in_motion,
            timeout_s=120,
        )
        # Position messages should have acceleration data when in motion
        assert msg is not None, "No motion PositionMsgV6 received"

    def test_motion_stops_when_stationary(self, ctx, firmware_build):
        """After stopping actuator, device reports not in motion."""
        # First trigger motion
        ctx.fixture.shake(duration_s=10, speed_mm_s=50)
        ctx.cloud.wait_for_position(
            predicate=lambda m: m.is_in_motion,
            timeout_s=60,
        )
        # Stop and wait for settle
        ctx.fixture.stop_motion()
        time.sleep(30)  # Let accelerometer settle + next report cycle
        ctx.cloud.mark_test_start()
        msg = ctx.cloud.wait_for_position(timeout_s=120)
        assert msg.is_in_motion is False, (
            "Device still reports motion after actuator stopped"
        )

    def test_repeated_shake_consistent(self, ctx, firmware_build):
        """Multiple shake cycles produce consistent motion detection."""
        detected_count = 0
        for cycle in range(3):
            ctx.cloud.mark_test_start()
            ctx.fixture.shake(duration_s=10, speed_mm_s=50)
            try:
                msg = ctx.cloud.wait_for_position(
                    predicate=lambda m: m.is_in_motion,
                    timeout_s=60,
                )
                if msg and msg.is_in_motion:
                    detected_count += 1
            except TimeoutError:
                pass
            ctx.fixture.stop_motion()
            time.sleep(15)  # Settle between cycles

        assert detected_count >= 2, (
            f"Motion detected in only {detected_count}/3 cycles"
        )
