"""Tests that verify validation test logic using programmable fixtures.

This module tests the tests themselves:
1. When programmable fixture returns good values → test passes
2. When programmable fixture returns bad values → test fails
3. When capability is missing → test skips or raises

This catches bugs in test logic BEFORE burning hardware time.
"""

import pytest
from unittest.mock import MagicMock, patch

from corekinect.capabilities import Capability, Feature
from corekinect.test.profiles import (
    DeviceProfile,
    ValidationConfig,
)
from corekinect.test.programmable_fixture import (
    ProgrammableFixture,
    FixtureBuilder,
    FixturePresets,
    CapabilityNotAvailable,
)


# ═══════════════════════════════════════════════════════════════════════════════
# Test utilities
# ═══════════════════════════════════════════════════════════════════════════════


class MockCloudClient:
    """Minimal mock cloud client for test logic verification."""

    def __init__(self, device_id: int = 0x70B3D584C01E1FCC):
        self.device_id = device_id
        self._boot_msg = MagicMock(boot_reason=0, boot_reason_str="COLD_BOOT")
        self._biometric_msg = None
        self._position_msg = None

    def mark_test_start(self):
        pass

    def wait_for_boot(self, boot_reason=None, timeout_s=120):
        return self._boot_msg

    def wait_for_biometric(self, predicate=None, timeout_s=120):
        if self._biometric_msg is None:
            return None
        if predicate and not predicate(self._biometric_msg):
            return None
        return self._biometric_msg

    def wait_for_position(self, predicate=None, timeout_s=120):
        if self._position_msg is None:
            return None
        if predicate and not predicate(self._position_msg):
            return None
        return self._position_msg

    def stub_biometric(self, on_body: bool, temperature: float = 33.0):
        """Configure biometric message response."""
        self._biometric_msg = MagicMock(on_body=on_body, temperature=temperature)
        return self

    def stub_position(self, is_in_motion: bool):
        """Configure position message response."""
        self._position_msg = MagicMock(is_in_motion=is_in_motion)
        return self


class MockContext:
    """Minimal test context for test logic verification."""

    def __init__(
        self,
        fixture: ProgrammableFixture,
        cloud: MockCloudClient = None,
    ):
        self.fixture = fixture
        self.cloud = cloud or MockCloudClient()
        self.mtib = None
        self.uart = MagicMock()
        self.power = MagicMock()

    def setup_test(self):
        self.cloud.mark_test_start()
        self.fixture.clear_events()
        if hasattr(self.fixture, "_button_pressed"):
            self.fixture._button_pressed = False

    def teardown_test(self, test_name: str, artifacts_dir=None):
        pass


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for button test logic
# ═══════════════════════════════════════════════════════════════════════════════


class TestButtonTestLogic:
    """Verify button test logic produces correct pass/fail results."""

    def _run_short_press_no_power_off_test(self, ctx: MockContext):
        """Simulate test_short_press_no_power_off from test_button.py."""
        ctx.fixture.press_button(duration_s=0.5)
        # Original test does time.sleep(5) here — skip in unit test
        assert ctx.fixture.verify_dut_powered(), "Device powered off after short press"

    def test_short_press_passes_when_device_stays_on(self):
        """Test passes when device remains powered after short press."""
        fixture = FixtureBuilder().with_capability(Capability.BUTTON).build()
        ctx = MockContext(fixture=fixture)

        # Should not raise
        self._run_short_press_no_power_off_test(ctx)

    def test_short_press_fails_when_device_powers_off(self):
        """Test fails when device unexpectedly powers off."""
        fixture = FixtureBuilder().with_capability(Capability.BUTTON).build()
        # Simulate device powering off after button press
        fixture.on_button_press(lambda d: setattr(fixture, "_powered", False))
        ctx = MockContext(fixture=fixture)

        with pytest.raises(AssertionError, match="powered off"):
            self._run_short_press_no_power_off_test(ctx)

    def test_short_press_raises_without_button_capability(self):
        """Test raises CapabilityNotAvailable without BUTTON capability."""
        fixture = FixtureBuilder().build()  # No capabilities
        ctx = MockContext(fixture=fixture)

        with pytest.raises(CapabilityNotAvailable) as exc:
            self._run_short_press_no_power_off_test(ctx)

        assert exc.value.capability == Capability.BUTTON

    def _run_long_press_sos_test(self, ctx: MockContext):
        """Simulate test_long_press_sos from test_button.py."""
        ctx.fixture.long_press_button(duration_s=3.0)
        # Original does time.sleep(2) here
        assert ctx.fixture.verify_dut_powered(), "Device not powered after 3s press"

    def test_long_press_3s_passes_device_stays_on(self):
        """3s press doesn't power off device → test passes."""
        fixture = FixtureBuilder().with_capability(Capability.BUTTON).build()
        ctx = MockContext(fixture=fixture)

        self._run_long_press_sos_test(ctx)

    def _run_very_long_press_power_off_test(self, ctx: MockContext):
        """Simulate test_very_long_press_power_off from test_button.py."""
        ctx.fixture.long_press_button(duration_s=8.0)
        # After very long press, device should be off
        current = ctx.fixture.read_dut_current()
        assert current < 5.0, f"Device still drawing {current:.1f}mA after very long press"

    def test_very_long_press_passes_when_device_powers_off(self):
        """8s press powers off device → test passes."""
        fixture = (
            FixtureBuilder()
            .with_capability(Capability.BUTTON)
            .with_dut_current(15.0)
            .build()
        )
        ctx = MockContext(fixture=fixture)

        # 8s press triggers power off in programmable fixture
        self._run_very_long_press_power_off_test(ctx)

    def test_very_long_press_fails_when_device_stays_on(self):
        """8s press but device stays on → test fails."""
        fixture = (
            FixtureBuilder()
            .with_capability(Capability.BUTTON)
            .with_dut_current(15.0)
            .build()
        )
        # Override the state change to keep device on
        fixture._powered = True

        def keep_powered(_):
            fixture._powered = True
            fixture._dut_current_ma = 15.0

        fixture.on_button_press(keep_powered)

        # Manually simulate the button press without state change
        fixture.require_capability(Capability.BUTTON, "long_press_button")
        fixture._record("long_press_button", duration_s=8.0)
        # Don't set _powered = False — device stays on

        ctx = MockContext(fixture=fixture)

        with pytest.raises(AssertionError, match="still drawing"):
            # Read current should show device is still on
            current = fixture.read_dut_current()
            assert current < 5.0, f"Device still drawing {current:.1f}mA after very long press"


class TestLedTestLogic:
    """Verify LED test logic produces correct pass/fail results."""

    def _run_led_response_test(self, ctx: MockContext):
        """Simulate test_short_press_led_response from test_button.py."""
        ctx.fixture.press_button(duration_s=0.5)
        # Original does time.sleep(1) here
        led = ctx.fixture.read_led_color()
        assert any(v > 0.1 for v in led.values()), f"No LED response to short press: {led}"

    def test_led_response_passes_when_led_lights(self):
        """Test passes when LED lights up after button press."""
        fixture = (
            FixtureBuilder()
            .with_capability(Capability.BUTTON)
            .with_capability(Capability.LED_PHOTODIODE)
            .build()
        )
        fixture.configure_led_after_press(red=0.0, green=0.8, blue=0.0)
        ctx = MockContext(fixture=fixture)

        self._run_led_response_test(ctx)

    def test_led_response_fails_when_led_stays_dark(self):
        """Test fails when no LED response detected."""
        fixture = (
            FixtureBuilder()
            .with_capability(Capability.BUTTON)
            .with_capability(Capability.LED_PHOTODIODE)
            .build()
        )
        # Configure LED to stay dark even after button press
        fixture.configure_led_after_press(red=0.0, green=0.0, blue=0.0)
        ctx = MockContext(fixture=fixture)

        with pytest.raises(AssertionError, match="No LED response"):
            self._run_led_response_test(ctx)

    def test_led_response_raises_without_photodiode(self):
        """Test raises without LED_PHOTODIODE capability."""
        fixture = FixtureBuilder().with_capability(Capability.BUTTON).build()
        ctx = MockContext(fixture=fixture)

        with pytest.raises(CapabilityNotAvailable) as exc:
            self._run_led_response_test(ctx)

        assert exc.value.capability == Capability.LED_PHOTODIODE


class TestPowerTestLogic:
    """Verify power test logic produces correct pass/fail results."""

    def _run_boot_current_test(self, ctx: MockContext, max_current_ma: float = 15.0):
        """Simulate active mode current check."""
        current = ctx.fixture.read_dut_current()
        assert current <= max_current_ma, (
            f"Boot current {current:.1f}mA exceeds budget {max_current_ma}mA"
        )

    def test_boot_current_passes_within_budget(self):
        """Test passes when current is within budget."""
        fixture = FixtureBuilder().with_dut_current(10.0).build()
        ctx = MockContext(fixture=fixture)

        self._run_boot_current_test(ctx, max_current_ma=15.0)

    def test_boot_current_fails_over_budget(self):
        """Test fails when current exceeds budget."""
        fixture = FixtureBuilder().with_dut_current(20.0).build()
        ctx = MockContext(fixture=fixture)

        with pytest.raises(AssertionError, match="exceeds budget"):
            self._run_boot_current_test(ctx, max_current_ma=15.0)

    def test_verify_powered_passes_with_good_current(self):
        """verify_dut_powered passes when current is above threshold."""
        fixture = FixtureBuilder().with_dut_current(10.0).with_powered(True).build()

        assert fixture.verify_dut_powered(min_current_ma=5.0)

    def test_verify_powered_fails_when_off(self):
        """verify_dut_powered fails when device is off."""
        fixture = FixtureBuilder().with_powered(False).build()

        assert not fixture.verify_dut_powered(min_current_ma=5.0)


class TestBiometricTestLogic:
    """Verify biometric/on-skin test logic."""

    def _run_on_skin_detected_test(self, ctx: MockContext):
        """Simulate test_on_skin_detected from test_biometric.py."""
        ctx.fixture.simulate_on_skin(on=True)
        msg = ctx.cloud.wait_for_biometric(
            predicate=lambda m: m.on_body,
            timeout_s=120,
        )
        assert msg is not None, "No on-body BiometricDataMsg received"
        assert msg.on_body is True
        ctx.fixture.simulate_on_skin(on=False)  # Cleanup

    def test_on_skin_passes_with_biometric_message(self):
        """Test passes when cloud reports on_body=True."""
        fixture = (
            FixtureBuilder()
            .with_capability(Capability.PPG_SERVO)
            .with_capability(Capability.PPG_LED)
            .build()
        )
        cloud = MockCloudClient()
        cloud.stub_biometric(on_body=True)
        ctx = MockContext(fixture=fixture, cloud=cloud)

        self._run_on_skin_detected_test(ctx)

    def test_on_skin_fails_without_message(self):
        """Test fails when no biometric message received."""
        fixture = (
            FixtureBuilder()
            .with_capability(Capability.PPG_SERVO)
            .with_capability(Capability.PPG_LED)
            .build()
        )
        cloud = MockCloudClient()  # No biometric message configured
        ctx = MockContext(fixture=fixture, cloud=cloud)

        with pytest.raises(AssertionError, match="No on-body"):
            self._run_on_skin_detected_test(ctx)

    def test_on_skin_raises_without_ppg_capability(self):
        """Test raises without PPG capabilities."""
        fixture = FixtureBuilder().with_capability(Capability.BUTTON).build()
        cloud = MockCloudClient()
        cloud.stub_biometric(on_body=True)
        ctx = MockContext(fixture=fixture, cloud=cloud)

        with pytest.raises(CapabilityNotAvailable):
            self._run_on_skin_detected_test(ctx)


class TestMotionTestLogic:
    """Verify motion test logic."""

    def _run_shake_triggers_motion_test(self, ctx: MockContext):
        """Simulate test_shake_triggers_motion from test_motion.py."""
        ctx.fixture.shake(duration_s=30, speed_mm_s=50)
        msg = ctx.cloud.wait_for_position(
            predicate=lambda m: m.is_in_motion,
            timeout_s=120,
        )
        assert msg is not None, "No motion-flagged PositionMsgV6 received"
        assert msg.is_in_motion is True

    def test_motion_passes_with_position_message(self):
        """Test passes when cloud reports is_in_motion=True."""
        fixture = FixtureBuilder().with_capability(Capability.MOTION_ACTUATOR).build()
        cloud = MockCloudClient()
        cloud.stub_position(is_in_motion=True)
        ctx = MockContext(fixture=fixture, cloud=cloud)

        self._run_shake_triggers_motion_test(ctx)

    def test_motion_fails_without_message(self):
        """Test fails when no motion message received."""
        fixture = FixtureBuilder().with_capability(Capability.MOTION_ACTUATOR).build()
        cloud = MockCloudClient()  # No position message configured
        ctx = MockContext(fixture=fixture, cloud=cloud)

        with pytest.raises(AssertionError, match="No motion-flagged"):
            self._run_shake_triggers_motion_test(ctx)

    def test_motion_raises_without_actuator(self):
        """Test raises without MOTION_ACTUATOR capability."""
        fixture = FixtureBuilder().build()
        cloud = MockCloudClient()
        cloud.stub_position(is_in_motion=True)
        ctx = MockContext(fixture=fixture, cloud=cloud)

        with pytest.raises(CapabilityNotAvailable):
            self._run_shake_triggers_motion_test(ctx)


class TestEnvironmentalTestLogic:
    """Verify environmental test logic."""

    def _run_temperature_change_test(self, ctx: MockContext):
        """Simulate test_temperature_changes_with_peltier from test_environmental.py."""
        # Read baseline
        baseline = ctx.fixture.read_temperature()

        # Heat on
        ctx.fixture.set_peltier(True)
        # Original does time.sleep() here

        heated = ctx.fixture.read_temperature()

        # Verify temperature changed
        delta = abs(heated - baseline)
        assert delta > 0.1, f"Temperature did not change: baseline={baseline}, heated={heated}"

        # Cleanup
        ctx.fixture.set_peltier(False)

    def test_temperature_passes_when_peltier_works(self):
        """Test passes when peltier causes temperature change."""
        fixture = FixtureBuilder().with_capability(Capability.PELTIER).build()
        fixture.configure_temperature(baseline=2.5, heated=3.0)
        ctx = MockContext(fixture=fixture)

        self._run_temperature_change_test(ctx)

    def test_temperature_fails_when_no_change(self):
        """Test fails when peltier has no effect."""
        fixture = FixtureBuilder().with_capability(Capability.PELTIER).build()
        # Configure same temperature for both states
        fixture.configure_temperature(baseline=2.5, heated=2.5)
        ctx = MockContext(fixture=fixture)

        with pytest.raises(AssertionError, match="did not change"):
            self._run_temperature_change_test(ctx)

    def test_temperature_raises_without_peltier(self):
        """Test raises without PELTIER capability."""
        fixture = FixtureBuilder().build()
        ctx = MockContext(fixture=fixture)

        with pytest.raises(CapabilityNotAvailable):
            self._run_temperature_change_test(ctx)


class TestValidationConfigFeatureSkipping:
    """Verify ValidationConfig correctly determines runnable features."""

    @pytest.fixture
    def full_device(self) -> DeviceProfile:
        return DeviceProfile(
            product="alpha",
            revision="b0",
            features={
                Feature.POWER,
                Feature.BUTTON,
                Feature.LED,
                Feature.BIOMETRIC,
                Feature.ENVIRONMENTAL,
                Feature.MOTION,
                Feature.NFC,
            },
        )

    def test_biometric_not_runnable_without_ppg(self, full_device):
        """Biometric feature not runnable when fixture lacks PPG hardware."""
        fixture_profile = (
            FixtureBuilder()
            .with_capability(Capability.BUTTON)
            .with_capability(Capability.PELTIER)
            .build()
            .profile
        )
        config = ValidationConfig(device=full_device, fixture=fixture_profile)

        assert Feature.BIOMETRIC not in config.runnable_features
        reason = config.skip_reason(Feature.BIOMETRIC)
        assert "ppg_servo" in reason or "ppg_led" in reason

    def test_motion_not_runnable_without_actuator(self, full_device):
        """Motion feature not runnable when fixture lacks actuator."""
        fixture_profile = (
            FixtureBuilder()
            .with_capability(Capability.BUTTON)
            .build()
            .profile
        )
        config = ValidationConfig(device=full_device, fixture=fixture_profile)

        assert Feature.MOTION not in config.runnable_features
        reason = config.skip_reason(Feature.MOTION)
        assert "motion_actuator" in reason

    def test_all_features_runnable_with_full_fixture(self, full_device):
        """All device features runnable with fully-equipped fixture."""
        fixture_profile = FixturePresets.alpha_b0_full().profile
        config = ValidationConfig(device=full_device, fixture=fixture_profile)

        for feature in full_device.features:
            assert config.can_test_feature(feature), (
                f"Feature {feature.value} should be runnable but isn't: "
                f"{config.skip_reason(feature)}"
            )
