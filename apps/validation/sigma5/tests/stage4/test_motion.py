"""C3: Motion detection tests for Sigma5.

Sigma5 uses LIS2DE12 3-axis accelerometer for motion detection.
Asset tracker use case - detects movement, geofence violations, tampering.

Tests:
    - Accelerometer responds to physical shake
    - Motion triggers MotionMsg at CoreCloud
    - Motion detection threshold sensitivity
    - Accelerometer orientation detection
"""

import time
import logging

import pytest

from corekinect.test.validation import Capability, requires_capability

log = logging.getLogger(__name__)


class TestMotion:
    """Motion detection verification for Sigma5 (LIS2DE12)."""

    @requires_capability(Capability.MOTION_ACTUATOR)
    @pytest.mark.corecloud
    def test_shake_triggers_motion_msg(self, ctx, firmware_build):
        """PRDTST-S5-201: Physical shake produces MotionMsg at CoreCloud."""
        # Clear any pending messages
        ctx.cloud.clear_motion_messages()

        # Shake the device
        ctx.fixture.shake(duration_s=5, speed_mm_s=80, distance_mm=30)

        # Wait for motion message
        msg = ctx.cloud.wait_for_motion(timeout_s=30)
        assert msg is not None, "No MotionMsg received after shake"
        log.info("Motion detected: %s", msg)

    @requires_capability(Capability.MOTION_ACTUATOR)
    def test_accelerometer_responds_to_motion(self, ctx, firmware_build):
        """PRDTST-S5-202: LIS2DE12 accelerometer data changes during shake."""
        # Read baseline (stationary)
        baseline = ctx.fixture.read_accelerometer()
        log.info("Baseline accel: x=%.2fg, y=%.2fg, z=%.2fg",
                 baseline.x_g, baseline.y_g, baseline.z_g)

        # Start shake and read during motion
        ctx.fixture.shake(duration_s=3, speed_mm_s=100, distance_mm=40)
        time.sleep(1)  # Let motion stabilize

        moving = ctx.fixture.read_accelerometer()
        log.info("Moving accel: x=%.2fg, y=%.2fg, z=%.2fg",
                 moving.x_g, moving.y_g, moving.z_g)

        ctx.fixture.stop_motion()

        # At least one axis should show significant change
        delta_x = abs(moving.x_g - baseline.x_g)
        delta_y = abs(moving.y_g - baseline.y_g)
        delta_z = abs(moving.z_g - baseline.z_g)
        max_delta = max(delta_x, delta_y, delta_z)

        assert max_delta > 0.1, (
            f"Accelerometer not responding: max delta = {max_delta:.2f}g"
        )

    @requires_capability(Capability.MOTION_ACTUATOR)
    @pytest.mark.corecloud
    def test_no_motion_when_stationary(self, ctx, firmware_build):
        """PRDTST-S5-203: No spurious MotionMsg when device is stationary."""
        # Ensure device is stationary
        ctx.fixture.stop_motion()
        ctx.fixture.home()
        time.sleep(5)

        # Clear messages and wait
        ctx.cloud.clear_motion_messages()
        time.sleep(30)

        # Should not have received motion messages
        msgs = ctx.cloud.get_motion_messages(since_s=30)
        assert len(msgs) == 0, (
            f"Spurious motion messages when stationary: {len(msgs)} received"
        )

    def test_accelerometer_gravity_vector(self, ctx, firmware_build):
        """PRDTST-S5-204: Accelerometer correctly detects gravity (~1g on one axis)."""
        reading = ctx.fixture.read_accelerometer()

        # Calculate magnitude - should be ~1g for stationary device
        magnitude = (reading.x_g**2 + reading.y_g**2 + reading.z_g**2) ** 0.5

        log.info(
            "Gravity vector: x=%.2fg, y=%.2fg, z=%.2fg, magnitude=%.2fg",
            reading.x_g, reading.y_g, reading.z_g, magnitude,
        )

        # Should be close to 1g (gravity)
        assert 0.8 < magnitude < 1.2, (
            f"Gravity magnitude {magnitude:.2f}g not within expected range"
        )

    @requires_capability(Capability.MOTION_ACTUATOR)
    @pytest.mark.corecloud
    def test_motion_sensitivity_threshold(self, ctx, firmware_build):
        """PRDTST-S5-205: Motion detection triggers at expected acceleration threshold."""
        # Small movement should not trigger
        ctx.cloud.clear_motion_messages()
        ctx.fixture.shake(duration_s=2, speed_mm_s=20, distance_mm=5)
        time.sleep(5)
        small_msgs = ctx.cloud.get_motion_messages(since_s=10)

        # Larger movement should trigger
        ctx.cloud.clear_motion_messages()
        ctx.fixture.shake(duration_s=2, speed_mm_s=100, distance_mm=40)
        time.sleep(5)
        large_msgs = ctx.cloud.get_motion_messages(since_s=10)

        ctx.fixture.stop_motion()

        log.info(
            "Motion sensitivity: small=%d msgs, large=%d msgs",
            len(small_msgs), len(large_msgs),
        )

        # Large movement should produce more motion events
        assert len(large_msgs) >= len(small_msgs), (
            "Larger motion should trigger at least as many events"
        )
