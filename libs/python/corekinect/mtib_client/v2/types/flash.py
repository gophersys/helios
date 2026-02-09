from dataclasses import dataclass, field
from typing import List


@dataclass
class FlashRegion:
    """A flash memory region.

    Args:
        start: Start address.
        size: Region size in bytes.
        sector_size: Erase sector size in bytes.
        writable: Whether the region is writable.
    """

    start: int
    size: int
    sector_size: int
    writable: bool


@dataclass
class FlashInfo:
    """Flash memory layout information.

    Args:
        regions: List of flash memory regions.
    """

    regions: List[FlashRegion] = field(default_factory=list)


@dataclass
class FlashWriteResult:
    """Result of a flash write operation.

    Args:
        bytes_written: Number of bytes written.
        time_ms: Time taken in milliseconds.
    """

    bytes_written: int
    time_ms: int


@dataclass
class FlashProgramResult:
    """Result of a flash program operation.

    Args:
        bytes_programmed: Number of bytes programmed.
        time_ms: Time taken in milliseconds.
    """

    bytes_programmed: int
    time_ms: int
