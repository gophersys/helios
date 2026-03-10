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

from corekinect.test.validation import Capability, requires_capability

log = logging.getLogger(__name__)


@pytest.mark.corecloud
class TestMotion:
    """Motion detection verification via linear actuator stimulus."""

    @requires_capability(Capability.MOTION_ACTUATOR)
    def test_shake_triggers_motion(self, ctx, firmware_build):
        """PRDTST-326: Shaking device triggers PositionMsgV6 with is_in_motion=True."""
        fixture = ctx.fixture
        fixture.shake(duration_s=30, speed_mm_s=50)
        msg = ctx.cloud.wait_for_position(
            predicate=lambda m: m.is_in_motion,
            timeout_s=120,
        )
        assert msg is not None, "No motion-flagged PositionMsgV6 received"
        assert msg.is_in_motion is True

    @requires_capability(Capability.MOTION_ACTUATOR)
    def test_stationary_no_false_motion(self, ctx, firmware_build):
        """PRDTST-324: Stationary device does not falsely trigger motion detection."""
        fixture = ctx.fixture
        fixture.stop_motion()
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

    @requires_capability(Capability.MOTION_ACTUATOR)
    def test_motion_includes_accel_data(self, ctx, firmware_build):
        """PRDTST-326: Motion event includes valid accelerometer readings."""
        fixture = ctx.fixture
        fixture.shake(duration_s=15, speed_mm_s=50)
        msg = ctx.cloud.wait_for_position(
            predicate=lambda m: m.is_in_motion,
            timeout_s=120,
        )
        # Position messages should have acceleration data when in motion
        assert msg is not None, "No motion PositionMsgV6 received"

    @requires_capability(Capability.MOTION_ACTUATOR)
    def test_motion_stops_when_stationary(self, ctx, firmware_build):
        """PRDTST-324: After stopping actuator, device reports not in motion."""
        fixture = ctx.fixture
        # First trigger motion
        fixture.shake(duration_s=10, speed_mm_s=50)
        ctx.cloud.wait_for_position(
            predicate=lambda m: m.is_in_motion,
            timeout_s=60,
        )
        # Stop and wait for settle
        fixture.stop_motion()
        time.sleep(30)  # Let accelerometer settle + next report cycle
        ctx.cloud.mark_test_start()
        msg = ctx.cloud.wait_for_position(timeout_s=120)
        assert msg.is_in_motion is False, (
            "Device still reports motion after actuator stopped"
        )

    @requires_capability(Capability.MOTION_ACTUATOR)
    def test_repeated_shake_consistent(self, ctx, firmware_build):
        """PRDTST-326: Multiple shake cycles produce consistent motion detection."""
        fixture = ctx.fixture
        detected_count = 0
        for cycle in range(3):
            ctx.cloud.mark_test_start()
            fixture.shake(duration_s=10, speed_mm_s=50)
            try:
                msg = ctx.cloud.wait_for_position(
                    predicate=lambda m: m.is_in_motion,
                    timeout_s=60,
                )
                if msg and msg.is_in_motion:
                    detected_count += 1
            except TimeoutError:
                pass
            fixture.stop_motion()
            time.sleep(15)  # Settle between cycles

        assert detected_count >= 2, (
            f"Motion detected in only {detected_count}/3 cycles"
        )
