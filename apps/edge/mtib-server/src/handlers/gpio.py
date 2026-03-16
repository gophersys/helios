# Standard library imports
import time
from datetime import timedelta
from typing import Dict, Iterator, Optional

# Third party imports
import gpiod
import grpc

# Corekinect imports
from corekinect.utils import Logger
from gpiod.line import Bias, Direction, Edge, Value

# Protocol imports
from src.drivers.gpio import Gpio, Pin
from src.shared.types import (
    GpioConfigRequest,
    GpioConfigResponse,
    GpioDirection,
    GpioReadRequest,
    GpioReadResponse,
    GpioResistorConfig,
    GpioWriteRequest,
    GpioWriteResponse,
    GpioEdge,
    GpioWatchRequest,
    GpioWatchEvent,
    SnapshotGpio,
)


# -------------------------------------------------
#                                 GPIO gRPC Handler
# -------------------------------------------------
class GpioHandler:
    def __init__(self, gpios: Dict[int, Gpio], logger: Logger):
        self.gpios = gpios
        self.logger = logger

    # Map proto resistor config to gpiod Bias
    _RESISTOR_MAP = {
        GpioResistorConfig.GPIO_RESISTOR_PULL_UP: Bias.PULL_UP,
        GpioResistorConfig.GPIO_RESISTOR_PULL_DOWN: Bias.PULL_DOWN,
        GpioResistorConfig.GPIO_RESISTOR_NONE: Bias.DISABLED,
    }

    def config(self, request: GpioConfigRequest, context: grpc.ServicerContext) -> GpioConfigResponse:
        """Configure a GPIO pin's direction and resistor settings."""
        self.logger.info(f"GpioConfig request received for GPIO {request.gpio}")

        if request.gpio not in self.gpios:
            return GpioConfigResponse(success=False, message=f"Invalid GPIO number {request.gpio}. GPIO not found.")

        gpio = self.gpios[request.gpio]
        gpio.deinit()

        direction = Direction.OUTPUT if request.direction == GpioDirection.GPIO_DIRECTION_OUTPUT else Direction.INPUT
        gpio.direction = direction

        # Apply resistor/bias config if specified
        bias = self._RESISTOR_MAP.get(request.resistor)
        if bias is not None:
            gpio.bias = bias

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
            return GpioWriteResponse(success=False, message=f"{err}")

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

    def watch(self, request: GpioWatchRequest, context: grpc.ServicerContext) -> Iterator[GpioWatchEvent]:
        """Server-streaming GPIO edge detection."""
        self.logger.info(f"GpioWatch: gpio={request.gpio}, edge={request.edge}")

        if request.gpio not in self.gpios:
            return

        gpio = self.gpios[request.gpio]
        pin = gpio.pin

        # Map proto edge enum to gpiod edge
        edge_map = {
            GpioEdge.GPIO_EDGE_RISING: Edge.RISING,
            GpioEdge.GPIO_EDGE_FALLING: Edge.FALLING,
            GpioEdge.GPIO_EDGE_BOTH: Edge.BOTH,
        }
        gpiod_edge = edge_map.get(request.edge, Edge.BOTH)

        # Temporarily release the pin and re-request with edge detection
        gpio.deinit()

        watch_request = None
        try:
            for chip_num in range(5):
                try:
                    chip = gpiod.Chip(f"/dev/gpiochip{chip_num}")
                    config = {
                        pin.value: gpiod.LineSettings(
                            direction=Direction.INPUT,
                            edge_detection=gpiod_edge,
                        )
                    }
                    watch_request = chip.request_lines(config=config, consumer="mtib-gpio-watch")
                    break
                except Exception:
                    continue

            if not watch_request:
                self.logger.error(f"GpioWatch: Could not configure edge detection for GPIO {request.gpio}")
                return

            self.logger.info(f"GpioWatch: Monitoring GPIO {request.gpio} for {gpiod_edge} edges")
            start_time = time.time()

            while context.is_active():
                # Wait for edge events with 100ms timeout (timedelta, not clock type)
                if watch_request.wait_edge_events(timeout=timedelta(milliseconds=100)):
                    try:
                        events = watch_request.read_edge_events()
                        for event in events:
                            if not context.is_active():
                                break
                            elapsed_ms = int((time.time() - start_time) * 1000)
                            state = event.event_type == gpiod.EdgeEvent.Type.RISING_EDGE
                            yield GpioWatchEvent(
                                gpio=request.gpio,
                                state=state,
                                timestamp_ms=elapsed_ms,
                            )
                    except Exception:
                        pass

        except Exception as e:
            self.logger.error(f"GpioWatch error: {e}")
        finally:
            if watch_request:
                watch_request.release()
            # Re-initialize the original GPIO config
            gpio.init()
            self.logger.info(f"GpioWatch ended for GPIO {request.gpio}")

    def get_snapshot_data(self) -> list:
        """Return current GPIO states for GetSnapshot."""
        result = []
        for gpio_num, gpio in self.gpios.items():
            try:
                err, value = gpio.read()
                if not err:
                    result.append(SnapshotGpio(gpio=gpio_num, state=bool(value)))
            except Exception as e:
                self.logger.warning(f"Snapshot: failed to read GPIO {gpio_num}: {e}")
        return result
