"""Nightly charger behavior tests.

Tests charger detection and charging behavior:
- Plug detection
- Unplug detection
- Charge current verification
- Charge state transitions

Test IDs: NIGHTLY-ALPHA-CHG-001 through NIGHTLY-ALPHA-CHG-NNN
"""

import time

import pytest

from corekinect.utils import Logger

from tests.common.timing import Timing

log = Logger(log_name="nightly.charger")


class TestCharger:
    """Charger behavior tests."""

    @pytest.fixture(autouse=True)
    def setup(self, ctx):
        """Inject fixtures."""
        self.ctx = ctx

    @pytest.mark.timeout(Timing.NIGHTLY.CHARGER_FULL)
    def test_charger_detect(self):
        """NIGHTLY-ALPHA-CHG-001: Device detects charger connection."""
        # TODO: Implement
        # - Start with charger off
        # - Turn charger on via relay
        # - Verify cloud message shows onCharger=true
        pytest.skip("Not implemented")

    @pytest.mark.timeout(Timing.NIGHTLY.CHARGER_FULL)
    def test_charger_disconnect(self):
        """NIGHTLY-ALPHA-CHG-002: Device detects charger disconnection."""
        # TODO: Implement
        # - Start with charger on
        # - Turn charger off via relay
        # - Verify cloud message shows onCharger=false
        pytest.skip("Not implemented")

    @pytest.mark.timeout(Timing.NIGHTLY.CHARGER_FULL)
    def test_charge_current(self):
        """NIGHTLY-ALPHA-CHG-003: Charge current within spec (50-200mA)."""
        # TODO: Implement
        # - Enable charger
        # - Measure ch1 current
        # - Verify within range
        pytest.skip("Not implemented")
