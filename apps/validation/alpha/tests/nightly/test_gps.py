"""Nightly GPS acquisition tests.

Tests GPS time-to-first-fix under various conditions:
- Cold start (no ephemeris)
- Warm start (cached ephemeris)
- Indoor vs outdoor (signal quality)

Test IDs: NIGHTLY-ALPHA-GPS-001 through NIGHTLY-ALPHA-GPS-NNN
"""

import time

import pytest

from corekinect.utils import Logger

from tests.common.timing import Timing

log = Logger(log_name="nightly.gps")


class TestGPS:
    """GPS acquisition tests."""

    @pytest.fixture(autouse=True)
    def setup(self, ctx):
        """Inject fixtures."""
        self.ctx = ctx

    @pytest.mark.timeout(Timing.NIGHTLY.GPS_FULL)
    def test_cold_start_ttff(self):
        """NIGHTLY-ALPHA-GPS-001: Cold start TTFF < 60 seconds."""
        # TODO: Implement
        # - Power cycle to clear ephemeris
        # - Wait for 3D fix via cloud message
        # - Measure TTFF
        pytest.skip("Not implemented")

    @pytest.mark.timeout(Timing.NIGHTLY.GPS_FULL)
    def test_warm_start_ttff(self):
        """NIGHTLY-ALPHA-GPS-002: Warm start TTFF < 10 seconds."""
        # TODO: Implement
        # - Get initial fix (cold start)
        # - Brief power cycle (preserve ephemeris)
        # - Measure TTFF for second fix
        pytest.skip("Not implemented")
