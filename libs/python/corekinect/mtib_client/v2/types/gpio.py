from dataclasses import dataclass


@dataclass
class GpioState:
    """Current state of a GPIO pin.

    Args:
        pin: GPIO pin number.
        value: Pin logic level (True = high, False = low).
    """

    pin: int
    value: bool


@dataclass
class GpioEvent:
    """A GPIO edge event.

    Args:
        pin: GPIO pin number.
        value: Pin logic level after the event.
        timestamp_s: Timestamp seconds.
        timestamp_ns: Timestamp nanoseconds.
    """

    pin: int
    value: bool
    timestamp_s: int = 0
    timestamp_ns: int = 0
