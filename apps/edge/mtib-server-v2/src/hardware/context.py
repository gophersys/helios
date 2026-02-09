"""Hardware context manager for MTIB server.

This module provides a unified interface for accessing all hardware-specific
functionality based on the detected or configured board revision.

Usage:
    # Create hardware context (auto-detects revision)
    hw = HardwareContext.create()

    # Or with explicit revision
    hw = HardwareContext.create(revision=HardwareRevision.REV_1_2)

    # Access hardware features
    hw.set_dut_voltage(3.3)

    # REV 1.2 specific features (raises error on REV 1.1)
    hw.set_jlink_mux(swap=True)
    hw.set_motor_power(enable=True)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional

from .revision import HardwareRevision, HardwareSpecs
from .tca9534a import TCA9534A, TCA9534APin

if TYPE_CHECKING:
    from corekinect.utils import Logger


class HardwareFeatureNotAvailable(Exception):
    """Raised when a feature is not available on the current hardware revision."""

    def __init__(self, feature: str, revision: HardwareRevision):
        self.feature = feature
        self.revision = revision
        super().__init__(f"{feature} is not available on {revision}")


@dataclass
class HardwareContext:
    """Unified hardware context for MTIB server.

    This class provides a single point of access for all hardware-specific
    functionality, automatically adapting to the detected board revision.
    """

    revision: HardwareRevision
    specs: HardwareSpecs = field(init=False)

    # Optional hardware components (only initialized on supported revisions)
    _gpio_expander: Optional[TCA9534A] = field(default=None, init=False)
    _initialized: bool = field(default=False, init=False)
    _logger: Optional[logging.Logger] = field(default=None, init=False)

    def __post_init__(self) -> None:
        self.specs = self.revision.specs

    @classmethod
    def create(
        cls,
        revision: Optional[HardwareRevision] = None,
        logger: Optional[Logger] = None,
        i2c_bus: int = 3,  # /dev/i2c-3 = Verdin I2C_1 (main bus on TorizonOS)
    ) -> HardwareContext:
        """Create a hardware context with optional revision override.

        Args:
            revision: Explicit revision to use (None = auto-detect/env var)
            logger: Optional logger for hardware operations
            i2c_bus: I2C bus number for hardware access

        Returns:
            Initialized HardwareContext
        """
        if revision is None:
            revision = HardwareRevision.resolve(bus_num=i2c_bus)

        ctx = cls(revision=revision)
        ctx._logger = logger
        ctx._i2c_bus = i2c_bus
        return ctx

    def init(self) -> None:
        """Initialize all hardware components for the detected revision.

        This should be called once during server startup.
        """
        if self._initialized:
            return

        self._log_info(f"Initializing hardware context for {self.revision}")

        # Initialize REV 1.2 specific hardware
        if self.specs.has_gpio_expander:
            self._log_info("Initializing TCA9534A GPIO expander")
            self._gpio_expander = TCA9534A(bus_num=self._i2c_bus)
            self._gpio_expander.init()

        self._initialized = True
        self._log_info(f"Hardware context initialized: {self.revision}")

    def close(self) -> None:
        """Close all hardware connections."""
        if self._gpio_expander is not None:
            self._gpio_expander.close()
            self._gpio_expander = None

        self._initialized = False

    def _log_info(self, msg: str) -> None:
        """Log an info message if logger is available."""
        if self._logger is not None:
            self._logger.info(msg)

    def _log_warning(self, msg: str) -> None:
        """Log a warning message if logger is available."""
        if self._logger is not None:
            self._logger.warning(msg)

    def _require_feature(self, feature: str, available: bool) -> None:
        """Raise an error if a feature is not available."""
        if not available:
            raise HardwareFeatureNotAvailable(feature, self.revision)

    # -------------------------------------------------------------------------
    # Power Control
    # -------------------------------------------------------------------------

    def calculate_voltage_wiper(self, target_voltage: float) -> int:
        """Calculate MCP4017 wiper position for target voltage.

        This method handles the different resistance values between revisions.

        Args:
            target_voltage: Desired DUT voltage in volts

        Returns:
            Wiper position (0-127)
        """
        return self.specs.calculate_wiper_position(target_voltage)

    # -------------------------------------------------------------------------
    # GPIO Expander (REV 1.2 only)
    # -------------------------------------------------------------------------

    @property
    def gpio_expander(self) -> TCA9534A:
        """Get the GPIO expander (REV 1.2 only).

        Raises:
            HardwareFeatureNotAvailable: If not on REV 1.2
        """
        self._require_feature("GPIO expander (TCA9534A)", self.specs.has_gpio_expander)
        if self._gpio_expander is None:
            raise RuntimeError("Hardware context not initialized")
        return self._gpio_expander

    def set_jlink_mux(self, swap: bool) -> None:
        """Set J-Link multiplexer routing (REV 1.2 only).

        Args:
            swap: True to swap J-Link signals, False for normal routing

        Raises:
            HardwareFeatureNotAvailable: If not on REV 1.2
        """
        self._require_feature("J-Link multiplexer", self.specs.has_jlink_mux)
        self.gpio_expander.set_jlink_mux(swap)
        self._log_info(f"J-Link mux set to {'swapped' if swap else 'normal'}")

    def set_motor_power(self, enable: bool) -> None:
        """Enable or disable motor power (REV 1.2 only).

        On REV 1.1, motor power is always on when external supply is connected.

        Args:
            enable: True to enable motor power, False to disable

        Raises:
            HardwareFeatureNotAvailable: If not on REV 1.2
        """
        if not self.specs.has_motor_power_switch:
            # On REV 1.1, motor power is always on - just log a warning
            self._log_warning("Motor power control not available on this revision (always on)")
            return

        self.gpio_expander.set_motor_power(enable)
        self._log_info(f"Motor power {'enabled' if enable else 'disabled'}")

    def set_eeprom_write_protect(self, protect: bool) -> None:
        """Set EEPROM write protect state (REV 1.2 only).

        Args:
            protect: True to enable write protection, False to allow writes

        Raises:
            HardwareFeatureNotAvailable: If not on REV 1.2
        """
        self._require_feature("EEPROM", self.specs.has_eeprom)
        self.gpio_expander.set_eeprom_write_protect(protect)
        self._log_info(f"EEPROM write protect {'enabled' if protect else 'disabled'}")

    # -------------------------------------------------------------------------
    # Feature Queries
    # -------------------------------------------------------------------------

    @property
    def has_gpio_expander(self) -> bool:
        """Check if GPIO expander is available."""
        return self.specs.has_gpio_expander

    @property
    def has_eeprom(self) -> bool:
        """Check if EEPROM is available."""
        return self.specs.has_eeprom

    @property
    def has_jlink_mux(self) -> bool:
        """Check if J-Link multiplexer is available."""
        return self.specs.has_jlink_mux

    @property
    def has_motor_power_switch(self) -> bool:
        """Check if motor power can be controlled."""
        return self.specs.has_motor_power_switch

    # -------------------------------------------------------------------------
    # Context Manager
    # -------------------------------------------------------------------------

    def __enter__(self) -> HardwareContext:
        """Context manager entry - initializes hardware."""
        self.init()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit - closes hardware connections."""
        self.close()

    def __repr__(self) -> str:
        status = "initialized" if self._initialized else "not initialized"
        return f"HardwareContext({self.revision}, {status})"
