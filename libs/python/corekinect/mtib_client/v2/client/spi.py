from typing import Optional, Tuple

from protocols.mtib_v2.mtib_v2_pb2 import SpiConfig, SpiTransferRequest

from ._base import BaseClient
from ..types.bus import SpiResult


class SpiMixin(BaseClient):
    """SPI master operations."""

    def spi_configure(
        self,
        bus: int = 0,
        speed_hz: int = 1000000,
        cpol: bool = False,
        cpha: bool = False,
        bits_per_word: int = 8,
        msb_first: bool = True,
        cs_pin: int = 0,
    ) -> Optional[str]:
        """Configure an SPI bus.

        Args:
            bus: SPI bus number.
            speed_hz: Clock speed in Hz.
            cpol: Clock polarity.
            cpha: Clock phase.
            bits_per_word: Bits per transfer word.
            msb_first: MSB-first bit ordering.
            cs_pin: Chip select GPIO pin.

        Returns:
            Error message string, or None on success.
        """
        try:
            resp = self._call(
                "SpiConfigure",
                SpiConfig(
                    bus=bus,
                    speed_hz=speed_hz,
                    cpol=cpol,
                    cpha=cpha,
                    bits_per_word=bits_per_word,
                    msb_first=msb_first,
                    cs_pin=cs_pin,
                ),
            )
            if not resp.success:
                return resp.message
            return None
        except Exception as e:
            return f"spi_configure error: {e}"

    def spi_transfer(
        self, bus: int, tx_data: bytes, rx_size: int = 0, keep_cs_active: bool = False
    ) -> Tuple[Optional[str], Optional[SpiResult]]:
        """Perform an SPI transfer.

        Args:
            bus: SPI bus number.
            tx_data: Data to transmit.
            rx_size: Number of bytes to receive (can differ from tx for half-duplex).
            keep_cs_active: Whether to keep CS asserted after transfer.

        Returns:
            (error, SpiResult) tuple. error is None on success.
        """
        try:
            resp = self._call(
                "SpiTransfer",
                SpiTransferRequest(
                    bus=bus, tx_data=tx_data, rx_size=rx_size, keep_cs_active=keep_cs_active
                ),
            )
            if not resp.success:
                return resp.message, None
            return None, SpiResult(rx_data=resp.rx_data)
        except Exception as e:
            return f"spi_transfer error: {e}", None
