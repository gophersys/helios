"""
BME280 temperature, humidity, and pressure sensor driver.
Simplified implementation based on Adafruit BME280 library.
"""

import struct
import time
from typing import Optional, Tuple

from corekinect.utils import Logger

from .i2c import I2CDevice


class BME280:
    """BME280 sensor driver for temperature, humidity, and pressure readings."""

    # BME280 register addresses
    REGISTER_CHIPID = 0xD0
    REGISTER_SOFTRESET = 0xE0
    REGISTER_STATUS = 0xF3
    REGISTER_CONTROL = 0xF4
    REGISTER_CONTROLHUMID = 0xF2
    REGISTER_CONFIG = 0xF5
    REGISTER_TEMPDATA = 0xFA
    REGISTER_PRESSUREDATA = 0xF7
    REGISTER_HUMIDDATA = 0xFD

    # Expected chip ID
    CHIP_ID_BME280 = 0x60

    # Mode constants
    MODE_SLEEP = 0x00
    MODE_FORCE = 0x01
    MODE_NORMAL = 0x03

    def __init__(self, bus_number: int, device_address: int, logger: Logger = None):
        """
        Initialize BME280 sensor.

        Args:
            bus_number: I2C bus number
            device_address: I2C device address (0x76 or 0x77)
            logger: Logger instance
        """
        self.logger = logger
        self.i2c = I2CDevice(bus_number, device_address, logger)
        self._temp_calib = [0] * 3
        self._pressure_calib = [0] * 9
        self._humidity_calib = [0] * 6
        self._t_fine = None
        self._initialized = False
        self.sea_level_pressure = 1013.25

        if self.logger:
            self.logger.debug(f"BME280 initialized on bus {bus_number}, address 0x{device_address:02x}")

    def initialize(self) -> bool:
        """
        Initialize the BME280 sensor.

        Returns:
            True if initialization successful, False otherwise
        """
        try:
            # Check if sensor is responding
            if not self.i2c.ping():
                if self.logger:
                    self.logger.error("BME280 sensor not responding")
                return False

            # Check chip ID
            chip_id = self.i2c.read_register_uint8(self.REGISTER_CHIPID)
            if chip_id != self.CHIP_ID_BME280:
                if self.logger:
                    self.logger.error(f"Invalid chip ID: 0x{chip_id:02x}, expected 0x{self.CHIP_ID_BME280:02x}")
                return False

            if self.logger:
                self.logger.info(f"BME280 chip ID verified: 0x{chip_id:02x}")

            # Reset the device
            self.i2c.write_register_uint8(self.REGISTER_SOFTRESET, 0xB6)
            time.sleep(0.004)  # Wait for reset (datasheet says 2ms, using 4ms to be safe)

            # Read calibration data
            self._read_coefficients()

            # Set default configuration
            self._write_ctrl_meas()
            self._write_config()

            self._initialized = True
            if self.logger:
                self.logger.info("BME280 initialization successful")
            return True

        except Exception as e:
            if self.logger:
                self.logger.error(f"BME280 initialization failed: {e}")
            return False

    def _read_coefficients(self):
        """Read & save the calibration coefficients using struct.unpack like Adafruit."""
        try:
            # Read temperature and pressure calibration (24 bytes starting at 0x88)
            coeff = self.i2c.read_register(0x88, 24)
            coeff = list(struct.unpack("<HhhHhhhhhhhh", bytes(coeff)))
            coeff = [float(i) for i in coeff]
            self._temp_calib = coeff[:3]
            self._pressure_calib = coeff[3:]

            # Read humidity calibration
            self._humidity_calib = [0] * 6
            self._humidity_calib[0] = self.i2c.read_register_uint8(0xA1)  # H1
            coeff = self.i2c.read_register(0xE1, 7)  # H2-H6
            coeff = list(struct.unpack("<hBbBbb", bytes(coeff)))
            self._humidity_calib[1] = float(coeff[0])  # H2
            self._humidity_calib[2] = float(coeff[1])  # H3
            self._humidity_calib[3] = float((coeff[2] << 4) | (coeff[3] & 0xF))  # H4
            self._humidity_calib[4] = float((coeff[4] << 4) | (coeff[3] >> 4))  # H5
            self._humidity_calib[5] = float(coeff[5])  # H6

            if self.logger:
                self.logger.debug("BME280 calibration data read successfully")

        except Exception as e:
            if self.logger:
                self.logger.error(f"Error reading BME280 calibration data: {e}")
            raise

    def _write_ctrl_meas(self):
        """Write the values to the ctrl_meas and ctrl_hum registers."""
        # Set humidity oversampling (1x)
        self.i2c.write_register_uint8(self.REGISTER_CONTROLHUMID, 0x01)
        # Set temperature (1x), pressure (1x), and mode (forced)
        self.i2c.write_register_uint8(self.REGISTER_CONTROL, 0x25)

    def _write_config(self):
        """Write the value to the config register."""
        # Set filter (16) and standby time (125ms)
        self.i2c.write_register_uint8(self.REGISTER_CONFIG, 0xA0)

    def _get_status(self):
        """Get the value from the status register."""
        return self.i2c.read_register_uint8(self.REGISTER_STATUS)

    def _read_temperature(self):
        """Read temperature and calculate t_fine (internal method)."""
        if not self._initialized:
            if self.logger:
                self.logger.error("BME280 not initialized")
            return

        try:
            # Trigger measurement in forced mode
            self.i2c.write_register_uint8(self.REGISTER_CONTROL, 0x25)  # forced mode
            # Wait for conversion to complete
            while self._get_status() & 0x08:
                time.sleep(0.002)

            # Read raw temperature data (24 bits)
            raw_temperature = self._read24(self.REGISTER_TEMPDATA) / 16  # lowest 4 bits get dropped

            # Temperature compensation calculation (Adafruit algorithm)
            var1 = (raw_temperature / 16384.0 - self._temp_calib[0] / 1024.0) * self._temp_calib[1]
            var2 = (
                (raw_temperature / 131072.0 - self._temp_calib[0] / 8192.0)
                * (raw_temperature / 131072.0 - self._temp_calib[0] / 8192.0)
            ) * self._temp_calib[2]

            self._t_fine = int(var1 + var2)

        except Exception as e:
            if self.logger:
                self.logger.error(f"Error reading temperature: {e}")
            raise

    def read_temperature(self) -> Optional[float]:
        """
        Read temperature from the sensor.

        Returns:
            Temperature in Celsius, or None if error
        """
        try:
            self._read_temperature()
            return self._t_fine / 5120.0
        except Exception as e:
            if self.logger:
                self.logger.error(f"Error reading temperature: {e}")
            return None

    def _read24(self, register: int) -> float:
        """Read an unsigned 24-bit value as a floating point and return it."""
        ret = 0.0
        data = self.i2c.read_register(register, 3)
        for b in data:
            ret *= 256.0
            ret += float(b & 0xFF)
        return ret

    def read_pressure(self) -> Optional[float]:
        """
        Read pressure from the sensor.

        Returns:
            Pressure in hectoPascals, or None if error
        """
        if not self._initialized:
            if self.logger:
                self.logger.error("BME280 not initialized")
            return None

        try:
            self._read_temperature()

            # Read raw pressure data (24 bits)
            adc = self._read24(0xF7) / 16  # lowest 4 bits get dropped

            # Pressure compensation calculation (Adafruit algorithm)
            var1 = float(self._t_fine) / 2.0 - 64000.0
            var2 = var1 * var1 * self._pressure_calib[5] / 32768.0
            var2 = var2 + var1 * self._pressure_calib[4] * 2.0
            var2 = var2 / 4.0 + self._pressure_calib[3] * 65536.0
            var3 = self._pressure_calib[2] * var1 * var1 / 524288.0
            var1 = (var3 + self._pressure_calib[1] * var1) / 524288.0
            var1 = (1.0 + var1 / 32768.0) * self._pressure_calib[0]

            if not var1:  # avoid exception caused by division by zero
                if self.logger:
                    self.logger.error("Invalid pressure calculation result")
                return None

            pressure = 1048576.0 - adc
            pressure = ((pressure - var2 / 4096.0) * 6250.0) / var1
            var1 = self._pressure_calib[8] * pressure * pressure / 2147483648.0
            var2 = pressure * self._pressure_calib[7] / 32768.0
            pressure = pressure + (var1 + var2 + self._pressure_calib[6]) / 16.0

            pressure /= 100  # Convert to hectoPascals
            return pressure

        except Exception as e:
            if self.logger:
                self.logger.error(f"Error reading pressure: {e}")
            return None

    def read_humidity(self) -> Optional[float]:
        """
        Read humidity from the sensor.

        Returns:
            Humidity in %RH, or None if error
        """
        if not self._initialized:
            if self.logger:
                self.logger.error("BME280 not initialized")
            return None

        try:
            self._read_temperature()

            # Read raw humidity data (16 bits)
            hum = self.i2c.read_register(0xFD, 2)  # BME280_REGISTER_HUMIDDATA
            adc = float(hum[0] << 8 | hum[1])

            # Humidity compensation calculation (Adafruit algorithm)
            var1 = float(self._t_fine) - 76800.0
            var2 = self._humidity_calib[3] * 64.0 + (self._humidity_calib[4] / 16384.0) * var1
            var3 = adc - var2
            var4 = self._humidity_calib[1] / 65536.0
            var5 = 1.0 + (self._humidity_calib[2] / 67108864.0) * var1
            var6 = 1.0 + (self._humidity_calib[5] / 67108864.0) * var1 * var5
            var6 = var3 * var4 * (var5 * var6)
            humidity = var6 * (1.0 - self._humidity_calib[0] * var6 / 524288.0)

            # Clamp humidity to valid range
            if humidity > 100:
                humidity = 100
            if humidity < 0:
                humidity = 0

            return humidity

        except Exception as e:
            if self.logger:
                self.logger.error(f"Error reading humidity: {e}")
            return None

    def read_all(self) -> Tuple[Optional[float], Optional[float], Optional[float]]:
        """
        Read all sensor values (temperature, pressure, humidity).

        Returns:
            Tuple of (temperature_celsius, pressure_hectopascals, humidity_percent)
        """
        temperature = self.read_temperature()
        pressure = self.read_pressure()
        humidity = self.read_humidity()

        return temperature, pressure, humidity

    def calculate_altitude(self, sea_level_pressure: float = None) -> Optional[float]:
        """
        Calculate altitude from pressure reading.

        Args:
            sea_level_pressure: Sea level pressure in hPa (uses self.sea_level_pressure if None)

        Returns:
            Altitude in meters, or None if error
        """
        if sea_level_pressure is None:
            sea_level_pressure = self.sea_level_pressure

        pressure = self.read_pressure()
        if pressure is None:
            return None

        # Calculate altitude using barometric formula
        altitude = 44330 * (1.0 - (pressure / sea_level_pressure) ** 0.1903)

        if self.logger:
            self.logger.debug(f"BME280 altitude: {altitude:.2f}m")

        return altitude