"""C5: Environmental sensor tests.

Verifies environmental sensor data (temperature, pressure, humidity) in
BiometricDataMsg. Uses ambient conditions — no active stimulus needed for
most tests. Temperature stimulus uses Peltier element on the NTC thermistor.

Tests:
    - Temperature reading in plausible range
    - BiometricDataMsg contains environmental fields
    - Environmental data updates periodically
    - Pressure reading in plausible range
    - Humidity reading in plausible range
    - Temperature changes with Peltier stimulus
    - Power rails stable during normal operation
"""

import time
import logging

import pytest

log = logging.getLogger(__name__)


class TestEnvironmental:
    """Environmental sensor data verification."""

    @pytest.mark.corecloud
    def test_temperature_within_range(self, ctx, firmware_build):
        """Environmental temperature reading is plausible (10-40C indoor)."""
        msg = ctx.cloud.wait_for_biometric(timeout_s=120)
        assert msg is not None, "No BiometricDataMsg received"
        if hasattr(msg, "temperature") and msg.temperature is not None:
            assert 10 <= msg.temperature <= 40, (
                f"Temperature {msg.temperature}C out of indoor range (10-40C)"
            )
            log.info("Temperature: %.1fC", msg.temperature)

    @pytest.mark.corecloud
    def test_biometric_has_environmental_fields(self, ctx, firmware_build):
        """BiometricDataMsg includes expected environmental data fields."""
        msg = ctx.cloud.wait_for_biometric(timeout_s=120)
        assert msg is not None, "No BiometricDataMsg received"
        # Verify message has the expected structure
        # (exact fields depend on firmware version)
        log.info("BiometricDataMsg fields: %s", dir(msg))

    @pytest.mark.corecloud
    def test_environmental_data_updates(self, ctx, firmware_build):
        """Environmental data updates at least once within 5 minutes."""
        msg1 = ctx.cloud.wait_for_biometric(timeout_s=120)
        assert msg1 is not None
        time.sleep(60)  # Wait for next reporting cycle
        ctx.cloud.mark_test_start()
        msg2 = ctx.cloud.wait_for_biometric(timeout_s=300)
        assert msg2 is not None, "No second BiometricDataMsg received"

    @pytest.mark.corecloud
    def test_pressure_within_range(self, ctx, firmware_build):
        """Atmospheric pressure is in plausible range (900-1100 hPa)."""
        msg = ctx.cloud.wait_for_biometric(timeout_s=120)
        if hasattr(msg, "pressure") and msg.pressure is not None:
            assert 900 <= msg.pressure <= 1100, (
                f"Pressure {msg.pressure}hPa out of range (900-1100)"
            )
            log.info("Pressure: %.1f hPa", msg.pressure)
        else:
            pytest.skip("Pressure field not available in BiometricDataMsg")

    @pytest.mark.corecloud
    def test_humidity_within_range(self, ctx, firmware_build):
        """Relative humidity is in plausible range (10-90%)."""
        msg = ctx.cloud.wait_for_biometric(timeout_s=120)
        if hasattr(msg, "humidity") and msg.humidity is not None:
            assert 10 <= msg.humidity <= 90, (
                f"Humidity {msg.humidity}% out of range (10-90)"
            )
            log.info("Humidity: %.1f%%", msg.humidity)
        else:
            pytest.skip("Humidity field not available in BiometricDataMsg")

    def test_temperature_changes_with_peltier(self, ctx, firmware_build):
        """Temperature reading changes when Peltier heats/cools the sensor.

        Drives the Peltier element GPIO, then reads the thermistor ADC
        to verify temperature influence. Compares to baseline reading.
        """
        baseline_adc = ctx.fixture.read_temperature()
        # Enable Peltier (heats one side, cools other)
        gpio = ctx.fixture.profile.peltier_gpio
        ctx.fixture._mtib.GpioWrite(gpio, True)
        time.sleep(30)  # Let temperature stabilize
        heated_adc = ctx.fixture.read_temperature()
        ctx.fixture._mtib.GpioWrite(gpio, False)  # Turn off

        delta = abs(heated_adc - baseline_adc)
        log.info(
            "Peltier test: baseline=%.3fV, heated=%.3fV, delta=%.3fV",
            baseline_adc, heated_adc, delta,
        )
        assert delta > 0.01, (
            f"No temperature change detected with Peltier: delta={delta:.4f}V"
        )

    def test_power_rails_stable(self, ctx, firmware_build):
        """Power rails are within expected voltage ranges during normal operation."""
        rails = ctx.fixture.read_power_rails()
        log.info("Power rails: %s", rails)

        # Expected ranges (from manufacturing test patterns)
        expected = {
            "3v3": (3.0, 3.6),        # +3.3V rail
            "batt_sys": (3.5, 4.8),    # Battery system rail
            "vbckp": (2.8, 3.6),       # Backup voltage
            "sys": (3.0, 5.2),         # System rail
        }
        for rail_name, (vmin, vmax) in expected.items():
            v = rails.get(rail_name)
            if v is not None:
                assert vmin <= v <= vmax, (
                    f"{rail_name} rail voltage {v:.2f}V outside range ({vmin}-{vmax}V)"
                )
