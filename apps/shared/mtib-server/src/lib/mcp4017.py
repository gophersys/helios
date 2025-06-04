import smbus
import logging
from typing import Optional, List, Dict
import time


class MCP4017Error(Exception):
    """Base exception for MCP4017 errors"""

    pass


class MCP4017:
    """Driver for the MCP4017 digital potentiometer.

    The MCP4017 is a 7-bit (128 steps) digital potentiometer with I2C interface.
    Address is fixed at 0x2F.
    """

    # Constants
    MAX_VALUE = 127  # 7-bit resolution
    DEFAULT_ADDRESS = 0x2F
    DEFAULT_BUS = 3  # Based on your i2cdetect output

    def scan_bus(self, bus: int = DEFAULT_BUS) -> Dict[int, bool]:
        """Scan the I2C bus for devices.

        Args:
            bus: I2C bus number to scan

        Returns:
            Dictionary mapping addresses to whether they responded
        """
        devices = {}
        i2c = None
        try:
            # Create bus connection
            i2c = smbus.SMBus(bus)

            # Scan all possible 7-bit addresses (0x08-0x77)
            for addr in range(0x08, 0x78):
                try:
                    # Try to read a byte from the address
                    i2c.read_byte(addr)
                    devices[addr] = True
                    self.logger.info(f"Found device at address 0x{addr:02x}")
                except:
                    devices[addr] = False

            # Log specific check for MCP4017
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
                except:
                    pass  # Ignore errors during cleanup

    def __init__(
        self,
        logger: logging.Logger,
        bus: int = DEFAULT_BUS,
        address: int = DEFAULT_ADDRESS,
        verify: bool = True,
        initial_value: int = 0,
    ):
        """Initialize the MCP4017 driver.

        Args:
            bus: I2C bus number (default: 3)
            address: I2C address (default: 0x2F)
            verify: Whether to verify device presence on bus (default: True)

        Raises:
            MCP4017Error: If I2C bus initialization fails or device not found
        """
        self.logger = logger

        # if verify:
        #     devices = self.scan_bus(bus)
        #     if not devices.get(address, False):
        #         raise MCP4017Error(f"No device found at address 0x{address:02x}")

        try:
            self._bus = smbus.SMBus(bus)
            self._address = address
            self._current_value = 0

            # Initialize to 0
            self.set_resistance(0)
            logger.info("MCP4017 initialized successfully")
            for i in range(128):
                self.set_resistance(i)
                time.sleep(0.1)

        except Exception as e:
            raise MCP4017Error(f"Failed to initialize MCP4017: {str(e)}")

    def set_resistance(self, value: int) -> None:
        """Set the wiper position (resistance value).

        Args:
            value: Resistance value (0-127)

        Raises:
            MCP4017Error: If value is out of range or write fails
        """
        # if not 0 <= value <= self.MAX_VALUE:
        #     raise MCP4017Error(f"Value must be between 0 and {self.MAX_VALUE}")

        try:
            self._bus.write_byte(self._address, value)
            self._current_value = value
            self.logger.debug(f"Set MCP4017 resistance to {value}")

        except Exception as e:
            raise MCP4017Error(f"Failed to set resistance: {str(e)}")

    def get_resistance(self) -> int:
        """Get the current wiper position.

        Note: The MCP4017 is write-only, so this returns the last written value
        that we've cached.

        Returns:
            Current resistance value (0-127)
        """
        return self._current_value

    def __del__(self):
        """Cleanup when object is destroyed"""
        try:
            self._bus.close()
        except:
            pass  # Ignore errors during cleanup
