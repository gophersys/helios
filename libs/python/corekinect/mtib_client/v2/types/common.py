from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class MtibError:
    """Structured error from the MTIB server.

    Args:
        code: Numeric error code.
        message: Human-readable error description.
        details: Additional key-value error context.
    """

    code: int
    message: str
    details: Dict[str, str] = field(default_factory=dict)


@dataclass
class HealthStatus:
    """Result of a health check.

    Args:
        ready: Whether the server is ready to accept requests.
        version: Server firmware/software version string.
        errors: List of any active error conditions.
        capabilities: Map of capability names to their status/version.
    """

    ready: bool
    version: str
    errors: List[str] = field(default_factory=list)
    capabilities: Dict[str, str] = field(default_factory=dict)


@dataclass
class SystemInfo:
    """System information from the MTIB server.

    Args:
        hostname: Server hostname.
        os: Operating system description.
        cpu_usage: CPU usage percentage (0.0-100.0).
        memory_usage: Memory usage percentage (0.0-100.0).
        disk_usage: Disk usage percentage (0.0-100.0).
        uptime_s: Server uptime in seconds.
    """

    hostname: str
    os: str
    cpu_usage: float
    memory_usage: float
    disk_usage: float
    uptime_s: float
