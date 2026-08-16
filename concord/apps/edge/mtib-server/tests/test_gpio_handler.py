"""Unit tests for GPIO handler.

Tests GPIO config, read, write, and resistor bias application.
"""

import unittest
from unittest.mock import MagicMock, patch

from src.shared.types import (
    GpioConfigRequest,
    GpioConfigResponse,
    GpioDirection,
    GpioReadRequest,
    GpioReadResponse,
    GpioResistorConfig,
    GpioWriteRequest,
    GpioWriteResponse,
    SnapshotGpio,
)
from src.handlers.gpio import GpioHandler


def _make_mock_gpio(read_val=0, read_err=None, write_err=None, init_err=None):
    """Create a mock Gpio object with configurable behavior."""
    gpio = MagicMock()
    gpio.read.return_value = (read_err, read_val)
    gpio.write.return_value = write_err
    gpio.init.return_value = init_err
    gpio.deinit.return_value = None
    gpio.direction = None
    gpio.bias = None
    return gpio


class TestGpioConfig(unittest.TestCase):
    """Test GpioConfig RPC handler."""

    def setUp(self):
        self.logger = MagicMock()
        self.gpios = {0: _make_mock_gpio(), 1: _make_mock_gpio(), 2: _make_mock_gpio()}
        self.handler = GpioHandler(self.gpios, self.logger)
        self.ctx = MagicMock()

    def test_config_output(self):
        req = GpioConfigRequest(gpio=0, direction=GpioDirection.GPIO_DIRECTION_OUTPUT)
        resp = self.handler.config(req, self.ctx)
        assert resp.success is True
        self.gpios[0].deinit.assert_called_once()
        self.gpios[0].init.assert_called_once()

    def test_config_input(self):
        req = GpioConfigRequest(gpio=1, direction=GpioDirection.GPIO_DIRECTION_INPUT)
        resp = self.handler.config(req, self.ctx)
        assert resp.success is True

    def test_config_invalid_gpio(self):
        req = GpioConfigRequest(gpio=99, direction=GpioDirection.GPIO_DIRECTION_OUTPUT)
        resp = self.handler.config(req, self.ctx)
        assert resp.success is False
        assert "99" in resp.message

    def test_config_init_failure(self):
        self.gpios[0].init.return_value = "hardware fault"
        req = GpioConfigRequest(gpio=0, direction=GpioDirection.GPIO_DIRECTION_OUTPUT)
        resp = self.handler.config(req, self.ctx)
        assert resp.success is False
        assert "hardware fault" in resp.message

    def test_config_applies_pullup_resistor(self):
        req = GpioConfigRequest(
            gpio=0,
            direction=GpioDirection.GPIO_DIRECTION_INPUT,
            resistor=GpioResistorConfig.GPIO_RESISTOR_PULL_UP,
        )
        resp = self.handler.config(req, self.ctx)
        assert resp.success is True
        # Verify bias was set on the gpio object
        from gpiod.line import Bias
        assert self.gpios[0].bias == Bias.PULL_UP

    def test_config_applies_pulldown_resistor(self):
        req = GpioConfigRequest(
            gpio=1,
            direction=GpioDirection.GPIO_DIRECTION_INPUT,
            resistor=GpioResistorConfig.GPIO_RESISTOR_PULL_DOWN,
        )
        resp = self.handler.config(req, self.ctx)
        assert resp.success is True
        from gpiod.line import Bias
        assert self.gpios[1].bias == Bias.PULL_DOWN

    def test_config_applies_no_resistor(self):
        req = GpioConfigRequest(
            gpio=2,
            direction=GpioDirection.GPIO_DIRECTION_OUTPUT,
            resistor=GpioResistorConfig.GPIO_RESISTOR_NONE,
        )
        resp = self.handler.config(req, self.ctx)
        assert resp.success is True
        from gpiod.line import Bias
        assert self.gpios[2].bias == Bias.DISABLED


class TestGpioWrite(unittest.TestCase):
    """Test GpioWrite RPC handler."""

    def setUp(self):
        self.logger = MagicMock()
        self.gpios = {0: _make_mock_gpio(), 1: _make_mock_gpio()}
        self.handler = GpioHandler(self.gpios, self.logger)
        self.ctx = MagicMock()

    def test_write_high(self):
        req = GpioWriteRequest(gpio=0, state=True)
        resp = self.handler.write(req, self.ctx)
        assert resp.success is True
        self.gpios[0].write.assert_called_once_with(1)

    def test_write_low(self):
        req = GpioWriteRequest(gpio=0, state=False)
        resp = self.handler.write(req, self.ctx)
        assert resp.success is True
        self.gpios[0].write.assert_called_once_with(0)

    def test_write_invalid_gpio(self):
        req = GpioWriteRequest(gpio=99, state=True)
        resp = self.handler.write(req, self.ctx)
        assert resp.success is False

    def test_write_error(self):
        self.gpios[0].write.return_value = "write failed"
        req = GpioWriteRequest(gpio=0, state=True)
        resp = self.handler.write(req, self.ctx)
        assert resp.success is False


class TestGpioRead(unittest.TestCase):
    """Test GpioRead RPC handler."""

    def setUp(self):
        self.logger = MagicMock()
        self.gpios = {0: _make_mock_gpio(read_val=1), 1: _make_mock_gpio(read_val=0)}
        self.handler = GpioHandler(self.gpios, self.logger)
        self.ctx = MagicMock()

    def test_read_high(self):
        req = GpioReadRequest(gpio=0)
        resp = self.handler.read(req, self.ctx)
        assert resp.success is True
        assert resp.state is True

    def test_read_low(self):
        req = GpioReadRequest(gpio=1)
        resp = self.handler.read(req, self.ctx)
        assert resp.success is True
        assert resp.state is False

    def test_read_invalid_gpio(self):
        req = GpioReadRequest(gpio=42)
        resp = self.handler.read(req, self.ctx)
        assert resp.success is False

    def test_read_error(self):
        self.gpios[0].read.return_value = ("read failed", 0)
        req = GpioReadRequest(gpio=0)
        resp = self.handler.read(req, self.ctx)
        assert resp.success is False


class TestGpioSnapshot(unittest.TestCase):
    """Test GPIO snapshot data for observability."""

    def setUp(self):
        self.logger = MagicMock()
        self.gpios = {
            0: _make_mock_gpio(read_val=1),
            1: _make_mock_gpio(read_val=0),
            2: _make_mock_gpio(read_err="fail"),
        }
        self.handler = GpioHandler(self.gpios, self.logger)

    def test_snapshot_returns_readable_gpios(self):
        data = self.handler.get_snapshot_data()
        # GPIO 2 has read error, so only 0 and 1 should be in snapshot
        assert len(data) == 2
        states = {d.gpio: d.state for d in data}
        assert states[0] is True
        assert states[1] is False

    def test_snapshot_empty_gpios(self):
        handler = GpioHandler({}, self.logger)
        assert handler.get_snapshot_data() == []


if __name__ == "__main__":
    unittest.main()
