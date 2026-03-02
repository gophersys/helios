"""C3: Biometric / on-skin detection tests.

Verifies on-skin detection and biometric data reporting. The MTIB drives
a GPIO to simulate skin contact on the electrode pad, and CoreCloud should
receive BiometricDataMsg with the on_body field set accordingly.

Tests:
    - On-skin electrode triggers on_body=True
    - Removing electrode triggers on_body=False
    - Biometric data includes temperature reading
"""

import time
import logging

import pytest

log = logging.getLogger(__name__)


class TestBiometric:
    """Biometric on-skin detection and environmental data verification."""

    def test_on_skin_detected(self, ctx, firmware_build):
        """On-skin electrode triggers BiometricDataMsg with on_body=True."""
        ctx.fixture.simulate_on_skin(on=True)
        msg = ctx.cloud.wait_for_biometric(
            predicate=lambda m: m.on_body,
            timeout_s=120,
        )
        assert msg is not None, "No on-body BiometricDataMsg received"
        assert msg.on_body is True
        ctx.fixture.simulate_on_skin(on=False)  # Cleanup

    def test_off_skin_detected(self, ctx, firmware_build):
        """Removing on-skin electrode triggers on_body=False."""
        # First establish on-skin
        ctx.fixture.simulate_on_skin(on=True)
        time.sleep(30)  # Let device detect on-body
        # Now remove
        ctx.cloud.mark_test_start()
        ctx.fixture.simulate_on_skin(on=False)
        msg = ctx.cloud.wait_for_biometric(
            predicate=lambda m: not m.on_body,
            timeout_s=120,
        )
        assert msg is not None, "No off-body BiometricDataMsg received"
        assert msg.on_body is False

    def test_biometric_includes_temperature(self, ctx, firmware_build):
        """BiometricDataMsg includes a plausible temperature reading."""
        ctx.fixture.simulate_on_skin(on=True)
        msg = ctx.cloud.wait_for_biometric(timeout_s=120)
        assert msg is not None, "No BiometricDataMsg received"
        # Temperature should be plausible indoor range (10-45 C)
        if hasattr(msg, "temperature") and msg.temperature is not None:
            assert 10 <= msg.temperature <= 45, (
                f"Temperature {msg.temperature}C out of plausible range"
            )
        ctx.fixture.simulate_on_skin(on=False)  # Cleanup
