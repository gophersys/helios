from dataclasses import dataclass, field
from typing import List


@dataclass
class TargetDevice:
    """A connected target device.

    Args:
        id: Unique target identifier (e.g. 'nrf52840_dk').
        name: Human-readable name.
        arch: Architecture enum value.
        chip: Chip name (e.g. 'nRF52840').
        board: Zephyr board name.
        has_debug: Whether debug probe is available.
        has_uart: Whether UART is available.
        has_rtt: Whether RTT is supported.
        has_swo: Whether SWO/ITM trace is supported.
        flash_size_kb: Flash memory size in kilobytes.
        ram_size_kb: RAM size in kilobytes.
    """

    id: str
    name: str
    arch: int
    chip: str
    board: str
    has_debug: bool = False
    has_uart: bool = False
    has_rtt: bool = False
    has_swo: bool = False
    flash_size_kb: int = 0
    ram_size_kb: int = 0


@dataclass
class DebugProbe:
    """A connected debug probe.

    Args:
        id: Unique probe identifier.
        type: Probe type enum value.
        serial: Probe serial number.
        firmware_version: Probe firmware version.
        supported_targets: List of target IDs this probe supports.
    """

    id: str
    type: int
    serial: str
    firmware_version: str
    supported_targets: List[str] = field(default_factory=list)
