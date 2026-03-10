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

from corekinect.test.validation import Capability, requires_capability

log = logging.getLogger(__name__)


class TestButton:
    """Button press response verification.

    All tests require BUTTON capability. LED-based tests also require
    LED_PHOTODIODE capability. Tests auto-skip if fixture lacks hardware.
    """

    @requires_capability(Capability.BUTTON, Capability.LED_PHOTODIODE)
    def test_short_press_led_response(self, ctx, firmware_build):
        """PRDTST-338: Short button press triggers an LED response."""
        fixture = ctx.fixture
        fixture.press_button(duration_s=0.5)
        time.sleep(1)  # Wait for LED to activate
        led = fixture.read_led_color()
        assert any(v > 0.1 for v in led.values()), (
            f"No LED response to short press: {led}"
        )
        log.info("LED after short press: R=%.2f G=%.2f B=%.2f",
                 led["red"], led["green"], led["blue"])

    @requires_capability(Capability.BUTTON)
    def test_short_press_no_power_off(self, ctx, firmware_build):
        """PRDTST-325: Short press does not power off the device."""
        fixture = ctx.fixture
        fixture.press_button(duration_s=0.5)
        time.sleep(5)
        assert fixture.verify_dut_powered(), (
            "Device powered off after short press"
        )

    @requires_capability(Capability.BUTTON)
    def test_long_press_sos(self, ctx, firmware_build):
        """PRDTST-382: Long press (3s) triggers SOS mode."""
        fixture = ctx.fixture
        fixture.long_press_button(duration_s=3.0)
        time.sleep(2)
        # Verify device is still powered (SOS doesn't power off)
        assert fixture.verify_dut_powered(), (
            "Device not powered after 3s press"
        )
        # TODO: Verify SOS CoreCloud message when message type is confirmed

    @pytest.mark.corecloud
    @requires_capability(Capability.BUTTON)
    def test_very_long_press_power_off(self, ctx, firmware_build):
        """PRDTST-382: Very long press (8s) triggers power off."""
        fixture = ctx.fixture
        fixture.long_press_button(duration_s=8.0)
        time.sleep(5)
        # After very long press, total current should drop to near zero
        if fixture.profile.power.battery_installed:
            current = fixture.read_total_current()
        else:
            current = fixture.read_dut_current()
        log.info("Current after 8s press: %.1fmA", current)
        # Power off means very low current (leakage only)
        assert current < 5.0, (
            f"Device still drawing {current:.1f}mA after very long press"
        )
        # Restore power for subsequent tests
        fixture.power_cycle()
        ctx.cloud.wait_for_boot(timeout_s=120)

    @requires_capability(Capability.BUTTON, Capability.LED_PHOTODIODE)
    def test_led_color_on_status(self, ctx, firmware_build):
        """PRDTST-338: LED shows specific color on status check (short press)."""
        fixture = ctx.fixture
        # Read baseline LED
        baseline = fixture.read_led_color()
        fixture.press_button(duration_s=0.5)
        time.sleep(1)
        active = fixture.read_led_color()
        # At least one channel should change from baseline
        delta = sum(abs(active[c] - baseline[c]) for c in ["red", "green", "blue"])
        assert delta > 0.1, (
            f"LED did not change on button press: baseline={baseline}, active={active}"
        )

    @requires_capability(Capability.BUTTON, Capability.MOTION_ACTUATOR, Capability.LED_PHOTODIODE)
    def test_button_during_motion(self, ctx, firmware_build):
        """PRDTST-326, PRDTST-382: Button press during motion still triggers LED response."""
        fixture = ctx.fixture
        fixture.shake(duration_s=10, speed_mm_s=30)
        time.sleep(2)
        fixture.press_button(duration_s=0.5)
        time.sleep(1)
        led = fixture.read_led_color()
        fixture.stop_motion()
        assert any(v > 0.1 for v in led.values()), (
            f"No LED response to button press during motion: {led}"
        )

    @requires_capability(Capability.BUTTON)
    def test_button_release_detected(self, ctx, firmware_build):
        """PRDTST-325: Device detects button release (no stuck button behavior)."""
        fixture = ctx.fixture
        fixture.press_button(duration_s=1.0)
        time.sleep(5)
        # After release, device should return to normal operation
        assert fixture.verify_dut_powered(), "Device not responsive after button release"

    @requires_capability(Capability.BUTTON)
    def test_no_false_button_events(self, ctx, firmware_build):
        """PRDTST-325: No false button events when idle (electrical noise immunity)."""
        fixture = ctx.fixture
        # Wait for a period without pressing button
        time.sleep(30)
        # Device should still be in normal state, not SOS or powered off
        assert fixture.verify_dut_powered(), "False button event caused power off"

    @requires_capability(Capability.BUTTON)
    def test_double_press(self, ctx, firmware_build):
        """PRDTST-377: Double press (two quick presses) is handled correctly."""
        fixture = ctx.fixture
        fixture.press_button(duration_s=0.3)
        time.sleep(0.3)
        fixture.press_button(duration_s=0.3)
        time.sleep(2)
        # Device should still be powered and responsive
        assert fixture.verify_dut_powered(), "Device not responsive after double press"
