"""GPIO handler for V2 protocol."""

import time
from typing import TYPE_CHECKING, Dict, Iterator, Optional

from corekinect.utils import Logger
from src.services.gpio import Gpio, Pin

try:
    from gpiod.line import Direction, Value
except ImportError:
    # gpiod not available (e.g., in test/CI environments)
    # Provide fallback constants so handler can still be imported
    class Direction:
        INPUT = "input"
        OUTPUT = "output"
    class Value:
        ACTIVE = 1
        INACTIVE = 0
from src.shared.types import (
    GpioConfigRequest,
    GpioDirection,
    GpioEventResponse,
    GpioPull,
    GpioReadRequest,
    GpioReadResponse,
    GpioWatchRequest,
    GpioWriteRequest,
    Response,
    Timestamp,
)

if TYPE_CHECKING:
    from src.hardware import HardwareContext
    from src.providers.observability.gpio_tracker import GpioStateTracker

# DUT GPIO pin mapping (same for all revisions)
DUT_GPIO_PIN_MAP = {
    0: Pin.SODIMM_206,
    1: Pin.SODIMM_208,
    2: Pin.SODIMM_210,
    3: Pin.SODIMM_212,
    4: Pin.SODIMM_34,
    5: Pin.SODIMM_30,
    6: Pin.SODIMM_32,
    7: Pin.SODIMM_15,
    8: Pin.SODIMM_16,
}


class GpioHandler:
    """Handles V2 GPIO RPCs."""

    def __init__(self, logger: Logger, hardware: "HardwareContext", gpio_tracker: Optional["GpioStateTracker"] = None):
        self.logger = logger
        self.hardware = hardware
        self._gpios: Dict[int, Gpio] = {}
        self._tracker = gpio_tracker

        # Initialize all DUT GPIOs as inputs by default
        for logical_num, pin in DUT_GPIO_PIN_MAP.items():
            gpio = Gpio(consumer=f"mtib-gpio-{logical_num}", pin=pin, direction=Direction.INPUT)
            if err := gpio.init():
                self.logger.error(f"Failed to init GPIO {logical_num} ({pin}): {err}")
                continue
            self._gpios[logical_num] = gpio

            # Seed tracker with initial state so observability shows all pins from boot
            if self._tracker:
                self._tracker.update_config(logical_num, GpioDirection.GPIO_INPUT)
                err_r, value = gpio.read()
                if not err_r:
                    self._tracker.update_value(logical_num, bool(value))

        # Register live-read callback so observability always gets fresh values
        if self._tracker:
            self._tracker.set_refresh_callback(self._refresh_all_pins)

        self.logger.debug("All DUT GPIOs configured")

    def _refresh_all_pins(self) -> None:
        """Read all GPIO pin values and update the tracker."""
        for logical_num, gpio in self._gpios.items():
            err, value = gpio.read()
            if not err and self._tracker:
                self._tracker.update_value(logical_num, bool(value))

    def config(self, request: GpioConfigRequest, context) -> Response:
        """Configure a GPIO pin's direction and pull settings."""
        pin = request.pin
        if pin not in self._gpios:
            return Response(success=False, message=f"Invalid GPIO pin {pin}")

        gpio = self._gpios[pin]
        gpio.deinit()

        direction = Direction.OUTPUT if request.direction == GpioDirection.GPIO_OUTPUT else Direction.INPUT
        gpio.direction = direction

        if err := gpio.init():
            return Response(success=False, message=f"Failed to configure GPIO: {err}")

        if self._tracker:
            self._tracker.update_config(pin, request.direction)

        return Response(success=True, message="")

    def write(self, request: GpioWriteRequest, context) -> Response:
        """Write a value to a GPIO pin."""
        pin = request.pin
        if pin not in self._gpios:
            return Response(success=False, message=f"Invalid GPIO pin {pin}")

        gpio = self._gpios[pin]
        if err := gpio.write(1 if request.value else 0):
            return Response(success=False, message=str(err))

        if self._tracker:
            self._tracker.update_value(pin, request.value)

        return Response(success=True, message="")

    def read(self, request: GpioReadRequest, context) -> GpioReadResponse:
        """Read a value from a GPIO pin."""
        pin = request.pin
        if pin not in self._gpios:
            return GpioReadResponse(success=False, message=f"Invalid GPIO pin {pin}", value=False)

        gpio = self._gpios[pin]
        err, value = gpio.read()
        if err:
            return GpioReadResponse(success=False, message=str(err), value=False)

        if self._tracker:
            self._tracker.update_value(pin, bool(value))

        return GpioReadResponse(success=True, message="", value=bool(value))

    def watch(self, request: GpioWatchRequest, context) -> Iterator[GpioEventResponse]:
        """Server-streaming GPIO edge event watcher."""
        pin = request.pin
        if pin not in DUT_GPIO_PIN_MAP:
            return

        gpio_pin = DUT_GPIO_PIN_MAP[pin]
        self.logger.info(f"GPIO watch started: pin={pin}, edge={request.edge}")

        try:
            # Poll-based edge detection (gpiod v2 edge events need specific setup)
            last_value = None
            while context.is_active():
                gpio = self._gpios.get(pin)
                if gpio is None:
                    break

                err, current_value = gpio.read()
                if err:
                    break

                if last_value is not None and current_value != last_value:
                    # Edge detected
                    is_rising = current_value == 1
                    edge = request.edge
                    # GpioWatchRequest.Edge: EDGE_RISING=0, EDGE_FALLING=1, EDGE_BOTH=2
                    should_report = (
                        edge == 2  # EDGE_BOTH
                        or (edge == 0 and is_rising)  # EDGE_RISING
                        or (edge == 1 and not is_rising)  # EDGE_FALLING
                    )
                    if should_report:
                        now = time.time()
                        yield GpioEventResponse(
                            pin=pin,
                            value=bool(current_value),
                            timestamp=Timestamp(seconds=int(now), nanos=int((now % 1) * 1e9)),
                        )

                last_value = current_value
                time.sleep(0.001)  # 1ms polling interval

        except Exception as e:
            self.logger.error(f"GPIO watch error: {e}")
        finally:
            self.logger.info(f"GPIO watch ended: pin={pin}")
