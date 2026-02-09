import logging
from typing import Dict, Optional

from corekinect.utils import Logger

try:
    import smbus2 as smbus
except ImportError:
    import smbus


class MCP4017Error(Exception):
    """Base exception for MCP4017 errors."""

    pass


class MCP4017:
    """Driver for the MCP4017 digital potentiometer.

    The MCP4017 is a 7-bit (128 steps) digital potentiometer with I2C interface.
    Address is fixed at 0x2F.
    """

    # Constants
    MAX_VALUE = 127  # 7-bit resolution
    DEFAULT_ADDRESS = 0x2F
    DEFAULT_BUS = 3  # /dev/i2c-3 = Verdin I2C_1 (main bus on TorizonOS)

    def scan_bus(self, bus: int = DEFAULT_BUS) -> Dict[int, bool]:
        """Scan the I2C bus for devices.

        Args:
            bus: I2C bus number to scan.

        Returns:
            Dictionary mapping addresses to whether they responded.
        """
        devices: Dict[int, bool] = {}
        i2c = None
        try:
            i2c = smbus.SMBus(bus)

            for addr in range(0x08, 0x78):
                try:
                    i2c.read_byte(addr)
                    devices[addr] = True
                    self.logger.info(f"Found device at address 0x{addr:02x}")
                except OSError:
                    devices[addr] = False

            if self.DEFAULT_ADDRESS in devices and devices[self.DEFAULT_ADDRESS]:
                self.logger.info("MCP4017 found at expected address 0x2F")
            else:
                self.logger.warning("MCP4017 not found at expected address 0x2F")

            return devices

        except Exception as e:
            raise MCP4017Error(f"Failed to scan I2C bus: {str(e)}")
        finally:
            if i2c is not None:
                try:
                    i2c.close()
                except OSError:
                    pass

    def __init__(
        self,
        logger: Logger,
        bus: int = DEFAULT_BUS,
        address: int = DEFAULT_ADDRESS,
        verify: bool = True,
        initial_value: int = 0,
    ):
        """Initialize the MCP4017 driver.

        Args:
            logger: Logger instance.
            bus: I2C bus number (default: 3).
            address: I2C address (default: 0x2F).
            verify: Whether to verify device presence on bus (default: True).
            initial_value: Initial wiper position (default: 0).

        Raises:
            MCP4017Error: If I2C bus initialization fails or device not found.
        """
        self.logger = logger

        try:
            self._bus = smbus.SMBus(bus)
            self._address = address
            self._current_value = initial_value

        except Exception as e:
            raise MCP4017Error(f"Failed to initialize MCP4017: {str(e)}")

    def set_step(self, value: int) -> None:
        """Set the wiper position (resistance value).

        Args:
            value: Resistance value (0-127).

        Raises:
            MCP4017Error: If value is out of range or write fails.
        """
        if not 0 <= value <= self.MAX_VALUE:
            raise MCP4017Error(f"Value must be between 0 and {self.MAX_VALUE}, got {value}")

        try:
            self._bus.write_byte(self._address, value)
            self._current_value = value

        except Exception as e:
            raise MCP4017Error(f"Failed to set step: {str(e)}")

    def get_step(self) -> int:
        """Get the current wiper position.

        Note: The MCP4017 is write-only, so this returns the last written value
        that we've cached.

        Returns:
            Current resistance value (0-127).
        """
        return self._current_value

    def __del__(self) -> None:
        """Cleanup when object is destroyed."""
        try:
            self._bus.close()
        except (OSError, AttributeError):
            pass
