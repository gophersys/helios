"""LIS2DE12 accelerometer driver.

Reads acceleration data from the LIS2DE12 via Linux IIO sysfs interface.
"""

import glob
import os
from typing import Optional

from corekinect.utils import Logger


class LIS2DE12:
    """Driver for LIS2DE12 accelerometer via IIO sysfs."""

    def __init__(self, logger: Logger):
        self.logger = logger
        self._device_path: Optional[str] = None
        self._scale_x: float = 1.0
        self._scale_y: float = 1.0
        self._scale_z: float = 1.0

        self._discover_device()

    @property
    def available(self) -> bool:
        """Whether the accelerometer device was found and initialized."""
        return self._device_path is not None

    def _discover_device(self):
        """Find the lis2de12 IIO device and initialize scale factors."""
        try:
            device_pattern = "/sys/bus/iio/devices/iio:device*/name"
            device_files = glob.glob(device_pattern)
            self.logger.info(f"Scanning {len(device_files)} IIO devices for lis2de12")

            for device_file in device_files:
                try:
                    with open(device_file, "r") as f:
                        device_name = f.read().strip()
                        if device_name == "lis2de12":
                            device_path = os.path.dirname(device_file)
                            self._device_path = device_path

                            # Read scale factors
                            self._scale_x = self._read_scale_factor(f"{device_path}/in_accel_x_scale")
                            self._scale_y = self._read_scale_factor(f"{device_path}/in_accel_y_scale")
                            self._scale_z = self._read_scale_factor(f"{device_path}/in_accel_z_scale")

                            # Set sampling frequency to 25 Hz for faster reads
                            self._set_sampling_frequency(device_path, 25)

                            self.logger.info(f"Accelerometer initialized: {device_path}")
                            self.logger.info(
                                f"Scale factors - X: {self._scale_x}, Y: {self._scale_y}, Z: {self._scale_z}"
                            )
                            return
                except (IOError, OSError) as e:
                    self.logger.warning(f"Error reading device file {device_file}: {e}")
                    continue

            self.logger.error("lis2de12 accelerometer device not found")

        except Exception as e:
            self.logger.error(f"Error initializing accelerometer: {e}")

    def _read_scale_factor(self, scale_file_path: str) -> float:
        """Read scale factor from IIO device file."""
        try:
            with open(scale_file_path, "r") as f:
                return float(f.read().strip())
        except (IOError, OSError, ValueError) as e:
            self.logger.warning(f"Error reading scale factor from {scale_file_path}: {e}")
            return 1.0

    def _set_sampling_frequency(self, device_path: str, frequency_hz: int):
        """Set the sampling frequency for the accelerometer."""
        try:
            sampling_freq_file = f"{device_path}/sampling_frequency"
            with open(sampling_freq_file, "w") as f:
                f.write(str(frequency_hz))
            self.logger.info(f"Set accelerometer sampling frequency to {frequency_hz} Hz")
        except (IOError, OSError) as e:
            self.logger.warning(f"Error setting sampling frequency to {frequency_hz} Hz: {e}")

    def _read_raw_value(self, raw_file_path: str) -> int:
        """Read raw value from IIO device file."""
        if not os.path.exists(raw_file_path):
            raise IOError(f"File does not exist: {raw_file_path}")

        if not os.access(raw_file_path, os.R_OK):
            raise IOError(f"File is not readable: {raw_file_path}")

        with open(raw_file_path, "r") as f:
            data = f.read().strip()
            if not data:
                raise IOError(f"No data read from {raw_file_path}")
            return int(data)

    def read(self) -> tuple[Optional[str], float, float, float]:
        """Read acceleration values from all three axes.

        Returns:
            Tuple of (error, x_g, y_g, z_g). Error is None on success.
            Values are in g (gravitational acceleration units).
        """
        if self._device_path is None:
            return "Accelerometer device not initialized", 0.0, 0.0, 0.0

        try:
            raw_x = self._read_raw_value(f"{self._device_path}/in_accel_x_raw")
            raw_y = self._read_raw_value(f"{self._device_path}/in_accel_y_raw")
            raw_z = self._read_raw_value(f"{self._device_path}/in_accel_z_raw")

            x_g = raw_x * self._scale_x
            y_g = raw_y * self._scale_y
            z_g = raw_z * self._scale_z

            return None, x_g, y_g, z_g
        except Exception as e:
            self.logger.error(f"Error reading accelerometer: {e}")
            return str(e), 0.0, 0.0, 0.0
