# Standard library
import glob
import os
import time
from typing import Optional

# Third party
import grpc

# Corekinect
from corekinect.utils import Logger
from corekinect.utils.units.temp import celsius_to_fahrenheit

# Proto types
from src.shared.types import (
    AccelReadResponse,
    AltimeterReadResponse,
    Empty,
)

# Drivers
from src.drivers.bme280 import BME280
from src.drivers.lis2de12 import LIS2DE12


class SensorsHandler:
    def __init__(self, logger: Logger, bme280: BME280 | None):
        self.logger = logger
        self.bme280 = bme280
        self._lis2de12 = LIS2DE12(logger)

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
            temperature_c, pressure_hpa, humidity_rh = self.bme280.read_all()

            if temperature_c is None or pressure_hpa is None:
                return AltimeterReadResponse(
                    success=False,
                    message="Failed to read sensor data",
                    temperature_f=0.0,
                    pressure_hg=0.0,
                    altitude_ft=0.0,
                )

            # Convert temperature from Celsius to Fahrenheit
            temperature_f = celsius_to_fahrenheit(temperature_c)

            # Convert pressure from hectoPascal to inches of mercury (Hg)
            # BME280 returns pressure in hPa, 1 hPa = 0.029529983071445 inHg
            pressure_hg = pressure_hpa * 0.029529983071445

            # Calculate altitude in feet (using standard sea level pressure of 1013.25 hPa)
            altitude_m = self.bme280.calculate_altitude(1013.25)
            altitude_ft = altitude_m * 3.28084 if altitude_m is not None else 0.0

            total_time = time.time() - start_time
            self.logger.info(
                f"BME280 altimeter read - Temp: {temperature_f:.1f}F, "
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

        err, x_g, y_g, z_g = self._lis2de12.read()
        if err:
            total_time = time.time() - start_time
            self.logger.error(f"Error reading accelerometer after {total_time:.3f}s: {err}")
            return AccelReadResponse(
                success=False, message=f"Error reading accelerometer: {err}", x_g=0.0, y_g=0.0, z_g=0.0
            )

        total_time = time.time() - start_time
        self.logger.info(
            f"Accelerometer read - X: {x_g:.3f}g, Y: {y_g:.3f}g, Z: {z_g:.3f}g (total: {total_time:.3f}s)"
        )

        return AccelReadResponse(success=True, message="Accelerometer read successful", x_g=x_g, y_g=y_g, z_g=z_g)
