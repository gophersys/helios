"""Nightly sensor characterization tests.

Tests all sensors across modes:
- Accelerometer (gravity, range, noise)
- PPG (skin detection, heart rate)
- Temperature (IR sensor, ambient)
- Pressure (barometric)

Test IDs: NIGHTLY-ALPHA-SENS-001 through NIGHTLY-ALPHA-SENS-NNN
"""

import pytest

from corekinect.utils import Logger

from tests.common.timing import Timing

log = Logger(log_name="nightly.sensors")


class TestSensors:
    """Sensor characterization tests."""

    @pytest.fixture(autouse=True)
    def setup(self, ctx):
        """Inject fixtures."""
        self.ctx = ctx

    @pytest.mark.timeout(Timing.NIGHTLY.SENSOR_SWEEP)
    def test_accelerometer_gravity(self):
        """NIGHTLY-ALPHA-SENS-001: Accelerometer reads gravity correctly."""
        # TODO: Implement
        # - Device stationary in fixture
        # - Read accel via cloud message or harness
        # - Verify Z axis ~= 1g
        pytest.skip("Not implemented")

    @pytest.mark.timeout(Timing.NIGHTLY.SENSOR_SWEEP)
    def test_ppg_skin_detection(self):
        """NIGHTLY-ALPHA-SENS-002: PPG detects on-skin stimulus."""
        # TODO: Implement
        # - Enable peltier for skin temp simulation
        # - Wait for on-body detection
        # - Verify cloud message shows onBody=true
        pytest.skip("Not implemented")

    @pytest.mark.timeout(Timing.NIGHTLY.SENSOR_SWEEP)
    def test_temperature_range(self):
        """NIGHTLY-ALPHA-SENS-003: Temperature sensor within range."""
        # TODO: Implement
        # - Read temperature from cloud message
        # - Verify within 15-35°C (room temp)
        pytest.skip("Not implemented")

    @pytest.mark.timeout(Timing.NIGHTLY.SENSOR_SWEEP)
    def test_pressure_range(self):
        """NIGHTLY-ALPHA-SENS-004: Pressure sensor within range."""
        # TODO: Implement
        # - Read pressure from cloud message
        # - Verify within 900-1100 hPa
        pytest.skip("Not implemented")
