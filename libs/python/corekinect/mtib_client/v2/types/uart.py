from dataclasses import dataclass


@dataclass
class UartConnection:
    """An open UART connection.

    Args:
        stream_id: Unique stream identifier for subsequent UART operations.
    """

    stream_id: str


@dataclass
class UartMessage:
    """A UART message received from the target.

    Args:
        data: Raw bytes received.
        timestamp_s: Timestamp seconds.
        timestamp_ns: Timestamp nanoseconds.
    """

    data: bytes
    timestamp_s: int = 0
    timestamp_ns: int = 0
