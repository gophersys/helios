"""Unit tests for the grpc_method decorator and MtibV1Provider initialization.

Tests the request logging, timing, and error handling behavior of the
grpc_method decorator without requiring actual hardware.
"""

import unittest
from unittest.mock import MagicMock, patch
from dataclasses import dataclass

from src.server import grpc_method
from src.config import MtibV1ProviderConfig, GPIO_PIN_MAP


class FakeServicer:
    """Fake servicer for testing the grpc_method decorator."""

    def __init__(self):
        self.logger = MagicMock()

    @grpc_method
    def success_method(self, request, context):
        return "ok"

    @grpc_method
    def error_method(self, request, context):
        raise ValueError("test error")

    @grpc_method
    def slow_method(self, request, context):
        import time
        time.sleep(0.05)
        return "slow ok"


class TestGrpcMethodDecorator(unittest.TestCase):
    """Test the grpc_method decorator."""

    def setUp(self):
        self.servicer = FakeServicer()
        self.request = MagicMock()
        self.context = MagicMock()
        self.context.peer.return_value = "ipv4:127.0.0.1:5555"

    def test_success_logs_request(self):
        result = self.servicer.success_method(self.request, self.context)
        assert result == "ok"
        # Should log request received and processed OK
        assert self.servicer.logger.debug.call_count == 2

    def test_success_returns_response(self):
        result = self.servicer.success_method(self.request, self.context)
        assert result == "ok"

    def test_error_logs_and_reraises(self):
        with self.assertRaises(ValueError) as cm:
            self.servicer.error_method(self.request, self.context)
        assert "test error" in str(cm.exception)
        # Should log the error
        self.servicer.logger.error.assert_called_once()

    def test_timing_logged(self):
        self.servicer.slow_method(self.request, self.context)
        # The debug call for "processed OK" should contain "ms"
        calls = self.servicer.logger.debug.call_args_list
        assert any("ms" in str(call) for call in calls)


class TestGpioPinMap(unittest.TestCase):
    """Test that the consolidated GPIO pin map is correct."""

    def test_has_9_pins(self):
        assert len(GPIO_PIN_MAP) == 9

    def test_main_connector_pins(self):
        """Pins 0-6 are on the main connector."""
        from src.drivers.gpio import Pin
        assert GPIO_PIN_MAP[0] == Pin.SODIMM_206
        assert GPIO_PIN_MAP[1] == Pin.SODIMM_208
        assert GPIO_PIN_MAP[2] == Pin.SODIMM_210
        assert GPIO_PIN_MAP[3] == Pin.SODIMM_212

    def test_auxiliary_connector_pins(self):
        """Pins 7-8 are on the auxiliary connector."""
        from src.drivers.gpio import Pin
        assert GPIO_PIN_MAP[7] == Pin.SODIMM_15
        assert GPIO_PIN_MAP[8] == Pin.SODIMM_16


class TestMtibV1ProviderConfig(unittest.TestCase):
    """Test the provider config dataclass."""

    def test_config_fields(self):
        config = MtibV1ProviderConfig(
            HARDWARE_VERSION="REV1.2",
            ASSETS_DIR="/assets",
            METRICS_ENABLED=False,
            METRICS_BROKER_URL="mqtt://localhost:1883",
            MOTION_ENABLED=False,
        )
        assert config.HARDWARE_VERSION == "REV1.2"
        assert config.METRICS_ENABLED is False
        assert config.MOTION_ENABLED is False


if __name__ == "__main__":
    unittest.main()
