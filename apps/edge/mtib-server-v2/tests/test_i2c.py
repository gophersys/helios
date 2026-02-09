"""Tests for I2cHandler."""

from unittest.mock import MagicMock, patch

import pytest

from src.providers.handlers.i2c import I2cHandler
from src.shared.types import I2cConfig, I2cScanRequest, I2cTransferRequest


@pytest.fixture
def i2c_handler(logger, hardware):
    return I2cHandler(logger, hardware)


class TestI2cConfigure:
    def test_configure_succeeds(self, i2c_handler, context):
        response = i2c_handler.configure(
            I2cConfig(bus=3, speed_hz=400000),
            context,
        )
        assert response.success is True

    def test_configure_stores_config(self, i2c_handler, context):
        i2c_handler.configure(I2cConfig(bus=3, speed_hz=400000), context)
        assert 3 in i2c_handler._configured_buses
        assert i2c_handler._configured_buses[3] == 400000


class TestI2cScan:
    def test_scan_with_mock(self, i2c_handler, context):
        """Test scan with a mocked smbus2."""
        mock_bus = MagicMock()
        # Simulate devices at 0x19, 0x2F
        def mock_read_byte(addr):
            if addr in (0x19, 0x2F):
                return 0
            raise OSError("Remote I/O error")

        mock_bus.__enter__ = MagicMock(return_value=mock_bus)
        mock_bus.__exit__ = MagicMock(return_value=False)
        mock_bus.read_byte = mock_read_byte

        mock_smbus2 = MagicMock()
        mock_smbus2.SMBus.return_value = mock_bus

        with patch.dict("sys.modules", {"smbus2": mock_smbus2}):
            response = i2c_handler.scan(I2cScanRequest(bus=3), context)

        assert response.success is True
        assert 0x19 in response.addresses
        assert 0x2F in response.addresses
        assert len(response.addresses) == 2


class TestI2cTransfer:
    def test_transfer_write(self, i2c_handler, context):
        """Test write-only transfer with mocked smbus2."""
        mock_bus = MagicMock()
        mock_bus.__enter__ = MagicMock(return_value=mock_bus)
        mock_bus.__exit__ = MagicMock(return_value=False)

        mock_smbus2 = MagicMock()
        mock_smbus2.SMBus.return_value = mock_bus

        with patch.dict("sys.modules", {"smbus2": mock_smbus2}):
            response = i2c_handler.transfer(
                I2cTransferRequest(bus=3, address=0x2F, write_data=b"\x00", read_size=0),
                context,
            )

        assert response.success is True

    def test_transfer_nak(self, i2c_handler, context):
        """Test NAK response."""
        mock_bus = MagicMock()
        mock_bus.__enter__ = MagicMock(return_value=mock_bus)
        mock_bus.__exit__ = MagicMock(return_value=False)
        mock_bus.i2c_rdwr.side_effect = OSError("Remote I/O error")

        mock_smbus2 = MagicMock()
        mock_smbus2.SMBus.return_value = mock_bus

        with patch.dict("sys.modules", {"smbus2": mock_smbus2}):
            response = i2c_handler.transfer(
                I2cTransferRequest(bus=3, address=0xFF, write_data=b"\x00"),
                context,
            )

        assert response.success is False
        assert response.nak is True
