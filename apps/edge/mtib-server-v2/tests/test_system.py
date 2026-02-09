"""Tests for SystemHandler (HealthCheck, SystemInfo)."""

import time

import pytest

from src.providers.handlers.system import SystemHandler
from src.shared.types import HealthCheckRequest, SystemInfoRequest


class TestHealthCheck:
    def test_returns_ready(self, logger, hardware, context):
        handler = SystemHandler(logger, hardware, time.time())
        response = handler.health_check(HealthCheckRequest(), context)
        assert response.ready is True

    def test_returns_version(self, logger, hardware, context):
        handler = SystemHandler(logger, hardware, time.time())
        response = handler.health_check(HealthCheckRequest(), context)
        assert response.version == "2.0.0"

    def test_capabilities_include_revision(self, logger, hardware, context):
        handler = SystemHandler(logger, hardware, time.time())
        response = handler.health_check(HealthCheckRequest(), context)
        assert "hardware_revision" in response.capabilities

    def test_capabilities_reflect_rev_1_1(self, logger, hardware, context):
        handler = SystemHandler(logger, hardware, time.time())
        response = handler.health_check(HealthCheckRequest(), context)
        assert response.capabilities["gpio_expander"] == "false"
        assert response.capabilities["jlink_mux"] == "false"

    def test_errors_list_empty_by_default(self, logger, hardware, context):
        handler = SystemHandler(logger, hardware, time.time())
        response = handler.health_check(HealthCheckRequest(), context)
        assert len(response.errors) == 0

    def test_errors_list_populated(self, logger, hardware, context):
        handler = SystemHandler(logger, hardware, time.time())
        handler.errors.append("test error")
        response = handler.health_check(HealthCheckRequest(), context)
        assert "test error" in response.errors


class TestSystemInfo:
    def test_returns_success(self, logger, hardware, context):
        handler = SystemHandler(logger, hardware, time.time())
        response = handler.system_info(SystemInfoRequest(), context)
        assert response.success is True

    def test_returns_hostname(self, logger, hardware, context):
        handler = SystemHandler(logger, hardware, time.time())
        response = handler.system_info(SystemInfoRequest(), context)
        assert len(response.hostname) > 0

    def test_returns_os_info(self, logger, hardware, context):
        handler = SystemHandler(logger, hardware, time.time())
        response = handler.system_info(SystemInfoRequest(), context)
        assert len(response.os) > 0

    def test_uptime_positive(self, logger, hardware, context):
        start = time.time() - 10  # Pretend started 10 seconds ago
        handler = SystemHandler(logger, hardware, start)
        response = handler.system_info(SystemInfoRequest(), context)
        assert response.uptime.seconds >= 10
