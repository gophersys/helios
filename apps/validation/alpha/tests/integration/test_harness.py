"""Integration harness tests.

Tests firmware internals via concord_harness:
- State machine transitions
- IPC message flow
- Sensor orchestration

Test IDs: INTEG-ALPHA-*
"""

import pytest

from corekinect.utils import Logger

from tests.common.timing import Timing

log = Logger(log_name="integration.harness")


class TestStateMachine:
    """State machine transition tests."""

    @pytest.fixture(autouse=True)
    def setup(self, ctx, harness):
        """Inject fixtures."""
        self.ctx = ctx
        self.harness = harness

    @pytest.mark.timeout(Timing.INTEGRATION.STATE_TRANSITION)
    def test_idle_to_monitoring(self):
        """INTEG-ALPHA-SM-001: IDLE -> MONITORING on touch detection."""
        # TODO: Implement
        # - Query current state via harness
        # - Trigger touch stimulus
        # - Verify transition to MONITORING
        pytest.skip("Not implemented")

    @pytest.mark.timeout(Timing.INTEGRATION.STATE_TRANSITION)
    def test_monitoring_to_idle(self):
        """INTEG-ALPHA-SM-002: MONITORING -> IDLE on off-body timeout."""
        # TODO: Implement
        # - Set state to MONITORING via harness
        # - Remove skin stimulus
        # - Wait for off-body timeout
        # - Verify transition to IDLE
        pytest.skip("Not implemented")


class TestIPC:
    """Inter-processor communication tests."""

    @pytest.fixture(autouse=True)
    def setup(self, ctx, harness):
        """Inject fixtures."""
        self.ctx = ctx
        self.harness = harness

    @pytest.mark.timeout(Timing.INTEGRATION.IPC_MESSAGE)
    def test_app_to_comms(self):
        """INTEG-ALPHA-IPC-001: App->Comms message delivery."""
        # TODO: Implement
        # - Inject message on APP side via harness
        # - Verify receipt on COMMS side via UART
        pytest.skip("Not implemented")

    @pytest.mark.timeout(Timing.INTEGRATION.IPC_MESSAGE)
    def test_comms_to_app(self):
        """INTEG-ALPHA-IPC-002: Comms->App message delivery."""
        # TODO: Implement
        # - Inject message on COMMS side
        # - Verify receipt on APP side via harness
        pytest.skip("Not implemented")
