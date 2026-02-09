"""Tests for power measurement operations."""

from corekinect.mtib_client.v2.types.power import PowerMeasurement, PowerStatus


class TestPowerEnable:
    def test_power_enable_default(self, client):
        err = client.power_enable()
        assert err is None

    def test_power_enable_custom_config(self, client):
        err = client.power_enable(channel=1, voltage_v=1.8, current_limit_ma=100.0)
        assert err is None


class TestPowerDisable:
    def test_power_disable(self, client):
        err = client.power_disable(channel=0)
        assert err is None


class TestPowerStatus:
    def test_power_status_returns_data(self, client):
        err, status = client.power_status()
        assert err is None
        assert isinstance(status, PowerStatus)
        assert status.enabled is True

    def test_power_status_has_measurements(self, client):
        err, status = client.power_status()
        assert err is None
        assert abs(status.voltage_v - 3.3) < 0.01
        assert abs(status.current_ma - 15.2) < 0.01
        assert abs(status.power_mw - 50.16) < 0.01


class TestPowerMeasure:
    def test_power_measure_returns_stats(self, client):
        err, measurement = client.power_measure(duration_s=1.0)
        assert err is None
        assert isinstance(measurement, PowerMeasurement)
        assert measurement.duration_s == 1.0
        assert measurement.average_ua == 15200.0
        assert measurement.min_ua == 12000.0
        assert measurement.max_ua == 18500.0
        assert measurement.energy_uj == 15200.0
        assert measurement.sample_count == 1000
