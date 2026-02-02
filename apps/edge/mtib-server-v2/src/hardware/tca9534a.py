"""TCA9534A I2C GPIO expander driver.

The TCA9534A is an 8-bit I/O expander for I2C bus. It provides general-purpose
remote I/O expansion via the I2C interface.

This driver is only used on REV 1.2 boards where the TCA9534A controls:
- P0: JLINK_MUL - J-Link multiplexer select
- P1: EEPROM_WP - EEPROM write protect
- P2: VMM_EN - Motor power enable
- P3-P7: Reserved

Usage:
    gpio_expander = TCA9534A(bus_num=1)
    gpio_expander.init()

    # Set motor power enable
    gpio_expander.set_pin(TCA9534APin.VMM_EN, True)

    # Read current output state
    state = gpio_expander.read_output()
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from typing import Optional

import smbus2


class TCA9534ARegister(IntEnum):
    """TCA9534A register addresses."""

    INPUT = 0x00  # Input port register (read-only)
    OUTPUT = 0x01  # Output port register
    POLARITY = 0x02  # Polarity inversion register
    CONFIG = 0x03  # Configuration register (0=output, 1=input)


class TCA9534APin(IntEnum):
    """Pin definitions for the TCA9534A on MTIB REV 1.2.

    These correspond to the physical connections on the PCB.
    """

    JLINK_MUL = 0  # P0: J-Link multiplexer select (0=normal, 1=swapped)
    EEPROM_WP = 1  # P1: EEPROM write protect (0=enabled, 1=protected)
    VMM_EN = 2  # P2: Motor power enable (0=off, 1=on)
    GPIO_3 = 3  # P3: Reserved
    GPIO_4 = 4  # P4: Reserved
    GPIO_5 = 5  # P5: Reserved
    GPIO_6 = 6  # P6: Reserved
    GPIO_7 = 7  # P7: Reserved

    @property
    def mask(self) -> int:
        """Get the bitmask for this pin."""
        return 1 << self.value


@dataclass
class TCA9534AState:
    """Current state of all TCA9534A pins."""

    output: int  # Current output register value
    config: int  # Current configuration register value

    def is_output(self, pin: TCA9534APin) -> bool:
        """Check if a pin is configured as output."""
        return (self.config & pin.mask) == 0

    def get_pin(self, pin: TCA9534APin) -> bool:
        """Get the output state of a pin."""
        return (self.output & pin.mask) != 0


class TCA9534A:
    """Driver for the TCA9534A I2C GPIO expander.

    This class provides a clean interface for controlling the GPIO expander
    on MTIB REV 1.2 boards.
    """

    DEFAULT_ADDRESS = 0x38
    DEFAULT_BUS = 1

    def __init__(
        self,
        bus_num: int = DEFAULT_BUS,
        address: int = DEFAULT_ADDRESS,
    ):
        """Initialize the TCA9534A driver.

        Args:
            bus_num: I2C bus number
            address: I2C device address (default 0x38)
        """
        self._bus_num = bus_num
        self._address = address
        self._bus: Optional[smbus2.SMBus] = None
        self._output_cache: int = 0x00  # Cache of output register

    def init(self) -> None:
        """Initialize the GPIO expander.

        Configures all pins as outputs and sets them to low.

        Raises:
            OSError: If I2C communication fails
        """
        self._bus = smbus2.SMBus(self._bus_num)

        # Configure all pins as outputs (0 = output)
        self._bus.write_byte_data(self._address, TCA9534ARegister.CONFIG, 0x00)

        # Set all outputs low
        self._output_cache = 0x00
        self._bus.write_byte_data(self._address, TCA9534ARegister.OUTPUT, self._output_cache)

    def close(self) -> None:
        """Close the I2C bus connection."""
        if self._bus is not None:
            self._bus.close()
            self._bus = None

    def _ensure_open(self) -> None:
        """Ensure the I2C bus is open."""
        if self._bus is None:
            raise RuntimeError("TCA9534A not initialized. Call init() first.")

    def set_pin(self, pin: TCA9534APin, value: bool) -> None:
        """Set a single pin output value.

        Args:
            pin: Pin to set
            value: True for high, False for low

        Raises:
            RuntimeError: If not initialized
            OSError: If I2C communication fails
        """
        self._ensure_open()

        if value:
            self._output_cache |= pin.mask
        else:
            self._output_cache &= ~pin.mask

        self._bus.write_byte_data(self._address, TCA9534ARegister.OUTPUT, self._output_cache)

    def get_pin(self, pin: TCA9534APin) -> bool:
        """Get the current output value of a pin.

        Note: This returns the cached output value, not the actual pin state.
        For input pins, use read_input() instead.

        Args:
            pin: Pin to read

        Returns:
            Current output value (True=high, False=low)
        """
        return (self._output_cache & pin.mask) != 0

    def set_pins(self, mask: int, values: int) -> None:
        """Set multiple pins at once using a mask.

        Args:
            mask: Bitmask of pins to modify
            values: Values to set for the masked pins

        Example:
            # Set P0 high and P2 low
            expander.set_pins(0x05, 0x01)
        """
        self._ensure_open()

        self._output_cache = (self._output_cache & ~mask) | (values & mask)
        self._bus.write_byte_data(self._address, TCA9534ARegister.OUTPUT, self._output_cache)

    def read_output(self) -> int:
        """Read the current output register value.

        Returns:
            Current output register value (0-255)
        """
        self._ensure_open()

        # Read from device to ensure cache is synchronized
        self._output_cache = self._bus.read_byte_data(self._address, TCA9534ARegister.OUTPUT)
        return self._output_cache

    def read_input(self) -> int:
        """Read the actual pin states from the input register.

        This reads the physical state of the pins, which may differ from
        the output register if pins are configured as inputs.

        Returns:
            Input register value (0-255)
        """
        self._ensure_open()
        return self._bus.read_byte_data(self._address, TCA9534ARegister.INPUT)

    def get_state(self) -> TCA9534AState:
        """Get the current state of all registers.

        Returns:
            TCA9534AState with output and config values
        """
        self._ensure_open()

        output = self._bus.read_byte_data(self._address, TCA9534ARegister.OUTPUT)
        config = self._bus.read_byte_data(self._address, TCA9534ARegister.CONFIG)
        self._output_cache = output

        return TCA9534AState(output=output, config=config)

    # Convenience methods for MTIB-specific functions

    def set_jlink_mux(self, swap: bool) -> None:
        """Set the J-Link multiplexer state.

        Args:
            swap: True to swap J-Link routing, False for normal
        """
        self.set_pin(TCA9534APin.JLINK_MUL, swap)

    def set_eeprom_write_protect(self, protect: bool) -> None:
        """Set the EEPROM write protect state.

        Args:
            protect: True to protect EEPROM, False to allow writes
        """
        self.set_pin(TCA9534APin.EEPROM_WP, protect)

    def set_motor_power(self, enable: bool) -> None:
        """Enable or disable motor power.

        Args:
            enable: True to enable motor power, False to disable
        """
        self.set_pin(TCA9534APin.VMM_EN, enable)

    def __enter__(self) -> TCA9534A:
        """Context manager entry."""
        self.init()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit."""
        self.close()

    def __del__(self) -> None:
        """Cleanup on deletion."""
        self.close()
