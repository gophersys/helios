from dataclasses import dataclass, field
from typing import List


@dataclass
class I2cResult:
    """Result of an I2C transfer.

    Args:
        read_data: Data read from the device.
        nak: Whether a NAK was received.
    """

    read_data: bytes
    nak: bool = False


@dataclass
class I2cScanResult:
    """Result of an I2C bus scan.

    Args:
        addresses: List of responding 7-bit I2C addresses.
    """

    addresses: List[int] = field(default_factory=list)


@dataclass
class SpiResult:
    """Result of an SPI transfer.

    Args:
        rx_data: Data received from the device.
    """

    rx_data: bytes


@dataclass
class CanFrame:
    """A CAN bus frame.

    Args:
        id: CAN frame ID.
        extended_id: Whether this uses extended (29-bit) ID.
        fd: Whether this is a CAN FD frame.
        brs: Bit rate switch flag.
        data: Frame payload.
        timestamp_s: Timestamp seconds.
        timestamp_ns: Timestamp nanoseconds.
    """

    id: int
    extended_id: bool = False
    fd: bool = False
    brs: bool = False
    data: bytes = b""
    timestamp_s: int = 0
    timestamp_ns: int = 0
