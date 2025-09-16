import grpc
import os
import glob
import time
from corekinect.utils import Logger
from src.shared.types import *
from src.lib.bme280 import BME280


class SensorsHandler:
    def __init__(self, logger: Logger):
        self.logger = logger
        self.accel_device_path = None
        self.accel_scale_x = None
        self.accel_scale_y = None
        self.accel_scale_z = None
        self.bme280 = None
        self._init_accelerometer()
        self._init_bme280()

    def _init_accelerometer(self):
        """Initialize accelerometer by finding the lis2de12 device and reading scale factors."""
        init_start = time.time()
        try:
            # Find the lis2de12 device by checking device names
            device_pattern = "/sys/bus/iio/devices/iio:device*/name"
            device_files = glob.glob(device_pattern)
            self.logger.info(f"Found {len(device_files)} IIO devices in {time.time() - init_start:.3f}s")

            for device_file in device_files:
                try:
                    with open(device_file, "r") as f:
                        device_name = f.read().strip()
                        if device_name == "lis2de12":
                            # Extract device path (e.g., /sys/bus/iio/devices/iio:device4)
                            device_path = os.path.dirname(device_file)
                            self.accel_device_path = device_path

                            # Read scale factors
                            self.accel_scale_x = self._read_scale_factor(f"{device_path}/in_accel_x_scale")
                            self.accel_scale_y = self._read_scale_factor(f"{device_path}/in_accel_y_scale")
                            self.accel_scale_z = self._read_scale_factor(f"{device_path}/in_accel_z_scale")

                            # Set sampling frequency to 25 Hz for faster reads
                            self._set_sampling_frequency(device_path, 25)

                            init_time = time.time() - init_start
                            self.logger.info(f"Accelerometer initialized: {device_path} (took {init_time:.3f}s)")
                            self.logger.info(
                                f"Scale factors - X: {self.accel_scale_x}, Y: {self.accel_scale_y}, Z: {self.accel_scale_z}"
                            )
                            return
                except (IOError, OSError) as e:
                    self.logger.warning(f"Error reading device file {device_file}: {e}")
                    continue

            self.logger.error("lis2de12 accelerometer device not found")

        except Exception as e:
            self.logger.error(f"Error initializing accelerometer: {e}")

    def _init_bme280(self):
        """Initialize BME280 sensor for altimeter readings."""
        init_start = time.time()
        try:
            # Try both common BME280 addresses
            for address in [0x77, 0x76]:
                try:
                    self.bme280 = BME280(bus_number=3, device_address=address, logger=self.logger)
                    if self.bme280.initialize():
                        init_time = time.time() - init_start
                        self.logger.info(f"BME280 initialized at address 0x{address:02x} (took {init_time:.3f}s)")
                        return
                    else:
                        self.bme280 = None
                except Exception as e:
                    self.logger.debug(f"BME280 at address 0x{address:02x} not available: {e}")
                    continue

            self.logger.warning("BME280 sensor not found on I2C bus 3")

        except Exception as e:
            self.logger.error(f"Error initializing BME280: {e}")

    def _read_scale_factor(self, scale_file_path):
        """Read scale factor from IIO device file."""
        try:
            with open(scale_file_path, "r") as f:
                return float(f.read().strip())
        except (IOError, OSError, ValueError) as e:
            self.logger.warning(f"Error reading scale factor from {scale_file_path}: {e}")
            return 1.0  # Default scale factor

    def _set_sampling_frequency(self, device_path, frequency_hz):
        """Set the sampling frequency for the accelerometer."""
        try:
            sampling_freq_file = f"{device_path}/sampling_frequency"
            with open(sampling_freq_file, "w") as f:
                f.write(str(frequency_hz))
            self.logger.info(f"Set accelerometer sampling frequency to {frequency_hz} Hz")
        except (IOError, OSError) as e:
            self.logger.warning(f"Error setting sampling frequency to {frequency_hz} Hz: {e}")

    def read_altimeter(self, request: Empty, context: grpc.ServicerContext) -> AltimeterReadResponse:
        """Read altimeter sensor data from BME280."""
        start_time = time.time()
        self.logger.info("AltimeterRead request received")

        if self.bme280 is None:
            return AltimeterReadResponse(
                success=False,
                message="BME280 sensor not initialized",
                temperature_f=0.0,
                pressure_hg=0.0,
                altitude_ft=0.0,
            )

        try:
            # Read all sensor values
            temperature_c, pressure_pa, humidity_rh = self.bme280.read_all()

            if temperature_c is None or pressure_pa is None:
                return AltimeterReadResponse(
                    success=False,
                    message="Failed to read sensor data",
                    temperature_f=0.0,
                    pressure_hg=0.0,
                    altitude_ft=0.0,
                )

            # Convert temperature from Celsius to Fahrenheit
            temperature_f = (temperature_c * 9.0 / 5.0) + 32.0

            # Convert pressure from Pascal to inches of mercury (Hg)
            # 1 Pa = 0.00029529983071445 inHg
            pressure_hg = pressure_pa * 0.00029529983071445

            # Calculate altitude in feet (using standard sea level pressure of 1013.25 hPa)
            altitude_m = self.bme280.calculate_altitude(1013.25)
            altitude_ft = altitude_m * 3.28084 if altitude_m is not None else 0.0

            total_time = time.time() - start_time
            self.logger.info(
                f"BME280 altimeter read - Temp: {temperature_f:.1f}°F, "
                f"Pressure: {pressure_hg:.2f} inHg, Altitude: {altitude_ft:.1f} ft "
                f"(took {total_time:.3f}s)"
            )

            return AltimeterReadResponse(
                success=True,
                message="BME280 altimeter read successful",
                temperature_f=temperature_f,
                pressure_hg=pressure_hg,
                altitude_ft=altitude_ft,
            )

        except Exception as e:
            total_time = time.time() - start_time
            self.logger.error(f"Error reading BME280 altimeter after {total_time:.3f}s: {e}")
            return AltimeterReadResponse(
                success=False,
                message=f"Error reading BME280 altimeter: {str(e)}",
                temperature_f=0.0,
                pressure_hg=0.0,
                altitude_ft=0.0,
            )

    def read_accel(self, request: Empty, context: grpc.ServicerContext) -> AccelReadResponse:
        """Read accelerometer sensor data."""
        start_time = time.time()
        self.logger.info("AccelRead request received")

        if self.accel_device_path is None:
            return AccelReadResponse(
                success=False, message="Accelerometer device not initialized", x_g=0.0, y_g=0.0, z_g=0.0
            )

        try:
            # Read raw accelerometer values with timing
            read_start = time.time()
            raw_x = self._read_raw_value(f"{self.accel_device_path}/in_accel_x_raw")
            x_time = time.time() - read_start

            read_start = time.time()
            raw_y = self._read_raw_value(f"{self.accel_device_path}/in_accel_y_raw")
            y_time = time.time() - read_start

            read_start = time.time()
            raw_z = self._read_raw_value(f"{self.accel_device_path}/in_accel_z_raw")
            z_time = time.time() - read_start

            self.logger.info(f"File read times - X: {x_time:.3f}s, Y: {y_time:.3f}s, Z: {z_time:.3f}s")

            # Log the actual file paths being read for debugging
            self.logger.debug(f"Reading from: {self.accel_device_path}/in_accel_*_raw")

            # Convert to G values using scale factors
            x_g = raw_x * self.accel_scale_x
            y_g = raw_y * self.accel_scale_y
            z_g = raw_z * self.accel_scale_z

            total_time = time.time() - start_time
            self.logger.info(
                f"Accelerometer read - X: {x_g:.3f}g, Y: {y_g:.3f}g, Z: {z_g:.3f}g (total: {total_time:.3f}s)"
            )

            return AccelReadResponse(success=True, message="Accelerometer read successful", x_g=x_g, y_g=y_g, z_g=z_g)

        except Exception as e:
            total_time = time.time() - start_time
            self.logger.error(f"Error reading accelerometer after {total_time:.3f}s: {e}")
            return AccelReadResponse(
                success=False, message=f"Error reading accelerometer: {str(e)}", x_g=0.0, y_g=0.0, z_g=0.0
            )

    def _read_raw_value(self, raw_file_path):
        """Read raw value from IIO device file."""
        try:
            # Check if file exists and is readable
            if not os.path.exists(raw_file_path):
                raise IOError(f"File does not exist: {raw_file_path}")

            if not os.access(raw_file_path, os.R_OK):
                raise IOError(f"File is not readable: {raw_file_path}")

            # Read the file
            with open(raw_file_path, "r") as f:
                data = f.read().strip()
                if not data:
                    raise IOError(f"No data read from {raw_file_path}")
                return int(data)
        except (IOError, OSError, ValueError) as e:
            self.logger.error(f"Error reading raw value from {raw_file_path}: {e}")
            raise
