"""Hardware abstraction layer for MTIB server.

This package provides a clean, extensible interface for interacting with
MTIB board hardware across different revisions.

Environment Variables:
    MTIB_HARDWARE_REVISION: Override auto-detected revision (e.g., "1.1", "1.2")
    MTIB_AUTO_DETECT_REVISION: Set to "false" to disable auto-detection

Usage:
    from src.hardware import HardwareRevision, HardwareContext

    # Resolve revision from env var or auto-detect
    revision = HardwareRevision.resolve()
    print(f"Running on {revision}")

    # Create hardware context
    with HardwareContext.create() as hw:
        # Calculate voltage wiper (revision-aware)
        wiper = hw.calculate_voltage_wiper(3.3)

        # REV 1.2 only features
        if hw.has_jlink_mux:
            hw.set_jlink_mux(swap=False)
"""

from .context import HardwareContext, HardwareFeatureNotAvailable
from .revision import (
    ENV_AUTO_DETECT,
    ENV_HARDWARE_REVISION,
    HardwareRevision,
    HardwareSpecs,
    I2CDevice,
    I2CDevices,
)
from .tca9534a import TCA9534A, TCA9534APin, TCA9534ARegister, TCA9534AState

__all__ = [
    # Environment variable names
    "ENV_HARDWARE_REVISION",
    "ENV_AUTO_DETECT",
    # Core types
    "HardwareRevision",
    "HardwareSpecs",
    "HardwareContext",
    "HardwareFeatureNotAvailable",
    # I2C devices
    "I2CDevice",
    "I2CDevices",
    # GPIO expander (REV 1.2)
    "TCA9534A",
    "TCA9534APin",
    "TCA9534ARegister",
    "TCA9534AState",
]
