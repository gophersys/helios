"""C4: Button press response tests.

Verifies button press responses: short press (status LED), long press
(SOS mode), very long press (power off). Verification via CoreCloud
messages and ADC photodiode reads (LED color).

Tests:
    - Short press triggers LED response
    - Short press does not trigger power off
    - Long press (3s) triggers SOS
    - Very long press (8s) triggers power off
    - Double-press behavior
    - LED color changes on short press
    - Button press during motion
    - Button release detected
    - No false button events when idle
"""

import time
import logging

import pytest

log = logging.getLogger(__name__)


class TestButton:
    """Button press response verification."""

    def test_short_press_led_response(self, ctx, firmware_build):
        """Short button press triggers an LED response."""
        ctx.fixture.press_button(duration_s=0.5)
        time.sleep(1)  # Wait for LED to activate
        led = ctx.fixture.read_led_color()
        assert any(v > 0.1 for v in led.values()), (
            f"No LED response to short press: {led}"
        )
        log.info("LED after short press: R=%.2f G=%.2f B=%.2f",
                 led["red"], led["green"], led["blue"])

    def test_short_press_no_power_off(self, ctx, firmware_build):
        """Short press does not power off the device."""
        ctx.fixture.press_button(duration_s=0.5)
        time.sleep(5)
        assert ctx.fixture.verify_dut_powered(), (
            "Device powered off after short press"
        )

    def test_long_press_sos(self, ctx, firmware_build):
        """Long press (3s) triggers SOS mode."""
        ctx.fixture.long_press_button(duration_s=3.0)
        time.sleep(2)
        # Verify device is still powered (SOS doesn't power off)
        assert ctx.fixture.verify_dut_powered(), (
            "Device not powered after 3s press"
        )
        # TODO: Verify SOS CoreCloud message when message type is confirmed

    @pytest.mark.corecloud
    def test_very_long_press_power_off(self, ctx, firmware_build):
        """Very long press (8s) triggers power off."""
        ctx.fixture.long_press_button(duration_s=8.0)
        time.sleep(5)
        # After very long press, current should drop to near zero
        current = ctx.fixture.read_dut_current()
        log.info("Current after 8s press: %.1fmA", current)
        # Power off means very low current (leakage only)
        assert current < 5.0, (
            f"Device still drawing {current:.1f}mA after very long press"
        )
        # Restore power for subsequent tests
        ctx.fixture.power_cycle()
        ctx.cloud.wait_for_boot(timeout_s=120)

    def test_led_color_on_status(self, ctx, firmware_build):
        """LED shows specific color on status check (short press)."""
        # Read baseline LED
        baseline = ctx.fixture.read_led_color()
        ctx.fixture.press_button(duration_s=0.5)
        time.sleep(1)
        active = ctx.fixture.read_led_color()
        # At least one channel should change from baseline
        delta = sum(abs(active[c] - baseline[c]) for c in ["red", "green", "blue"])
        assert delta > 0.1, (
            f"LED did not change on button press: baseline={baseline}, active={active}"
        )

    def test_button_during_motion(self, ctx, firmware_build):
        """Button press during motion still triggers LED response."""
        ctx.fixture.shake(duration_s=10, speed_mm_s=30)
        time.sleep(2)
        ctx.fixture.press_button(duration_s=0.5)
        time.sleep(1)
        led = ctx.fixture.read_led_color()
        ctx.fixture.stop_motion()
        assert any(v > 0.1 for v in led.values()), (
            f"No LED response to button press during motion: {led}"
        )

    def test_button_release_detected(self, ctx, firmware_build):
        """Device detects button release (no stuck button behavior)."""
        ctx.fixture.press_button(duration_s=1.0)
        time.sleep(5)
        # After release, device should return to normal operation
        assert ctx.fixture.verify_dut_powered(), "Device not responsive after button release"

    def test_no_false_button_events(self, ctx, firmware_build):
        """No false button events when idle (electrical noise immunity)."""
        # Wait for a period without pressing button
        time.sleep(30)
        # Device should still be in normal state, not SOS or powered off
        assert ctx.fixture.verify_dut_powered(), "False button event caused power off"

    def test_double_press(self, ctx, firmware_build):
        """Double press (two quick presses) is handled correctly."""
        ctx.fixture.press_button(duration_s=0.3)
        time.sleep(0.3)
        ctx.fixture.press_button(duration_s=0.3)
        time.sleep(2)
        # Device should still be powered and responsive
        assert ctx.fixture.verify_dut_powered(), "Device not responsive after double press"
