"""BME280 sensor reader via Linux IIO (Industrial I/O) sysfs interface.

When the kernel's bmp280 driver binds to the BME280 (device tree), the sensor
is exposed at /sys/bus/iio/devices/iio:deviceN/. This reader uses sysfs instead
of raw I2C, avoiding conflicts with the kernel driver.

IIO channels:
  in_temp_input             → millidegrees Celsius
  in_humidityrelative_input → milli-percent RH
  in_pressure_input         → kiloPascals
"""

import glob
import os
from typing import Optional, Tuple

from corekinect.utils import Logger


class BME280Iio:
    """BME280 sensor reader using the kernel IIO interface."""

    def __init__(self, iio_path: str, logger: Logger = None):
        self.logger = logger
        self._path = iio_path
        self.sea_level_pressure = 1013.25

    @classmethod
    def find(cls, logger: Logger = None) -> Optional["BME280Iio"]:
        """Scan IIO devices for a BME280/BMP280 and return an instance."""
        for dev_path in sorted(glob.glob("/sys/bus/iio/devices/iio:device*")):
            name_file = os.path.join(dev_path, "name")
            try:
                with open(name_file) as f:
                    name = f.read().strip()
            except OSError:
                continue
            if name in ("bme280", "bmp280"):
                if logger:
                    logger.info("BME280 found via IIO at %s", dev_path)
                return cls(dev_path, logger)
        return None

    def _read_channel(self, channel: str) -> Optional[float]:
        """Read a single IIO channel value from sysfs."""
        path = os.path.join(self._path, channel)
        try:
            with open(path) as f:
                return float(f.read().strip())
        except (OSError, ValueError) as e:
            if self.logger:
                self.logger.debug("IIO read failed for %s: %s", channel, e)
            return None

    def read_temperature(self) -> Optional[float]:
        """Read temperature in Celsius."""
        raw = self._read_channel("in_temp_input")
        return raw / 1000.0 if raw is not None else None

    def read_pressure(self) -> Optional[float]:
        """Read pressure in hectoPascals."""
        raw = self._read_channel("in_pressure_input")
        return raw * 10.0 if raw is not None else None  # kPa → hPa

    def read_humidity(self) -> Optional[float]:
        """Read relative humidity in percent."""
        raw = self._read_channel("in_humidityrelative_input")
        return raw / 1000.0 if raw is not None else None

    def read_all(self) -> Tuple[Optional[float], Optional[float], Optional[float]]:
        """Read all sensor values (temperature, pressure, humidity)."""
        return self.read_temperature(), self.read_pressure(), self.read_humidity()

    def calculate_altitude(self, sea_level_pressure: float = None) -> Optional[float]:
        """Calculate altitude from pressure using the barometric formula."""
        if sea_level_pressure is None:
            sea_level_pressure = self.sea_level_pressure
        pressure = self.read_pressure()
        if pressure is None:
            return None
        return 44330.0 * (1.0 - (pressure / sea_level_pressure) ** 0.1903)
