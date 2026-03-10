"""C4: Environmental sensor tests for Sigma5.

Sigma5 has BMP388 barometric pressure sensor for altitude detection.
Asset tracker use case - altitude changes, environmental monitoring.

Tests:
    - Pressure sensor returns valid readings
    - Pressure reading within expected range
    - Temperature sensor returns valid readings
    - Environmental data reported to CoreCloud
"""

import time
import logging

import pytest

log = logging.getLogger(__name__)

# Expected ranges for pressure and temperature
PRESSURE_MIN_HPA = 800    # ~2000m altitude
PRESSURE_MAX_HPA = 1100   # Sea level + margin
TEMP_MIN_C = -10
TEMP_MAX_C = 50


class TestEnvironmental:
    """Environmental sensor verification for Sigma5 (BMP388)."""

    @pytest.mark.corecloud
    def test_pressure_reading_valid(self, ctx, firmware_build):
        """PRDTST-S5-301: BMP388 pressure reading within valid range."""
        env = ctx.cloud.get_environmental_data(timeout_s=60)
        assert env is not None, "No environmental data received"

        pressure = env.get("pressure_hpa") or env.get("pressure")
        assert pressure is not None, "Pressure reading not available"

        log.info("Pressure: %.1f hPa", pressure)

        assert PRESSURE_MIN_HPA < pressure < PRESSURE_MAX_HPA, (
            f"Pressure {pressure:.1f} hPa outside valid range "
            f"[{PRESSURE_MIN_HPA}-{PRESSURE_MAX_HPA}]"
        )

    @pytest.mark.corecloud
    def test_temperature_reading_valid(self, ctx, firmware_build):
        """PRDTST-S5-302: BMP388 temperature reading within valid range."""
        env = ctx.cloud.get_environmental_data(timeout_s=60)
        assert env is not None, "No environmental data received"

        temp = env.get("temperature_c") or env.get("temperature")
        assert temp is not None, "Temperature reading not available"

        log.info("Temperature: %.1f C", temp)

        assert TEMP_MIN_C < temp < TEMP_MAX_C, (
            f"Temperature {temp:.1f}C outside valid range "
            f"[{TEMP_MIN_C}-{TEMP_MAX_C}]"
        )

    @pytest.mark.corecloud
    def test_environmental_data_reported(self, ctx, firmware_build):
        """PRDTST-S5-303: Environmental data is periodically reported to CoreCloud."""
        # Clear and wait for new readings
        start_time = time.time()
        readings = []

        while time.time() - start_time < 120:
            env = ctx.cloud.get_environmental_data(timeout_s=30)
            if env:
                readings.append(env)
                log.info("Environmental reading: %s", env)
            if len(readings) >= 2:
                break
            time.sleep(10)

        assert len(readings) >= 1, "No environmental readings received in 2 minutes"
        log.info("Received %d environmental readings", len(readings))

    def test_pressure_stability(self, ctx, firmware_build):
        """PRDTST-S5-304: Pressure readings are stable (no erratic jumps)."""
        readings = []

        for _ in range(5):
            env = ctx.cloud.get_environmental_data(timeout_s=30)
            if env and "pressure_hpa" in env:
                readings.append(env["pressure_hpa"])
            time.sleep(5)

        if len(readings) < 3:
            pytest.skip("Not enough pressure readings for stability test")

        # Check variance
        avg = sum(readings) / len(readings)
        max_deviation = max(abs(r - avg) for r in readings)

        log.info(
            "Pressure stability: avg=%.1f hPa, max_deviation=%.1f hPa",
            avg, max_deviation,
        )

        # Pressure should not vary by more than 5 hPa in stable conditions
        assert max_deviation < 5, (
            f"Pressure unstable: {max_deviation:.1f} hPa deviation from average"
        )

    @pytest.mark.corecloud
    def test_altitude_calculation(self, ctx, firmware_build):
        """PRDTST-S5-305: Altitude derived from pressure is reasonable."""
        env = ctx.cloud.get_environmental_data(timeout_s=60)
        assert env is not None, "No environmental data received"

        altitude = env.get("altitude_m") or env.get("altitude")

        if altitude is None:
            pytest.skip("Altitude not calculated by firmware")

        log.info("Altitude: %.1f m", altitude)

        # Reasonable altitude range (-500m to 5000m)
        assert -500 < altitude < 5000, (
            f"Altitude {altitude:.1f}m outside reasonable range"
        )
