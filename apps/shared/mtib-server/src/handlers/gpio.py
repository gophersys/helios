from typing import Tuple, Dict
import grpc
from corekinect.utils import Logger
from src.lib.gpio import Gpio, Direction
from src.shared.types import *


class GpioHandler:
    def __init__(self, gpios: Dict[int, Gpio], logger: Logger):
        self.gpios = gpios
        self.logger = logger

    def config(self, request: GpioConfigRequest, context: grpc.ServicerContext) -> GpioConfigResponse:
        """Configure a GPIO pin's direction and resistor settings."""
        self.logger.info(f"GpioConfig request received for GPIO {request.gpio}")

        # Validate GPIO number
        if request.gpio not in self.gpios:
            return GpioConfigResponse(success=False, message=f"Invalid GPIO number {request.gpio}. GPIO not found.")

        gpio = self.gpios[request.gpio]
        gpio.deinit()

        direction = Direction.OUTPUT if request.direction == GpioDirection.GPIO_DIRECTION_OUTPUT else Direction.INPUT
        if err := gpio.init():
            return GpioConfigResponse(success=False, message=f"Failed to configure GPIO: {err}")

        return GpioConfigResponse(success=True, message="")

    def write(self, request: GpioWriteRequest, context: grpc.ServicerContext) -> GpioWriteResponse:
        """Write a value to a GPIO pin."""
        self.logger.info(f"GpioWrite request received for GPIO {request.gpio}, state: {request.state}")

        if request.gpio not in self.gpios:
            return GpioWriteResponse(success=False, message=f"Invalid GPIO number {request.gpio}. GPIO not found.")

        gpio = self.gpios[request.gpio]
        if err := gpio.write(1 if request.state else 0):
            return GpioWriteResponse(success=False, message=f"Failed to write to GPIO: {err}")

        return GpioWriteResponse(success=True, message="")

    def read(self, request: GpioReadRequest, context: grpc.ServicerContext) -> GpioReadResponse:
        """Read a value from a GPIO pin."""
        self.logger.info(f"GpioRead request received for GPIO {request.gpio}")

        if request.gpio not in self.gpios:
            return GpioReadResponse(
                success=False, message=f"Invalid GPIO number {request.gpio}. GPIO not found.", state=False
            )

        gpio = self.gpios[request.gpio]
        err, value = gpio.read()
        if err:
            return GpioReadResponse(success=False, message=f"Failed to read GPIO: {err}", state=False)

        return GpioReadResponse(success=True, message="", state=bool(value))
