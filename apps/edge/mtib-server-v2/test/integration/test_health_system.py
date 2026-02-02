"""Integration tests for HealthCheck and SystemInfo RPCs."""

import pytest


class TestHealthCheck:
    """Tests for HealthCheck RPC."""

    def test_health_check_returns_ready(self, client):
        """HealthCheck should return ready=True when server is running."""
        ready, errors, err = client.HealthCheck()

        assert err is None, f"HealthCheck RPC failed: {err}"
        assert ready is True, "Server should be ready"

    def test_health_check_returns_errors_list(self, client):
        """HealthCheck should return errors list (may be empty)."""
        ready, errors, err = client.HealthCheck()

        assert err is None, f"HealthCheck RPC failed: {err}"
        assert isinstance(errors, list), "Errors should be a list"

    def test_health_check_timeout(self, client):
        """HealthCheck should respect timeout parameter."""
        # Should complete quickly with short timeout
        ready, errors, err = client.HealthCheck(timeout=5.0)

        assert err is None, f"HealthCheck RPC failed: {err}"
        assert ready is True


class TestSystemInfo:
    """Tests for SystemInfo RPC."""

    def test_system_info_returns_response(self, client):
        """SystemInfo should return system information."""
        response, err = client.SystemInfo()

        assert err is None, f"SystemInfo RPC failed: {err}"
        assert response is not None, "Response should not be None"

    def test_system_info_has_hostname(self, client):
        """SystemInfo should include hostname."""
        response, err = client.SystemInfo()

        assert err is None, f"SystemInfo RPC failed: {err}"
        assert response.hostname != "", "Hostname should not be empty"

    def test_system_info_has_os(self, client):
        """SystemInfo should include OS information."""
        response, err = client.SystemInfo()

        assert err is None, f"SystemInfo RPC failed: {err}"
        assert response.os != "", "OS should not be empty"
        assert "Linux" in response.os or "Windows" in response.os or "Darwin" in response.os

    def test_system_info_has_metrics(self, client):
        """SystemInfo should include CPU/memory/disk metrics."""
        response, err = client.SystemInfo()

        assert err is None, f"SystemInfo RPC failed: {err}"
        # Metrics can be 0 if psutil isn't available, but should be non-negative
        assert response.cpu_usage >= 0, "CPU usage should be non-negative"
        assert response.memory_usage >= 0, "Memory usage should be non-negative"
        assert response.disk_usage >= 0, "Disk usage should be non-negative"

    def test_system_info_has_uptime(self, client):
        """SystemInfo should include uptime."""
        response, err = client.SystemInfo()

        assert err is None, f"SystemInfo RPC failed: {err}"
        assert response.uptime is not None, "Uptime should be present"
        assert response.uptime.seconds >= 0, "Uptime seconds should be non-negative"
