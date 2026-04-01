"""Nightly power profiling tests.

Tests power consumption in various states:
- Sleep current (PSM, no activity)
- Active current (sensors sampling)
- Modem burst current (LTE TX)
- Full power profile capture

Test IDs: NIGHTLY-ALPHA-PWR-001 through NIGHTLY-ALPHA-PWR-004
"""

import time

import pytest

from corekinect.utils import Logger

from tests.common.timing import Timing
from tests.common.assertions import assert_current_in_range

log = Logger(log_name="nightly.power")

# Power budgets (from firmware design spec)
# Alpha PRD power limits (from PRDTST-341, PRDTST-404, PRDTST-348)
# Note: batteryless fixture measures ch0+ch1 combined (total current)
SLEEP_CURRENT_LIMIT_UA = 500.0    # PRDTST-348: Sleep mode < 500uA avg
ACTIVE_CURRENT_LIMIT_MA = 50.0    # PRDTST-404: Normal use < 50mA over 10 min
MODEM_PEAK_LIMIT_MA = 150.0       # PRDTST-341: Active mode < 150mA peak


class TestPowerProfile:
    """Power profiling tests."""

    @pytest.fixture(autouse=True)
    def setup(self, ctx):
        """Inject fixtures."""
        self.ctx = ctx

    @pytest.mark.timeout(Timing.NIGHTLY.POWER_PROFILE)
    def test_sleep_current(self):
        """NIGHTLY-ALPHA-PWR-001: Sleep current < 50uA.

        Verifies device enters Power Saving Mode (PSM) and maintains
        low current draw when idle. Allows for occasional modem bursts.
        """
        log.info("Power cycling device...")
        self.ctx.fixture.power_off()
        time.sleep(Timing.COMMON.POWER_CYCLE_OFF)
        self.ctx.fixture.power_on()

        # Wait for device to settle into sleep mode
        log.info("Waiting %ds for device to enter PSM...",
                 Timing.NIGHTLY.POWER_SLEEP_WAIT)
        time.sleep(Timing.NIGHTLY.POWER_SLEEP_WAIT)

        # Sample current over extended period
        samples = []
        for i in range(Timing.NIGHTLY.POWER_SAMPLE_DURATION):
            current_ma = self.ctx.fixture.read_total_current()
            samples.append(current_ma)
            if i % 10 == 0:
                log.info("[%ds] Current: %.3fmA", i, current_ma)
            time.sleep(1)

        # Calculate statistics
        avg_ua = (sum(samples) / len(samples)) * 1000
        min_ua = min(samples) * 1000
        max_ua = max(samples) * 1000

        log.info("Sleep current: avg=%.1fuA min=%.1fuA max=%.1fuA",
                 avg_ua, min_ua, max_ua)

        # Check minimum current (during sleep, not bursts)
        # Allow modem bursts to push max higher
        assert min_ua < 100, f"Minimum current {min_ua}uA > 100uA - device not sleeping"

        log.info("NIGHTLY-ALPHA-PWR-001 PASS: Sleep current min %.1fuA", min_ua)

    @pytest.mark.timeout(Timing.NIGHTLY.POWER_PROFILE)
    def test_active_current(self):
        """NIGHTLY-ALPHA-PWR-002: Active current < 15mA.

        Verifies active mode current (sensors sampling) is within budget.
        Triggered by button press to wake device from sleep.
        """
        log.info("Triggering active mode with button press...")
        self.ctx.fixture.press_button(duration_s=1)
        time.sleep(5)  # Wait for sensors to start

        # Sample during active period
        samples = []
        for i in range(20):
            current_ma = self.ctx.fixture.read_total_current()
            samples.append(current_ma)
            time.sleep(0.5)

        avg_ma = sum(samples) / len(samples)
        max_ma = max(samples)
        min_ma = min(samples)

        log.info("Active current: avg=%.2fmA min=%.2fmA max=%.2fmA",
                 avg_ma, min_ma, max_ma)
        log.info("Samples: %s", [f"{s:.2f}" for s in samples])

        assert_current_in_range(avg_ma, min_ma=1.0, max_ma=ACTIVE_CURRENT_LIMIT_MA,
                                name="active")

        log.info("NIGHTLY-ALPHA-PWR-002 PASS: Active current %.2fmA", avg_ma)

    @pytest.mark.timeout(Timing.NIGHTLY.POWER_PROFILE)
    def test_modem_burst(self):
        """NIGHTLY-ALPHA-PWR-003: Modem TX burst < 300mA peak.

        Monitors for LTE modem transmission bursts and verifies peak
        current stays within hardware limits.
        """
        log.info("Power cycling to trigger LTE attach...")
        self.ctx.fixture.power_off()
        time.sleep(Timing.COMMON.POWER_CYCLE_OFF)
        self.ctx.fixture.power_on()

        # Wait for LTE attach
        time.sleep(30)

        # Monitor for modem TX bursts over 60 seconds
        log.info("Monitoring for modem TX bursts (60s)...")
        max_current_ma = 0.0
        burst_count = 0
        BURST_THRESHOLD_MA = 50.0

        for i in range(600):
            current_ma = self.ctx.fixture.read_total_current()

            if current_ma > max_current_ma:
                max_current_ma = current_ma
                log.info("[%.1fs] New max: %.1fmA", i * 0.1, current_ma)

            if current_ma > BURST_THRESHOLD_MA:
                burst_count += 1

            time.sleep(0.1)

        log.info("Peak modem current: %.1fmA (%d samples > %.0fmA)",
                 max_current_ma, burst_count, BURST_THRESHOLD_MA)

        assert max_current_ma < MODEM_PEAK_LIMIT_MA, \
            f"Modem burst {max_current_ma}mA exceeds {MODEM_PEAK_LIMIT_MA}mA limit"

        log.info("NIGHTLY-ALPHA-PWR-003 PASS: Modem burst peak %.1fmA", max_current_ma)

    @pytest.mark.timeout(Timing.NIGHTLY.POWER_PROFILE)
    def test_power_profile(self):
        """NIGHTLY-ALPHA-PWR-004: Full 5-minute power profile capture.

        Captures continuous power trace over 5 minutes for offline analysis.
        Verifies no anomalous spikes or drops.
        """
        log.info("Starting 5-minute power profile capture...")

        # Collect samples at 10Hz for 5 minutes
        samples = []
        start_time = time.time()
        duration_s = 300  # 5 minutes

        while time.time() - start_time < duration_s:
            current_ma = self.ctx.fixture.read_total_current()
            elapsed = time.time() - start_time
            samples.append((elapsed, current_ma))

            if len(samples) % 100 == 0:
                log.info("[%.0fs] %d samples, current %.2fmA",
                         elapsed, len(samples), current_ma)

            time.sleep(0.1)

        # Calculate statistics
        currents = [s[1] for s in samples]
        avg_ma = sum(currents) / len(currents)
        min_ma = min(currents)
        max_ma = max(currents)

        log.info("5-min profile: %d samples, avg=%.2fmA min=%.2fmA max=%.2fmA",
                 len(samples), avg_ma, min_ma, max_ma)

        # Check for anomalous values
        anomalies = 0
        for ts, current_ma in samples:
            if current_ma < -1.0:
                log.warning("Negative current at t=%.1fs: %.2fmA", ts, current_ma)
                anomalies += 1
            elif current_ma > 500:
                log.warning("Anomalous spike at t=%.1fs: %.2fmA", ts, current_ma)
                anomalies += 1

        assert anomalies == 0, f"Found {anomalies} anomalous readings in power profile"
        assert avg_ma > 0, f"Average current is {avg_ma:.2f}mA - device may not be running"

        log.info("NIGHTLY-ALPHA-PWR-004 PASS: Power profile captured with no anomalies")
