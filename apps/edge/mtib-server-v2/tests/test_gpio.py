"""Tests for GpioHandler."""

import sys
from unittest.mock import patch, MagicMock

import pytest

# Mock gpiod before any handler import can trigger it
_mock_gpiod = MagicMock()
_mock_gpiod.line.Direction.INPUT = "input"
_mock_gpiod.line.Direction.OUTPUT = "output"
_mock_gpiod.line.Value.ACTIVE = 1
_mock_gpiod.line.Value.INACTIVE = 0
sys.modules.setdefault("gpiod", _mock_gpiod)
sys.modules.setdefault("gpiod.line", _mock_gpiod.line)

from src.shared.types import (
    GpioConfigRequest,
    GpioDirection,
    GpioReadRequest,
    GpioWriteRequest,
    Response,
)
from tests.mocks.hardware import MockGpio


class TestGpioHandler:
    """Test GPIO handler with mocked gpiod."""

    @pytest.fixture
    def gpio_handler(self, logger, hardware):
        """Create GPIO handler with mocked GPIOs."""
        from src.providers.handlers.gpio import GpioHandler, DUT_GPIO_PIN_MAP

        # Patch gpiod-based Gpio with MockGpio
        with patch("src.providers.handlers.gpio.Gpio", MockGpio):
            handler = GpioHandler(logger, hardware)
            yield handler

    def test_read_default_input(self, gpio_handler, context):
        """Default GPIOs should read as 0 (input, low)."""
        response = gpio_handler.read(GpioReadRequest(pin=0), context)
        assert response.success is True
        assert response.value is False

    def test_write_and_read(self, gpio_handler, context):
        """Configure as output, write, and read back."""
        # Configure pin 0 as output
        gpio_handler.config(
            GpioConfigRequest(pin=0, direction=GpioDirection.GPIO_OUTPUT),
            context,
        )
        # Write high
        response = gpio_handler.write(GpioWriteRequest(pin=0, value=True), context)
        assert response.success is True

        # Read back
        response = gpio_handler.read(GpioReadRequest(pin=0), context)
        assert response.success is True

    def test_invalid_pin_read(self, gpio_handler, context):
        """Reading an invalid pin should return error."""
        response = gpio_handler.read(GpioReadRequest(pin=99), context)
        assert response.success is False
        assert "Invalid" in response.message

    def test_invalid_pin_write(self, gpio_handler, context):
        """Writing an invalid pin should return error."""
        response = gpio_handler.write(GpioWriteRequest(pin=99, value=True), context)
        assert response.success is False

    def test_config_direction(self, gpio_handler, context):
        """Configuring a pin should change its direction."""
        response = gpio_handler.config(
            GpioConfigRequest(pin=0, direction=GpioDirection.GPIO_OUTPUT),
            context,
        )
        assert response.success is True
