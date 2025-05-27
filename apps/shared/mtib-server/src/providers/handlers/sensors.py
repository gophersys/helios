import grpc
from corekinect.utils import Logger
from src.shared.types import *

class SensorsHandler:
    def __init__(self, logger: Logger):
        self.logger = logger

    def read_altimeter(self, request: Empty, context: grpc.ServicerContext) -> AltimeterReadResponse:
        """Read altimeter sensor data."""
        self.logger.info("AltimeterRead request received")
        return AltimeterReadResponse(
            success=False,
            message="Not implemented",
            temperature_f=0.0,
            pressure_hg=0.0,
            altitude_ft=0.0
        )

    def read_accel(self, request: Empty, context: grpc.ServicerContext) -> AccelReadResponse:
        """Read accelerometer sensor data."""
        self.logger.info("AccelRead request received")
        return AccelReadResponse(
            success=False,
            message="Not implemented",
            x_g=0.0,
            y_g=0.0,
            z_g=0.0
        ) 