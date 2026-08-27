"""Unit tests for MCP4017 digital potentiometer driver.

Tests the driver with mocked I2CBus to verify I2C communication.
"""

import unittest
from unittest.mock import MagicMock

from src.drivers.mcp4017 import MCP4017, MCP4017Error


def _make_mock_bus():
    """Create a mock I2CBus."""
    return MagicMock()


class TestMCP4017Init(unittest.TestCase):
    """Test MCP4017 initialization."""

    def test_init_success(self):
        bus = _make_mock_bus()
        pot = MCP4017(i2c_bus=bus, logger=MagicMock(), address=0x2F, initial_value=0)
        assert pot._address == 0x2F
        assert pot._current_value == 0

    def test_init_default_address(self):
        bus = _make_mock_bus()
        pot = MCP4017(i2c_bus=bus, logger=MagicMock())
        assert pot._address == 0x2F


class TestMCP4017SetStep(unittest.TestCase):
    """Test wiper position setting."""

    def test_set_step_writes_byte(self):
        bus = _make_mock_bus()
        pot = MCP4017(i2c_bus=bus, logger=MagicMock())
        pot.set_step(64)
        bus.write_byte.assert_called_with(0x2F, 64)
        assert pot.get_step() == 64

    def test_set_step_min(self):
        bus = _make_mock_bus()
        pot = MCP4017(i2c_bus=bus, logger=MagicMock())
        pot.set_step(0)
        bus.write_byte.assert_called_with(0x2F, 0)

    def test_set_step_max(self):
        bus = _make_mock_bus()
        pot = MCP4017(i2c_bus=bus, logger=MagicMock())
        pot.set_step(127)
        bus.write_byte.assert_called_with(0x2F, 127)

    def test_set_step_write_error_raises(self):
        bus = _make_mock_bus()
        bus.write_byte.side_effect = OSError("I2C error")
        pot = MCP4017(i2c_bus=bus, logger=MagicMock())
        with self.assertRaises(MCP4017Error):
            pot.set_step(50)


class TestMCP4017GetStep(unittest.TestCase):
    """Test cached wiper position reading."""

    def test_get_step_returns_cached(self):
        bus = _make_mock_bus()
        pot = MCP4017(i2c_bus=bus, logger=MagicMock(), initial_value=42)
        assert pot.get_step() == 42

    def test_get_step_after_set(self):
        bus = _make_mock_bus()
        pot = MCP4017(i2c_bus=bus, logger=MagicMock())
        pot.set_step(100)
        assert pot.get_step() == 100


class TestMCP4017Constants(unittest.TestCase):
    """Test MCP4017 constants."""

    def test_max_value(self):
        assert MCP4017.MAX_VALUE == 127

    def test_default_address(self):
        assert MCP4017.DEFAULT_ADDRESS == 0x2F


if __name__ == "__main__":
    unittest.main()
