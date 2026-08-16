"""MCP4017 digital potentiometer driver.

7-bit (128 steps) digital potentiometer with I2C interface.
Uses shared I2CBus instead of managing its own SMBus connection.
"""

from corekinect.utils import Logger

from src.drivers.i2c_bus import I2CBus


class MCP4017Error(Exception):
    """Base exception for MCP4017 errors."""

    pass


class MCP4017:
    """Driver for the MCP4017 digital potentiometer."""

    # Constants
    MAX_VALUE = 127  # 7-bit resolution
    DEFAULT_ADDRESS = 0x2F

    def __init__(
        self,
        i2c_bus: I2CBus,
        logger: Logger,
        address: int = DEFAULT_ADDRESS,
        initial_value: int = 0,
    ):
        """Initialize the MCP4017 driver.

        Args:
            i2c_bus: Shared thread-safe I2C bus instance
            logger: Logger instance
            address: I2C address (default: 0x2F)
            initial_value: Initial wiper position (default: 0)

        Raises:
            MCP4017Error: If initialization fails
        """
        self.logger = logger
        self._bus = i2c_bus
        self._address = address
        self._current_value = initial_value

    def set_step(self, value: int) -> None:
        """Set the wiper position (resistance value).

        Args:
            value: Resistance value (0-127)

        Raises:
            MCP4017Error: If write fails
        """
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
            Current resistance value (0-127)
        """
        return self._current_value
