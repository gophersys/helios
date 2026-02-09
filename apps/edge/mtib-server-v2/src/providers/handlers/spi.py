"""SPI master handler for V2 protocol."""

from typing import TYPE_CHECKING

from corekinect.utils import Logger
from src.shared.types import (
    Response,
    SpiConfig,
    SpiTransferRequest,
    SpiTransferResponse,
)

if TYPE_CHECKING:
    from src.hardware import HardwareContext


class SpiHandler:
    """Handles SPI master RPCs."""

    def __init__(self, logger: Logger, hardware: "HardwareContext"):
        self.logger = logger
        self.hardware = hardware
        self._configs: dict[int, dict] = {}  # bus -> config

    def configure(self, request: SpiConfig, context) -> Response:
        """Configure an SPI bus."""
        self._configs[request.bus] = {
            "speed_hz": request.speed_hz,
            "cpol": request.cpol,
            "cpha": request.cpha,
            "bits_per_word": request.bits_per_word or 8,
            "msb_first": request.msb_first,
            "cs_pin": request.cs_pin,
        }
        self.logger.info(f"SPI bus {request.bus} configured at {request.speed_hz}Hz")
        return Response(success=True, message="")

    def transfer(self, request: SpiTransferRequest, context) -> SpiTransferResponse:
        """Perform an SPI transfer."""
        try:
            import spidev

            bus_num = request.bus if request.bus > 0 else 0
            config = self._configs.get(bus_num, {})

            spi = spidev.SpiDev()
            spi.open(bus_num, config.get("cs_pin", 0))
            spi.max_speed_hz = config.get("speed_hz", 1000000)
            spi.mode = (1 if config.get("cpol", False) else 0) << 1 | (1 if config.get("cpha", False) else 0)
            spi.bits_per_word = config.get("bits_per_word", 8)

            try:
                if request.tx_data:
                    rx_data = spi.xfer2(list(request.tx_data))
                    return SpiTransferResponse(success=True, message="", rx_data=bytes(rx_data))
                elif request.rx_size > 0:
                    rx_data = spi.readbytes(request.rx_size)
                    return SpiTransferResponse(success=True, message="", rx_data=bytes(rx_data))
                else:
                    return SpiTransferResponse(success=True, message="No data to transfer", rx_data=b"")
            finally:
                spi.close()

        except ImportError:
            return SpiTransferResponse(success=False, message="spidev not available", rx_data=b"")
        except Exception as e:
            return SpiTransferResponse(success=False, message=str(e), rx_data=b"")
