"""TCA9534A I2C GPIO expander driver.

The TCA9534A is an 8-bit I/O expander for I2C bus. It provides general-purpose
remote I/O expansion via the I2C interface.

This driver is only used on REV 1.2 boards where the TCA9534A controls:
- P0: JLINK_MUL - J-Link multiplexer select
- P1: EEPROM_WP - EEPROM write protect
- P2: VMM_EN - Motor power enable
- P3-P7: Reserved
"""

from __future__ import annotations

import threading
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
    """Pin definitions for the TCA9534A on MTIB REV 1.2."""

    JLINK_MUL = 0  # P0: J-Link multiplexer select (0=nRF9151, 1=nRF52840) — verified empirically
    EEPROM_WP = 1  # P1: EEPROM write protect (0=enabled, 1=protected)
    VMM_EN = 2  # P2: Motor power enable (0=off, 1=on)

    @property
    def mask(self) -> int:
        return 1 << self.value


class TCA9534A:
    """Driver for the TCA9534A I2C GPIO expander on MTIB REV 1.2."""

    DEFAULT_ADDRESS = 0x38
    DEFAULT_BUS = 3  # /dev/i2c-3 on Verdin iMX8MM

    def __init__(self, bus_num: int = DEFAULT_BUS, address: int = DEFAULT_ADDRESS):
        self._bus_num = bus_num
        self._address = address
        self._bus: Optional[smbus2.SMBus] = None
        self._output_cache: int = 0x00
        self._lock = threading.Lock()

    def init(self) -> None:
        """Initialize: configure all pins as outputs, set all low.

        Uses force=True to bypass kernel gpio-pca953x driver claim.
        Raises OSError if I2C communication fails.
        """
        self._bus = smbus2.SMBus(self._bus_num)
        self._bus.write_byte_data(self._address, TCA9534ARegister.CONFIG, 0x00, force=True)
        self._output_cache = 0x00
        self._bus.write_byte_data(self._address, TCA9534ARegister.OUTPUT, self._output_cache, force=True)

    def close(self) -> None:
        if self._bus is not None:
            self._bus.close()
            self._bus = None

    def _ensure_open(self) -> None:
        if self._bus is None:
            raise RuntimeError("TCA9534A not initialized. Call init() first.")

    def set_pin(self, pin: TCA9534APin, value: bool) -> None:
        """Set a single pin output value."""
        self._ensure_open()
        with self._lock:
            if value:
                self._output_cache |= pin.mask
            else:
                self._output_cache &= ~pin.mask
            self._bus.write_byte_data(self._address, TCA9534ARegister.OUTPUT, self._output_cache, force=True)

    def get_pin(self, pin: TCA9534APin) -> bool:
        """Get the cached output value of a pin."""
        return (self._output_cache & pin.mask) != 0

    def set_jlink_mux(self, swap: bool) -> None:
        """Set J-Link mux: swap=True → nRF52840 (P0=HIGH), swap=False → nRF9151 (P0=LOW)."""
        self.set_pin(TCA9534APin.JLINK_MUL, swap)

    def set_eeprom_write_protect(self, protect: bool) -> None:
        self.set_pin(TCA9534APin.EEPROM_WP, protect)

    def set_motor_power(self, enable: bool) -> None:
        self.set_pin(TCA9534APin.VMM_EN, enable)

    def __enter__(self) -> TCA9534A:
        self.init()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    def __del__(self) -> None:
        self.close()
