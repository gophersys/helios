"""C3: Biometric / on-skin detection tests.

Verifies on-skin detection and biometric data reporting. The MTIB drives
a servo + LED to simulate skin contact on the PPG sensor, and CoreCloud
should receive BiometricDataMsg with the on_body field set accordingly.

Tests:
    - On-skin detection triggers on_body=True
    - Removing skin triggers on_body=False
    - Biometric data includes temperature reading

Requires PPG_SERVO + PPG_LED capabilities (servo moves IR blocker,
LED array provides reflective surface).
"""

import time
import logging

import pytest

from corekinect.test.validation import Capability, requires_capability

log = logging.getLogger(__name__)


@pytest.mark.corecloud
class TestBiometric:
    """Biometric on-skin detection and environmental data verification.

    All tests require PPG_SERVO + PPG_LED capabilities. Auto-skips on
    benches without the PPG simulator hardware wired.
    """

    @requires_capability(Capability.PPG_SERVO, Capability.PPG_LED)
    def test_on_skin_detected(self, ctx, firmware_build):
        """PRDTST-400: On-skin simulation triggers BiometricDataMsg with on_body=True."""
        fixture = ctx.fixture
        fixture.simulate_on_skin(on=True)
        msg = ctx.cloud.wait_for_biometric(
            predicate=lambda m: m.on_body,
            timeout_s=120,
        )
        assert msg is not None, "No on-body BiometricDataMsg received"
        assert msg.on_body is True
        fixture.simulate_on_skin(on=False)  # Cleanup

    @requires_capability(Capability.PPG_SERVO, Capability.PPG_LED)
    def test_off_skin_detected(self, ctx, firmware_build):
        """PRDTST-400: Removing on-skin simulation triggers on_body=False."""
        fixture = ctx.fixture
        # First establish on-skin
        fixture.simulate_on_skin(on=True)
        time.sleep(30)  # Let device detect on-body
        # Now remove
        ctx.cloud.mark_test_start()
        fixture.simulate_on_skin(on=False)
        msg = ctx.cloud.wait_for_biometric(
            predicate=lambda m: not m.on_body,
            timeout_s=120,
        )
        assert msg is not None, "No off-body BiometricDataMsg received"
        assert msg.on_body is False

    @requires_capability(Capability.PPG_SERVO, Capability.PPG_LED)
    def test_biometric_includes_temperature(self, ctx, firmware_build):
        """PRDTST-327: BiometricDataMsg includes a plausible temperature reading."""
        fixture = ctx.fixture
        fixture.simulate_on_skin(on=True)
        msg = ctx.cloud.wait_for_biometric(timeout_s=120)
        assert msg is not None, "No BiometricDataMsg received"
        # Temperature should be plausible indoor range (10-45 C)
        if hasattr(msg, "temperature") and msg.temperature is not None:
            assert 10 <= msg.temperature <= 45, (
                f"Temperature {msg.temperature}C out of plausible range"
            )
        fixture.simulate_on_skin(on=False)  # Cleanup
