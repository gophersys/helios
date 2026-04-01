"""Advanced biometric/on-skin tests.

PRDTST Coverage:
    PRDTST-379: Position messages sent when on-skin
"""

import time

import pytest

from corekinect.test.profiles import Capability
from corekinect.test.pytest_integration import requires_capability
from corekinect.utils import Logger

from tests.common.timing import Timing

log = Logger(log_name="nightly.biometric_advanced")

# Timeout for position message after on-skin activation
POSITION_TIMEOUT_S = 180


class TestBiometricAdvanced:
    """Advanced biometric behavior tests."""

    @pytest.fixture(autouse=True)
    def setup(self, ctx):
        """Inject fixtures."""
        self.ctx = ctx

    @pytest.fixture(autouse=True)
    def _cleanup_on_skin(self, ctx):
        """Ensure on-skin simulation is deactivated after each test."""
        yield
        try:
            ctx.fixture.simulate_on_skin(False)
        except Exception as exc:
            log.warning("Failed to deactivate on-skin simulation: %s", exc)

    @requires_capability(Capability.PPG_SERVO, Capability.PPG_LED)
    @pytest.mark.timeout(Timing.NIGHTLY.STIMULUS_FULL)
    @pytest.mark.corecloud
    def test_position_message_on_skin(self):
        """PRDTST-379: Position messages sent when on-skin.

        When the device detects skin contact (on-body), it should begin
        sending position messages. This test activates the PPG skin
        simulator on the fixture, then waits for a position message
        from CoreCloud to confirm the device recognized it is on-skin
        and started GPS acquisition.

        Steps:
          1. Mark test start baseline in CoreCloud.
          2. Activate on-skin simulation via fixture servo/LED.
          3. Wait up to 180s for a position message.
          4. Verify a position message was received (any content).
          5. Deactivate on-skin simulation.
        """
        # Mark baseline so we detect new messages only
        self.ctx.cloud.mark_test_start()
        log.info("Baseline marked — activating on-skin simulation")

        # Activate on-skin detection
        self.ctx.fixture.simulate_on_skin(True)
        log.info("On-skin simulation activated — waiting for position message")

        # Wait for the device to send a position message
        try:
            position = self.ctx.cloud.wait_for_position(timeout_s=POSITION_TIMEOUT_S)
        except TimeoutError:
            pytest.fail(
                f"No position message received within {POSITION_TIMEOUT_S}s "
                f"after on-skin activation"
            )

        # Verify we got a position message (any content proves the device
        # recognized on-skin status and started GPS acquisition)
        if isinstance(position, dict):
            log.info(
                "Position received: lat=%s, lon=%s, reason=%s",
                position.get("latitude", "N/A"),
                position.get("longitude", "N/A"),
                position.get("updateReason", "N/A"),
            )
        else:
            log.info(
                "Position received: lat=%s, lon=%s, reason=%s",
                getattr(position, "latitude", "N/A"),
                getattr(position, "longitude", "N/A"),
                getattr(position, "update_reason_str", "N/A"),
            )

        assert position is not None, "Position message was None"

        # Deactivate on-skin simulation
        self.ctx.fixture.simulate_on_skin(False)
        log.info("On-skin simulation deactivated")

        log.info("PRDTST-379 PASS: Position message received when on-skin")
