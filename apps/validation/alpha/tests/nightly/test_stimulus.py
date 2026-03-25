"""Nightly physical stimulus tests.

Tests device response to physical inputs:
- Button press (short, long)
- Motion (shake, tilt)
- On-body detection (peltier heating)

Test IDs: NIGHTLY-ALPHA-STIM-001 through NIGHTLY-ALPHA-STIM-NNN
"""

import time

import pytest

from corekinect.utils import Logger

from tests.common.timing import Timing

log = Logger(log_name="nightly.stimulus")


class TestStimulus:
    """Physical stimulus tests."""

    @pytest.fixture(autouse=True)
    def setup(self, ctx):
        """Inject fixtures."""
        self.ctx = ctx

    @pytest.mark.timeout(Timing.NIGHTLY.STIMULUS_FULL)
    def test_button_short_press(self):
        """NIGHTLY-ALPHA-STIM-001: Short button press triggers state change."""
        # TODO: Implement
        # - Press button briefly (0.5s)
        # - Verify status message or LED change
        pytest.skip("Not implemented")

    @pytest.mark.timeout(Timing.NIGHTLY.STIMULUS_FULL)
    def test_button_long_press(self):
        """NIGHTLY-ALPHA-STIM-002: Long button press triggers SOS/shutdown."""
        # TODO: Implement
        # - Press button for 5s
        # - Verify SOS alert or shutdown
        pytest.skip("Not implemented")

    @pytest.mark.timeout(Timing.NIGHTLY.STIMULUS_FULL)
    def test_motion_detection(self):
        """NIGHTLY-ALPHA-STIM-003: Motion stage triggers motion event."""
        if not self.ctx.fixture.has_capability("motion"):
            pytest.skip("Motion stage not available")

        # TODO: Implement
        # - Shake device via motion stage
        # - Verify motion message
        pytest.skip("Not implemented")
