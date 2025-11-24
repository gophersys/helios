"""
I2C communication library for raw register reads and writes.
Provides low-level I2C operations for sensor communication.
"""

import os
import struct
import time
from typing import Optional, List
from corekinect.utils import Logger


class I2CDevice:
    """Low-level I2C device communication class."""

    def __init__(self, bus_number: int, device_address: int, logger: Logger = None):
        """
        Initialize I2C device.

        Args:
            bus_number: I2C bus number (e.g., 3 for /dev/i2c-3)
            device_address: 7-bit I2C device address (e.g., 0x77 for BME280)
            logger: Logger instance for debugging
        """
        self.bus_number = bus_number
        self.device_address = device_address
        self.logger = logger
        self.device_path = f"/dev/i2c-{bus_number}"

        # Check if I2C device exists
        if not os.path.exists(self.device_path):
            raise FileNotFoundError(f"I2C device {self.device_path} not found")

        if self.logger:
            self.logger.debug(f"I2C device initialized: {self.device_path}, address 0x{device_address:02x}")

    def read_register(self, register: int, length: int = 1) -> bytes:
        """
        Read data from a register.

        Args:
            register: Register address to read from
            length: Number of bytes to read

        Returns:
            Raw bytes read from the register
        """
        try:
            if length == 1:
                # Single byte read
                cmd = f"i2cget -y {self.bus_number} 0x{self.device_address:02x} 0x{register:02x}"
                result = os.popen(cmd).read().strip()

                if not result:
                    raise IOError(f"No data received from register 0x{register:02x}")

                return bytes([int(result, 16)])
            else:
                # Multi-byte read - read each byte individually
                data = []
                for i in range(length):
                    cmd = f"i2cget -y {self.bus_number} 0x{self.device_address:02x} 0x{register + i:02x}"
                    result = os.popen(cmd).read().strip()

                    if not result:
                        raise IOError(f"No data received from register 0x{register + i:02x}")

                    data.append(int(result, 16))

                return bytes(data)

        except Exception as e:
            if self.logger:
                self.logger.error(f"Error reading register 0x{register:02x}: {e}")
            raise

    def write_register(self, register: int, data: bytes) -> None:
        """
        Write data to a register.

        Args:
            register: Register address to write to
            data: Data bytes to write
        """
        try:
            # Convert data to hex string
            data_hex = " ".join([f"0x{b:02x}" for b in data])
            cmd = f"i2cset -y {self.bus_number} 0x{self.device_address:02x} 0x{register:02x} {data_hex}"

            result = os.popen(cmd).read().strip()

            if result and "Error" in result:
                raise IOError(f"i2cset error: {result}")

        except Exception as e:
            if self.logger:
                self.logger.error(f"Error writing to register 0x{register:02x}: {e}")
            raise

    def read_register_uint8(self, register: int) -> int:
        """Read a single 8-bit unsigned integer from a register."""
        data = self.read_register(register, 1)
        return data[0]

    def read_register_uint16(self, register: int, little_endian: bool = True) -> int:
        """Read a 16-bit unsigned integer from consecutive registers."""
        data = self.read_register(register, 2)
        if little_endian:
            return data[0] | (data[1] << 8)
        else:
            return (data[0] << 8) | data[1]

    def read_register_int16(self, register: int, little_endian: bool = True) -> int:
        """Read a 16-bit signed integer from consecutive registers."""
        data = self.read_register(register, 2)
        if little_endian:
            value = data[0] | (data[1] << 8)
        else:
            value = (data[0] << 8) | data[1]

        # Convert to signed
        if value >= 0x8000:
            value -= 0x10000
        return value

    def read_register_uint24(self, register: int) -> int:
        """Read a 24-bit unsigned integer from consecutive registers."""
        data = self.read_register(register, 3)
        return data[0] | (data[1] << 8) | (data[2] << 16)

    def write_register_uint8(self, register: int, value: int) -> None:
        """Write an 8-bit unsigned integer to a register."""
        self.write_register(register, bytes([value & 0xFF]))

    def ping(self) -> bool:
        """
        Ping the device to check if it's responding.

        Returns:
            True if device responds, False otherwise
        """
        try:
            # Try to read any register to test connectivity
            # Use a simple register that most devices have
            self.read_register_uint8(0x00)
            return True
        except:
            return False
