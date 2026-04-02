"""Structured error types — re-exports from top-level module.

The canonical definitions now live at ``corekinect.errors``.
This module re-exports them for backward compatibility so existing
imports like ``from corekinect.test.errors import CloudError`` still work.

Usage:
    from corekinect.test.errors import CloudError, FirmwareError

    raise CloudError("Device not registered in CoreCloud")
    raise FirmwareError(
        "Version mismatch: expected 0.5.2, got 0.5.1",
        expected="0.5.2",
        actual="0.5.1",
    )
"""

# Re-export everything from the canonical location
from corekinect.errors import (  # noqa: F401
    CloudError,
    ConfigError,
    FirmwareError,
    HardwareError,
    TimeoutError,
    ValidationError,
)

__all__ = [
    "CloudError",
    "ConfigError",
    "FirmwareError",
    "HardwareError",
    "TimeoutError",
    "ValidationError",
]
