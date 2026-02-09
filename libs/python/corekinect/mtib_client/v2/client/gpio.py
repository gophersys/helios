from typing import Iterator, Optional, Tuple

from protocols.mtib_v2.mtib_v2_pb2 import (
    GpioConfigRequest,
    GpioReadRequest,
    GpioWatchRequest,
    GpioWriteRequest,
)

from ._base import BaseClient
from ..types.gpio import GpioEvent, GpioState


class GpioMixin(BaseClient):
    """GPIO control operations."""

    def gpio_config(
        self,
        pin: int,
        direction: int = 0,
        pull: int = 0,
        open_drain: bool = False,
    ) -> Optional[str]:
        """Configure a GPIO pin.

        Args:
            pin: GPIO pin number.
            direction: Direction (0=INPUT, 1=OUTPUT).
            pull: Pull mode (0=NONE, 1=UP, 2=DOWN).
            open_drain: Whether to use open-drain output.

        Returns:
            Error message string, or None on success.
        """
        try:
            resp = self._call(
                "GpioConfig",
                GpioConfigRequest(
                    pin=pin, direction=direction, pull=pull, open_drain=open_drain
                ),
            )
            if not resp.success:
                return resp.message
            return None
        except Exception as e:
            return f"gpio_config error: {e}"

    def gpio_write(self, pin: int, value: bool) -> Optional[str]:
        """Write a GPIO pin output value.

        Args:
            pin: GPIO pin number.
            value: Logic level (True=high, False=low).

        Returns:
            Error message string, or None on success.
        """
        try:
            resp = self._call("GpioWrite", GpioWriteRequest(pin=pin, value=value))
            if not resp.success:
                return resp.message
            return None
        except Exception as e:
            return f"gpio_write error: {e}"

    def gpio_read(self, pin: int) -> Tuple[Optional[str], Optional[GpioState]]:
        """Read a GPIO pin value.

        Args:
            pin: GPIO pin number.

        Returns:
            (error, GpioState) tuple. error is None on success.
        """
        try:
            resp = self._call("GpioRead", GpioReadRequest(pin=pin))
            if not resp.success:
                return resp.message, None
            return None, GpioState(pin=pin, value=resp.value)
        except Exception as e:
            return f"gpio_read error: {e}", None

    def gpio_watch(
        self, pin: int, edge: int = 2, timeout: float = None
    ) -> Iterator[GpioEvent]:
        """Watch a GPIO pin for edge events.

        Args:
            pin: GPIO pin number.
            edge: Edge type (0=RISING, 1=FALLING, 2=BOTH).
            timeout: Stream timeout in seconds.

        Yields:
            GpioEvent objects for each detected edge.
        """
        stream = self._server_stream(
            "GpioWatch", GpioWatchRequest(pin=pin, edge=edge), timeout=timeout
        )
        for resp in stream:
            yield GpioEvent(
                pin=resp.pin,
                value=resp.value,
                timestamp_s=resp.timestamp.seconds if resp.timestamp else 0,
                timestamp_ns=resp.timestamp.nanos if resp.timestamp else 0,
            )
