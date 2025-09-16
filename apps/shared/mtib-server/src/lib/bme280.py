"""
BME280 temperature, humidity, and pressure sensor driver.
Based on the Adafruit BME280 library but adapted for raw I2C communication.
"""

import time
from typing import Optional, Tuple
from corekinect.utils import Logger
from .i2c import I2CDevice


class BME280Calibration:
    """BME280 calibration data structure."""

    def __init__(self):
        # Temperature calibration
        self.dig_T1: int = 0
        self.dig_T2: int = 0
        self.dig_T3: int = 0

        # Pressure calibration
        self.dig_P1: int = 0
        self.dig_P2: int = 0
        self.dig_P3: int = 0
        self.dig_P4: int = 0
        self.dig_P5: int = 0
        self.dig_P6: int = 0
        self.dig_P7: int = 0
        self.dig_P8: int = 0
        self.dig_P9: int = 0

        # Humidity calibration
        self.dig_H1: int = 0
        self.dig_H2: int = 0
        self.dig_H3: int = 0
        self.dig_H4: int = 0
        self.dig_H5: int = 0
        self.dig_H6: int = 0


class BME280:
    """BME280 sensor driver for temperature, humidity, and pressure readings."""

    # BME280 register addresses
    REGISTER_CHIPID = 0xD0
    REGISTER_SOFTRESET = 0xE0
    REGISTER_STATUS = 0xF3
    REGISTER_CONTROL = 0xF4
    REGISTER_CONTROLHUMID = 0xF2
    REGISTER_CONFIG = 0xF5

    # Calibration registers
    REGISTER_DIG_T1 = 0x88
    REGISTER_DIG_T2 = 0x8A
    REGISTER_DIG_T3 = 0x8C
    REGISTER_DIG_P1 = 0x8E
    REGISTER_DIG_P2 = 0x90
    REGISTER_DIG_P3 = 0x92
    REGISTER_DIG_P4 = 0x94
    REGISTER_DIG_P5 = 0x96
    REGISTER_DIG_P6 = 0x98
    REGISTER_DIG_P7 = 0x9A
    REGISTER_DIG_P8 = 0x9C
    REGISTER_DIG_P9 = 0x9E
    REGISTER_DIG_H1 = 0xA1
    REGISTER_DIG_H2 = 0xE1
    REGISTER_DIG_H3 = 0xE3
    REGISTER_DIG_H4 = 0xE4
    REGISTER_DIG_H5 = 0xE5
    REGISTER_DIG_H6 = 0xE7

    # Data registers
    REGISTER_TEMPDATA = 0xFA
    REGISTER_PRESSUREDATA = 0xF7
    REGISTER_HUMIDDATA = 0xFD

    # Expected chip ID
    CHIP_ID_BME280 = 0x60

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
        self.calibration = BME280Calibration()
        self.t_fine = 0
        self.t_fine_adjust = 0
        self._initialized = False

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
            time.sleep(0.01)  # Wait for reset

            # Wait for calibration to complete
            while self._is_reading_calibration():
                time.sleep(0.01)

            # Read calibration data
            self._read_calibration()

            # Set default sampling configuration
            self._set_sampling()

            time.sleep(0.1)  # Wait for configuration to take effect

            self._initialized = True
            if self.logger:
                self.logger.info("BME280 initialization successful")
            return True

        except Exception as e:
            if self.logger:
                self.logger.error(f"BME280 initialization failed: {e}")
            return False

    def _is_reading_calibration(self) -> bool:
        """Check if the sensor is still reading calibration data."""
        status = self.i2c.read_register_uint8(self.REGISTER_STATUS)
        return (status & 0x01) != 0

    def _read_calibration(self):
        """Read calibration data from the sensor."""
        try:
            # Temperature calibration
            self.calibration.dig_T1 = self.i2c.read_register_uint16(self.REGISTER_DIG_T1, little_endian=True)
            self.calibration.dig_T2 = self.i2c.read_register_int16(self.REGISTER_DIG_T2, little_endian=True)
            self.calibration.dig_T3 = self.i2c.read_register_int16(self.REGISTER_DIG_T3, little_endian=True)

            # Pressure calibration
            self.calibration.dig_P1 = self.i2c.read_register_uint16(self.REGISTER_DIG_P1, little_endian=True)
            self.calibration.dig_P2 = self.i2c.read_register_int16(self.REGISTER_DIG_P2, little_endian=True)
            self.calibration.dig_P3 = self.i2c.read_register_int16(self.REGISTER_DIG_P3, little_endian=True)
            self.calibration.dig_P4 = self.i2c.read_register_int16(self.REGISTER_DIG_P4, little_endian=True)
            self.calibration.dig_P5 = self.i2c.read_register_int16(self.REGISTER_DIG_P5, little_endian=True)
            self.calibration.dig_P6 = self.i2c.read_register_int16(self.REGISTER_DIG_P6, little_endian=True)
            self.calibration.dig_P7 = self.i2c.read_register_int16(self.REGISTER_DIG_P7, little_endian=True)
            self.calibration.dig_P8 = self.i2c.read_register_int16(self.REGISTER_DIG_P8, little_endian=True)
            self.calibration.dig_P9 = self.i2c.read_register_int16(self.REGISTER_DIG_P9, little_endian=True)

            # Humidity calibration
            self.calibration.dig_H1 = self.i2c.read_register_uint8(self.REGISTER_DIG_H1)
            self.calibration.dig_H2 = self.i2c.read_register_int16(self.REGISTER_DIG_H2, little_endian=True)
            self.calibration.dig_H3 = self.i2c.read_register_uint8(self.REGISTER_DIG_H3)

            # H4 and H5 are packed in a special way
            h4_h5_data = self.i2c.read_register(self.REGISTER_DIG_H4, 2)
            self.calibration.dig_H4 = (h4_h5_data[0] << 4) | (h4_h5_data[1] & 0x0F)
            if self.calibration.dig_H4 >= 0x800:
                self.calibration.dig_H4 -= 0x1000

            h5_h6_data = self.i2c.read_register(self.REGISTER_DIG_H5, 2)
            self.calibration.dig_H5 = (h5_h6_data[1] << 4) | (h5_h6_data[0] >> 4)
            if self.calibration.dig_H5 >= 0x800:
                self.calibration.dig_H5 -= 0x1000

            self.calibration.dig_H6 = self.i2c.read_register_uint8(self.REGISTER_DIG_H6)
            if self.calibration.dig_H6 >= 0x80:
                self.calibration.dig_H6 -= 0x100

            if self.logger:
                self.logger.debug("BME280 calibration data read successfully")
                self.logger.debug(
                    f"T1={self.calibration.dig_T1}, T2={self.calibration.dig_T2}, T3={self.calibration.dig_T3}"
                )
                self.logger.debug(
                    f"P1={self.calibration.dig_P1}, P2={self.calibration.dig_P2}, P3={self.calibration.dig_P3}"
                )
                self.logger.debug(
                    f"P4={self.calibration.dig_P4}, P5={self.calibration.dig_P5}, P6={self.calibration.dig_P6}"
                )
                self.logger.debug(
                    f"P7={self.calibration.dig_P7}, P8={self.calibration.dig_P8}, P9={self.calibration.dig_P9}"
                )
                self.logger.debug(
                    f"H1={self.calibration.dig_H1}, H2={self.calibration.dig_H2}, H3={self.calibration.dig_H3}"
                )

        except Exception as e:
            if self.logger:
                self.logger.error(f"Error reading BME280 calibration data: {e}")
            raise

    def _set_sampling(self):
        """Set default sampling configuration."""
        # Set humidity oversampling
        self.i2c.write_register_uint8(self.REGISTER_CONTROLHUMID, 0x01)  # 1x oversampling

        # Set temperature and pressure oversampling, and mode
        # Use forced mode (0x25) instead of normal mode for better control
        self.i2c.write_register_uint8(self.REGISTER_CONTROL, 0x25)  # 1x oversampling, forced mode

        # Set filter and standby time
        self.i2c.write_register_uint8(self.REGISTER_CONFIG, 0xA0)  # 16 filter, 1000ms standby

    def _trigger_measurement(self):
        """Trigger a measurement in forced mode."""
        # Set forced mode to trigger measurement
        self.i2c.write_register_uint8(self.REGISTER_CONTROL, 0x25)  # 1x oversampling, forced mode
        time.sleep(0.1)  # Wait longer for measurement to complete

    def read_temperature(self) -> Optional[float]:
        """
        Read temperature from the sensor.

        Returns:
            Temperature in Celsius, or None if error
        """
        if not self._initialized:
            if self.logger:
                self.logger.error("BME280 not initialized")
            return None

        try:
            # Trigger measurement in forced mode
            self._trigger_measurement()

            # Read raw temperature data (24 bits)
            adc_T = self.i2c.read_register_uint24(self.REGISTER_TEMPDATA)
            adc_T >>= 4  # Remove unused bits

            if self.logger:
                self.logger.debug(f"BME280 raw temperature ADC: {adc_T}")

            # Temperature compensation calculation
            var1 = (adc_T / 8) - (self.calibration.dig_T1 * 2)
            var1 = (var1 * self.calibration.dig_T2) / 2048
            var2 = (adc_T / 16) - self.calibration.dig_T1
            var2 = (((var2 * var2) / 4096) * self.calibration.dig_T3) / 16384

            self.t_fine = var1 + var2 + self.t_fine_adjust

            # Convert to temperature in Celsius
            T = (self.t_fine * 5 + 128) / 256
            temperature = T / 100.0

            if self.logger:
                self.logger.debug(
                    f"BME280 temperature calculation - var1: {var1}, var2: {var2}, t_fine: {self.t_fine}"
                )
                self.logger.debug(f"BME280 temperature: {temperature:.2f}°C")

            return temperature

        except Exception as e:
            if self.logger:
                self.logger.error(f"Error reading temperature: {e}")
            return None

    def read_pressure(self) -> Optional[float]:
        """
        Read pressure from the sensor.

        Returns:
            Pressure in Pascal, or None if error
        """
        if not self._initialized:
            if self.logger:
                self.logger.error("BME280 not initialized")
            return None

        try:
            # Read raw pressure data (24 bits) - no need to trigger new measurement
            adc_P = self.i2c.read_register_uint24(self.REGISTER_PRESSUREDATA)
            adc_P >>= 4  # Remove unused bits

            if self.logger:
                self.logger.debug(f"BME280 raw pressure ADC: {adc_P}")

            # Pressure compensation calculation (using 64-bit integers)
            var1 = int(self.t_fine) - 128000
            var2 = int(var1) * int(var1) * int(self.calibration.dig_P6)
            var2 = var2 + ((int(var1) * int(self.calibration.dig_P5)) * 131072)
            var2 = var2 + (int(self.calibration.dig_P4) * 34359738368)
            var1 = ((int(var1) * int(var1) * int(self.calibration.dig_P3)) // 256) + (
                (int(var1) * int(self.calibration.dig_P2)) * 4096
            )
            var3 = 140737488355328
            var1 = (var3 + var1) * int(self.calibration.dig_P1) // 8589934592

            if var1 == 0:
                return 0  # Avoid division by zero

            var4 = 1048576 - int(adc_P)
            var4 = (((var4 * 2147483648) - var2) * 3125) // var1
            var1 = (int(self.calibration.dig_P9) * (var4 // 8192) * (var4 // 8192)) // 33554432
            var2 = (int(self.calibration.dig_P8) * var4) // 524288
            var4 = ((var4 + var1 + var2) // 256) + (int(self.calibration.dig_P7) * 16)

            pressure = var4 / 256.0

            if self.logger:
                self.logger.debug(
                    f"BME280 pressure calculation - var1: {var1}, var2: {var2}, var3: {var3}, var4: {var4}"
                )
                self.logger.debug(f"BME280 pressure: {pressure:.2f} Pa")

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
            # Read raw humidity data (16 bits) - no need to trigger new measurement
            adc_H = self.i2c.read_register_uint16(self.REGISTER_HUMIDDATA, little_endian=False)

            if self.logger:
                self.logger.debug(f"BME280 raw humidity ADC: {adc_H}")

            # Humidity compensation calculation
            var1 = self.t_fine - 76800
            var2 = adc_H * 16384
            var3 = self.calibration.dig_H4 * 1048576
            var4 = self.calibration.dig_H5 * var1
            var5 = (((var2 - var3) - var4) + 16384) / 32768
            var2 = (var1 * self.calibration.dig_H6) / 1024
            var3 = (var1 * self.calibration.dig_H3) / 2048
            var4 = ((var2 * (var3 + 32768)) / 1024) + 2097152
            var2 = ((var4 * self.calibration.dig_H2) + 8192) / 16384
            var3 = var5 * var2
            var4 = ((var3 / 32768) * (var3 / 32768)) / 128
            var5 = var3 - ((var4 * self.calibration.dig_H1) / 16)
            var5 = max(0, min(var5, 419430400))  # Clamp to valid range

            humidity = var5 / 4096.0

            if self.logger:
                self.logger.debug(f"BME280 humidity: {humidity:.2f}%RH")

            return humidity

        except Exception as e:
            if self.logger:
                self.logger.error(f"Error reading humidity: {e}")
            return None

    def read_all(self) -> Tuple[Optional[float], Optional[float], Optional[float]]:
        """
        Read all sensor values (temperature, pressure, humidity).

        Returns:
            Tuple of (temperature_celsius, pressure_pascal, humidity_percent)
        """
        # Read temperature first to get t_fine
        temperature = self.read_temperature()
        if temperature is None:
            return None, None, None

        # Read pressure and humidity (they will use the t_fine from temperature reading)
        pressure = self.read_pressure()
        humidity = self.read_humidity()

        return temperature, pressure, humidity

    def calculate_altitude(self, sea_level_pressure: float = 1013.25) -> Optional[float]:
        """
        Calculate altitude from pressure reading.

        Args:
            sea_level_pressure: Sea level pressure in hPa

        Returns:
            Altitude in meters, or None if error
        """
        pressure = self.read_pressure()
        if pressure is None:
            return None

        # Convert Pa to hPa
        atmospheric_pressure = pressure / 100.0

        # Calculate altitude using barometric formula
        altitude = 44330.0 * (1.0 - (atmospheric_pressure / sea_level_pressure) ** 0.1903)

        if self.logger:
            self.logger.debug(f"BME280 altitude: {altitude:.2f}m")

        return altitude
