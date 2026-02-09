"""Tests for system and health check operations."""

from corekinect.mtib_client.v2.types.common import HealthStatus, SystemInfo


class TestHealthCheck:
    def test_health_check_returns_status(self, client):
        err, health = client.health_check()
        assert err is None
        assert isinstance(health, HealthStatus)
        assert health.ready is True
        assert health.version == "2.0.0-mock"

    def test_health_check_has_capabilities(self, client):
        err, health = client.health_check()
        assert err is None
        assert "debug" in health.capabilities
        assert health.capabilities["debug"] == "true"

    def test_health_check_no_errors(self, client):
        err, health = client.health_check()
        assert err is None
        assert health.errors == []


class TestSystemInfo:
    def test_system_info_returns_data(self, client):
        err, info = client.system_info()
        assert err is None
        assert isinstance(info, SystemInfo)
        assert info.hostname == "mock-mtib"
        assert info.os == "Linux"

    def test_system_info_has_metrics(self, client):
        err, info = client.system_info()
        assert err is None
        assert info.cpu_usage == 12.5
        assert info.memory_usage == 45.0
        assert info.disk_usage == 30.0

    def test_system_info_has_uptime(self, client):
        err, info = client.system_info()
        assert err is None
        assert info.uptime_s == 3600.0
