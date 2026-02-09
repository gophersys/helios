from typing import List, Optional, Tuple

from protocols.mtib_v2.mtib_v2_pb2 import I2cConfig, I2cScanRequest, I2cTransferRequest

from ._base import BaseClient
from ..types.bus import I2cResult, I2cScanResult


class I2cMixin(BaseClient):
    """I2C master operations."""

    def i2c_configure(self, bus: int = 0, speed_hz: int = 400000) -> Optional[str]:
        """Configure an I2C bus.

        Args:
            bus: I2C bus number.
            speed_hz: Bus speed in Hz (100000, 400000, 1000000, 3400000).

        Returns:
            Error message string, or None on success.
        """
        try:
            resp = self._call("I2cConfigure", I2cConfig(bus=bus, speed_hz=speed_hz))
            if not resp.success:
                return resp.message
            return None
        except Exception as e:
            return f"i2c_configure error: {e}"

    def i2c_transfer(
        self,
        bus: int,
        address: int,
        write_data: bytes = b"",
        read_size: int = 0,
        repeated_start: bool = False,
    ) -> Tuple[Optional[str], Optional[I2cResult]]:
        """Perform an I2C transfer.

        Args:
            bus: I2C bus number.
            address: 7-bit I2C slave address.
            write_data: Data to write to the device.
            read_size: Number of bytes to read.
            repeated_start: Whether to use repeated start between write and read.

        Returns:
            (error, I2cResult) tuple. error is None on success.
        """
        try:
            resp = self._call(
                "I2cTransfer",
                I2cTransferRequest(
                    bus=bus,
                    address=address,
                    write_data=write_data,
                    read_size=read_size,
                    repeated_start=repeated_start,
                ),
            )
            if not resp.success:
                return resp.message, None
            return None, I2cResult(read_data=resp.read_data, nak=resp.nak)
        except Exception as e:
            return f"i2c_transfer error: {e}", None

    def i2c_scan(self, bus: int = 0) -> Tuple[Optional[str], Optional[I2cScanResult]]:
        """Scan an I2C bus for devices.

        Args:
            bus: I2C bus number.

        Returns:
            (error, I2cScanResult) tuple. error is None on success.
        """
        try:
            resp = self._call("I2cScan", I2cScanRequest(bus=bus))
            if not resp.success:
                return resp.message, None
            return None, I2cScanResult(addresses=list(resp.addresses))
        except Exception as e:
            return f"i2c_scan error: {e}", None
