"""Tests for SpiHandler."""

import sys
from unittest.mock import MagicMock, patch

import pytest

from src.providers.handlers.spi import SpiHandler
from src.shared.types import SpiConfig, SpiTransferRequest


@pytest.fixture
def spi_handler(logger, hardware):
    return SpiHandler(logger, hardware)


class TestSpiConfigure:
    def test_configure_stores_config(self, spi_handler, context):
        """Configure stores bus settings in _configs dict."""
        request = SpiConfig(bus=0, speed_hz=1000000, cpol=False, cpha=False, bits_per_word=8, msb_first=True, cs_pin=0)
        response = spi_handler.configure(request, context)

        assert response.success is True
        assert 0 in spi_handler._configs
        assert spi_handler._configs[0]["speed_hz"] == 1000000

    def test_default_bits_per_word_applied(self, spi_handler, context):
        """bits_per_word defaults to 8 when set to 0."""
        request = SpiConfig(bus=1, speed_hz=500000, bits_per_word=0)
        spi_handler.configure(request, context)

        assert spi_handler._configs[1]["bits_per_word"] == 8


class TestSpiTransfer:
    def test_tx_returns_rx_data(self, spi_handler, context):
        """TX transfer returns received data from xfer2."""
        mock_spidev = MagicMock()
        mock_spi_instance = MagicMock()
        mock_spidev.SpiDev.return_value = mock_spi_instance
        mock_spi_instance.xfer2.return_value = [0xAB, 0xCD]

        request = SpiTransferRequest(bus=0, tx_data=bytes([0x01, 0x02]), rx_size=0)

        with patch.dict("sys.modules", {"spidev": mock_spidev}):
            response = spi_handler.transfer(request, context)

        assert response.success is True
        assert response.rx_data == bytes([0xAB, 0xCD])
        mock_spi_instance.xfer2.assert_called_once_with([0x01, 0x02])
        mock_spi_instance.close.assert_called_once()

    def test_read_only_transfer(self, spi_handler, context):
        """Read-only transfer uses readbytes when no tx_data."""
        mock_spidev = MagicMock()
        mock_spi_instance = MagicMock()
        mock_spidev.SpiDev.return_value = mock_spi_instance
        mock_spi_instance.readbytes.return_value = [0x01, 0x02]

        request = SpiTransferRequest(bus=0, tx_data=b"", rx_size=2)

        with patch.dict("sys.modules", {"spidev": mock_spidev}):
            response = spi_handler.transfer(request, context)

        assert response.success is True
        assert response.rx_data == bytes([0x01, 0x02])
        mock_spi_instance.readbytes.assert_called_once_with(2)
        mock_spi_instance.close.assert_called_once()

    def test_no_data_returns_empty(self, spi_handler, context):
        """No tx_data and rx_size=0 returns empty response."""
        mock_spidev = MagicMock()
        mock_spi_instance = MagicMock()
        mock_spidev.SpiDev.return_value = mock_spi_instance

        request = SpiTransferRequest(bus=0, tx_data=b"", rx_size=0)

        with patch.dict("sys.modules", {"spidev": mock_spidev}):
            response = spi_handler.transfer(request, context)

        assert response.success is True
        assert response.rx_data == b""
        assert "No data" in response.message
        mock_spi_instance.close.assert_called_once()

    def test_spidev_import_error(self, spi_handler, context):
        """Missing spidev module returns success=False."""
        request = SpiTransferRequest(bus=0, tx_data=bytes([0x01]), rx_size=0)

        with patch.dict("sys.modules", {"spidev": None}):
            response = spi_handler.transfer(request, context)

        assert response.success is False
        assert "spidev" in response.message.lower()
        assert response.rx_data == b""

    def test_transfer_exception(self, spi_handler, context):
        """xfer2 raising an exception returns success=False."""
        mock_spidev = MagicMock()
        mock_spi_instance = MagicMock()
        mock_spidev.SpiDev.return_value = mock_spi_instance
        mock_spi_instance.xfer2.side_effect = OSError("SPI bus error")

        request = SpiTransferRequest(bus=0, tx_data=bytes([0x01]), rx_size=0)

        with patch.dict("sys.modules", {"spidev": mock_spidev}):
            response = spi_handler.transfer(request, context)

        assert response.success is False
        assert "SPI bus error" in response.message
        mock_spi_instance.close.assert_called_once()
