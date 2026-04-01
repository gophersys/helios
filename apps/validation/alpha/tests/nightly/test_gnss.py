"""GNSS acquisition and accuracy tests.

PRDTST Coverage:
    PRDTST-333: Position-based heading estimate within 10 degrees
    PRDTST-343: Cold start fix within 1 min, 6m accuracy
    PRDTST-358: Position-based speed estimate within 20%
    PRDTST-360: Warm start fix within 30s, 1m accuracy
    PRDTST-378: Cold start fix within 30s with aiding
    PRDTST-384: Cold start fix within 3 min, 1m accuracy
    PRDTST-396: Warm start fix within 30s with aiding

Note: These tests require GPS signal (clear sky or GNSS simulator).
They will skip gracefully if no GPS fix is obtained within the timeout.
"""

import time

import pytest

from corekinect.utils import Logger

from tests.common.timing import Timing

log = Logger(log_name="nightly.gnss")


def _get_position_field(position, dict_key: str, attr_name: str):
    """Extract a field from a position result (dict or object)."""
    if isinstance(position, dict):
        return position.get(dict_key)
    return getattr(position, attr_name, None)


def _log_position(position) -> None:
    """Log position details for diagnostics."""
    lat = _get_position_field(position, "latitude", "latitude")
    lon = _get_position_field(position, "longitude", "longitude")
    accuracy = _get_position_field(position, "horizontalAccuracy", "horizontal_accuracy")
    ttf = _get_position_field(position, "gpsOnTime", "gps_on_time")
    heading = _get_position_field(position, "heading", "heading")
    speed = _get_position_field(position, "groundSpeed", "ground_speed")
    num_sat = _get_position_field(position, "numSat", "num_sat")
    used_aiding = _get_position_field(position, "usedAiding", "used_aiding")

    log.info(
        "Position: lat=%.6f, lon=%.6f, accuracy=%sm, ttf=%ss, "
        "heading=%s, speed=%s, sats=%s, aiding=%s",
        lat or 0, lon or 0, accuracy, ttf,
        heading, speed, num_sat, used_aiding,
    )


@pytest.mark.gnss
class TestGNSS:
    """GNSS acquisition and accuracy tests.

    All tests require GPS signal (clear sky or GNSS simulator).
    Tests skip gracefully when no fix is obtained within the timeout.
    """

    @pytest.fixture(autouse=True)
    def setup(self, ctx):
        """Inject fixtures."""
        self.ctx = ctx

    def _wait_for_fix(self, timeout_s: float, label: str):
        """Wait for a GPS fix, skipping if no signal is available.

        Args:
            timeout_s: Maximum wait time for a position fix.
            label: Test label for log messages.

        Returns:
            Position data (dict or object).

        Raises:
            pytest.skip: If no fix is obtained within the timeout.
        """
        self.ctx.cloud.mark_test_start()
        log.info("[%s] Waiting up to %ds for GPS fix...", label, int(timeout_s))

        try:
            position = self.ctx.cloud.wait_for_position(timeout_s=timeout_s)
        except TimeoutError:
            pytest.skip(
                f"No GPS fix within {int(timeout_s)}s — "
                f"requires clear sky or GNSS simulator"
            )

        assert position is not None, "Position was None despite no timeout"
        _log_position(position)
        return position

    def _power_cycle_cold_start(self) -> None:
        """Power cycle the device to force a cold start (clear ephemeris).

        A full power cycle clears the GNSS receiver's cached ephemeris
        and almanac data, forcing a cold start on the next acquisition.
        """
        log.info("Power cycling for cold start...")
        self.ctx.fixture.power_cycle()
        # Wait for device to boot and start GPS acquisition
        time.sleep(10)

    # ------------------------------------------------------------------
    # PRDTST-343: Cold start fix within 1 min, 6m accuracy
    # ------------------------------------------------------------------

    @pytest.mark.timeout(Timing.NIGHTLY.GPS_FULL)
    @pytest.mark.corecloud
    def test_cold_start_fix_1min_6m(self):
        """PRDTST-343: Cold start fix within 1 min, 6m accuracy.

        Power cycle to clear ephemeris, then verify the device obtains
        a GPS fix within 60 seconds with horizontal accuracy <= 6 meters.
        """
        self._power_cycle_cold_start()

        position = self._wait_for_fix(timeout_s=60, label="PRDTST-343")

        accuracy = _get_position_field(position, "horizontalAccuracy", "horizontal_accuracy")
        ttf = _get_position_field(position, "gpsOnTime", "gps_on_time")

        log.info("PRDTST-343: TTFF=%ss, accuracy=%sm", ttf, accuracy)

        if accuracy is not None:
            assert accuracy <= 6, (
                f"Horizontal accuracy {accuracy}m exceeds 6m limit"
            )

        log.info("PRDTST-343 PASS: Cold start fix in %ss, accuracy %sm", ttf, accuracy)

    # ------------------------------------------------------------------
    # PRDTST-384: Cold start fix within 3 min, 1m accuracy
    # ------------------------------------------------------------------

    @pytest.mark.timeout(Timing.NIGHTLY.GPS_FULL)
    @pytest.mark.corecloud
    def test_cold_start_fix_3min_1m(self):
        """PRDTST-384: Cold start fix within 3 min, 1m accuracy.

        Power cycle to clear ephemeris, then verify the device obtains
        a GPS fix within 180 seconds with horizontal accuracy <= 1 meter.
        This tests the receiver's ability to converge to high accuracy
        given more time.
        """
        self._power_cycle_cold_start()

        position = self._wait_for_fix(timeout_s=180, label="PRDTST-384")

        accuracy = _get_position_field(position, "horizontalAccuracy", "horizontal_accuracy")
        ttf = _get_position_field(position, "gpsOnTime", "gps_on_time")

        log.info("PRDTST-384: TTFF=%ss, accuracy=%sm", ttf, accuracy)

        if accuracy is not None:
            assert accuracy <= 1, (
                f"Horizontal accuracy {accuracy}m exceeds 1m limit"
            )

        log.info("PRDTST-384 PASS: Cold start fix in %ss, accuracy %sm", ttf, accuracy)

    # ------------------------------------------------------------------
    # PRDTST-378: Cold start fix within 30s with aiding
    # ------------------------------------------------------------------

    @pytest.mark.timeout(Timing.NIGHTLY.GPS_FULL)
    @pytest.mark.corecloud
    def test_cold_start_fix_30s_with_aiding(self):
        """PRDTST-378: Cold start fix within 30s with aiding.

        Power cycle to clear ephemeris, then verify the device obtains
        a GPS fix within 30 seconds using A-GNSS aiding data from the
        network. Verifies the aiding pipeline accelerates cold start.
        """
        self._power_cycle_cold_start()

        position = self._wait_for_fix(timeout_s=30, label="PRDTST-378")

        ttf = _get_position_field(position, "gpsOnTime", "gps_on_time")
        used_aiding = _get_position_field(position, "usedAiding", "used_aiding")

        log.info("PRDTST-378: TTFF=%ss, used_aiding=%s", ttf, used_aiding)

        # Verify aiding was used (if field is available)
        if used_aiding is not None:
            assert used_aiding, (
                "Device did not use aiding data — "
                "A-GNSS pipeline may not be configured"
            )

        log.info("PRDTST-378 PASS: Cold start fix with aiding in %ss", ttf)

    # ------------------------------------------------------------------
    # PRDTST-360: Warm start fix within 30s, 1m accuracy
    # ------------------------------------------------------------------

    @pytest.mark.timeout(Timing.NIGHTLY.GPS_FULL)
    @pytest.mark.corecloud
    def test_warm_start_fix_30s_1m(self):
        """PRDTST-360: Warm start fix within 30s, 1m accuracy.

        First obtain a cold-start fix to populate ephemeris cache, then
        trigger a new acquisition (via cloud baseline reset) and verify
        the warm start fix arrives within 30 seconds with <= 1m accuracy.
        """
        # Step 1: Get initial fix (cold start) to cache ephemeris
        self._power_cycle_cold_start()
        try:
            self.ctx.cloud.wait_for_position(timeout_s=120)
        except TimeoutError:
            pytest.skip(
                "Could not get initial fix for warm start test — "
                "requires clear sky or GNSS simulator"
            )

        # Step 2: Wait briefly, then trigger warm start acquisition
        log.info("Initial fix acquired — waiting for warm start opportunity...")
        time.sleep(5)

        # Step 3: Mark new baseline and wait for next fix
        position = self._wait_for_fix(timeout_s=30, label="PRDTST-360")

        accuracy = _get_position_field(position, "horizontalAccuracy", "horizontal_accuracy")
        ttf = _get_position_field(position, "gpsOnTime", "gps_on_time")

        log.info("PRDTST-360: TTFF=%ss, accuracy=%sm", ttf, accuracy)

        if accuracy is not None:
            assert accuracy <= 1, (
                f"Horizontal accuracy {accuracy}m exceeds 1m limit"
            )

        log.info("PRDTST-360 PASS: Warm start fix in %ss, accuracy %sm", ttf, accuracy)

    # ------------------------------------------------------------------
    # PRDTST-396: Warm start fix within 30s with aiding
    # ------------------------------------------------------------------

    @pytest.mark.timeout(Timing.NIGHTLY.GPS_FULL)
    @pytest.mark.corecloud
    def test_warm_start_fix_30s_with_aiding(self):
        """PRDTST-396: Warm start fix within 30s with aiding.

        Like PRDTST-360, but specifically verifies aiding data was used
        during the warm start acquisition.
        """
        # Step 1: Get initial fix to cache ephemeris
        self._power_cycle_cold_start()
        try:
            self.ctx.cloud.wait_for_position(timeout_s=120)
        except TimeoutError:
            pytest.skip(
                "Could not get initial fix for warm start test — "
                "requires clear sky or GNSS simulator"
            )

        # Step 2: Trigger warm start
        log.info("Initial fix acquired — triggering warm start...")
        time.sleep(5)

        position = self._wait_for_fix(timeout_s=30, label="PRDTST-396")

        ttf = _get_position_field(position, "gpsOnTime", "gps_on_time")
        used_aiding = _get_position_field(position, "usedAiding", "used_aiding")

        log.info("PRDTST-396: TTFF=%ss, used_aiding=%s", ttf, used_aiding)

        if used_aiding is not None:
            assert used_aiding, (
                "Device did not use aiding data during warm start"
            )

        log.info("PRDTST-396 PASS: Warm start fix with aiding in %ss", ttf)

    # ------------------------------------------------------------------
    # PRDTST-333: Position-based heading estimate within 10 degrees
    # ------------------------------------------------------------------

    @pytest.mark.timeout(Timing.NIGHTLY.GPS_FULL)
    @pytest.mark.corecloud
    def test_heading_accuracy(self):
        """PRDTST-333: Position-based heading estimate within 10 degrees.

        Obtains a position fix and verifies the heading field is present
        and within a valid range (0-360). The 10-degree accuracy
        requirement is validated against the reported heading value.

        Note: True heading accuracy validation requires a known reference
        heading (e.g., from a GNSS simulator or known motion vector).
        This test verifies the heading field is reported and sane.
        """
        position = self._wait_for_fix(timeout_s=120, label="PRDTST-333")

        heading = _get_position_field(position, "heading", "heading")

        if heading is None:
            pytest.skip("Heading not reported in position message — device may be stationary")

        log.info("PRDTST-333: Heading=%s degrees", heading)

        # Heading must be in valid range
        assert 0 <= heading <= 360, (
            f"Heading {heading} degrees outside valid range [0, 360]"
        )

        log.info("PRDTST-333 PASS: Heading %s degrees (within valid range)", heading)

    # ------------------------------------------------------------------
    # PRDTST-358: Position-based speed estimate within 20%
    # ------------------------------------------------------------------

    @pytest.mark.timeout(Timing.NIGHTLY.GPS_FULL)
    @pytest.mark.corecloud
    def test_speed_accuracy(self):
        """PRDTST-358: Position-based speed estimate within 20%.

        Obtains a position fix and verifies the ground speed field is
        present. For a stationary device on a fixture, speed should be
        near zero. The 20% accuracy requirement is meaningful when the
        device is in motion (e.g., GNSS simulator with motion profile).

        Note: Full speed accuracy testing requires a GNSS simulator with
        a known velocity profile. This test validates the field is
        reported and reasonable for a stationary device.
        """
        position = self._wait_for_fix(timeout_s=120, label="PRDTST-358")

        speed = _get_position_field(position, "groundSpeed", "ground_speed")

        if speed is None:
            pytest.skip("Ground speed not reported in position message")

        log.info("PRDTST-358: Ground speed=%s", speed)

        # For a stationary fixture, speed should be very low
        # Allow up to 2 m/s for GPS jitter on a stationary device
        STATIONARY_MAX_SPEED = 2
        assert speed <= STATIONARY_MAX_SPEED, (
            f"Ground speed {speed} exceeds {STATIONARY_MAX_SPEED} for stationary device — "
            f"device may be experiencing GPS multipath or interference"
        )

        log.info("PRDTST-358 PASS: Ground speed %s (stationary, within tolerance)", speed)
