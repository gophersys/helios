"""I2C master handler for V2 protocol."""

from typing import TYPE_CHECKING

from corekinect.utils import Logger
from src.shared.types import (
    I2cConfig,
    I2cScanRequest,
    I2cScanResponse,
    I2cTransferRequest,
    I2cTransferResponse,
    Response,
)

if TYPE_CHECKING:
    from src.hardware import HardwareContext


class I2cHandler:
    """Handles I2C master RPCs."""

    def __init__(self, logger: Logger, hardware: "HardwareContext"):
        self.logger = logger
        self.hardware = hardware
        self._configured_buses: dict[int, int] = {}  # bus -> speed_hz

    def configure(self, request: I2cConfig, context) -> Response:
        """Configure an I2C bus."""
        self._configured_buses[request.bus] = request.speed_hz
        self.logger.info(f"I2C bus {request.bus} configured at {request.speed_hz}Hz")
        return Response(success=True, message="")

    def transfer(self, request: I2cTransferRequest, context) -> I2cTransferResponse:
        """Perform an I2C transfer (write and/or read)."""
        try:
            import smbus2

            bus_num = request.bus if request.bus > 0 else 3  # Default to /dev/i2c-3 (Verdin I2C_1)
            with smbus2.SMBus(bus_num) as bus:
                read_data = b""

                if request.write_data and request.read_size > 0:
                    # Write then read (repeated start)
                    write_msg = smbus2.i2c_msg.write(request.address, list(request.write_data))
                    read_msg = smbus2.i2c_msg.read(request.address, request.read_size)
                    bus.i2c_rdwr(write_msg, read_msg)
                    read_data = bytes(list(read_msg))
                elif request.write_data:
                    # Write only
                    write_msg = smbus2.i2c_msg.write(request.address, list(request.write_data))
                    bus.i2c_rdwr(write_msg)
                elif request.read_size > 0:
                    # Read only
                    read_msg = smbus2.i2c_msg.read(request.address, request.read_size)
                    bus.i2c_rdwr(read_msg)
                    read_data = bytes(list(read_msg))

                return I2cTransferResponse(success=True, message="", read_data=read_data, nak=False)

        except OSError as e:
            if "Remote I/O error" in str(e):
                return I2cTransferResponse(success=False, message="NAK", read_data=b"", nak=True)
            return I2cTransferResponse(success=False, message=str(e), read_data=b"", nak=False)
        except Exception as e:
            return I2cTransferResponse(success=False, message=str(e), read_data=b"", nak=False)

    def scan(self, request: I2cScanRequest, context) -> I2cScanResponse:
        """Scan I2C bus for responding addresses."""
        try:
            import smbus2

            bus_num = request.bus if request.bus > 0 else 3
            addresses = []

            with smbus2.SMBus(bus_num) as bus:
                for addr in range(0x08, 0x78):
                    try:
                        # force=True to detect kernel-claimed devices (UU in i2cdetect)
                        bus.read_byte(addr, force=True)
                        addresses.append(addr)
                    except OSError:
                        continue

            self.logger.info(f"I2C scan on bus {bus_num}: found {len(addresses)} devices")
            return I2cScanResponse(success=True, message="", addresses=addresses)

        except Exception as e:
            return I2cScanResponse(success=False, message=str(e), addresses=[])
