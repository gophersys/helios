"""Thread-safe I2C bus wrapper.

Single instance shared across all I2C drivers (MCP4017, TCA9534A, BME280).
Sysfs-based drivers (INA219, ADS1015, LIS2DE12) don't need this — the kernel
handles their I2C access.
"""

import threading

import smbus2


class I2CBus:
    """Thread-safe wrapper around smbus2.SMBus."""

    def __init__(self, bus_num: int = 3):
        self._bus = smbus2.SMBus(bus_num)
        self._lock = threading.Lock()

    def read_byte(self, addr: int) -> int:
        with self._lock:
            return self._bus.read_byte(addr)

    def write_byte(self, addr: int, value: int) -> None:
        with self._lock:
            self._bus.write_byte(addr, value)

    def read_byte_data(self, addr: int, register: int, force: bool = False) -> int:
        with self._lock:
            return self._bus.read_byte_data(addr, register, force=force)

    def write_byte_data(self, addr: int, register: int, value: int, force: bool = False) -> None:
        with self._lock:
            self._bus.write_byte_data(addr, register, value, force=force)

    def read_i2c_block_data(self, addr: int, register: int, length: int, force: bool = False) -> list:
        with self._lock:
            return self._bus.read_i2c_block_data(addr, register, length, force=force)

    def close(self):
        self._bus.close()
