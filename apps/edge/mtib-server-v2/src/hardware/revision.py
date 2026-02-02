"""Hardware revision detection and management.

This module provides a type-safe way to handle different MTIB board revisions.
Revisions can be auto-detected via I2C probing or overridden via environment variable.

Usage:
    # Auto-detect (default)
    revision = HardwareRevision.detect()

    # Override via env var
    os.environ["MTIB_HARDWARE_REVISION"] = "1.2"
    revision = HardwareRevision.from_env()

    # Get specs for the detected revision
    specs = revision.specs
    print(f"MCP4017 resistance: {specs.mcp4017_pot_ohms}Ω")
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Optional, Set

if TYPE_CHECKING:
    from smbus2 import SMBus

# Environment variable for revision override
ENV_HARDWARE_REVISION = "MTIB_HARDWARE_REVISION"
ENV_AUTO_DETECT = "MTIB_AUTO_DETECT_REVISION"


@dataclass(frozen=True)
class I2CDevice:
    """Represents an I2C device with its address and description."""

    address: int
    name: str
    description: str

    def __str__(self) -> str:
        return f"{self.name} (0x{self.address:02X})"


# I2C device definitions
class I2CDevices:
    """Known I2C devices on the MTIB board."""

    # Common devices (both revisions)
    LIS2DE12 = I2CDevice(0x19, "LIS2DE12", "3-axis accelerometer")
    MCP4017 = I2CDevice(0x2F, "MCP4017", "Digital potentiometer")
    INA219_DUT = I2CDevice(0x40, "INA219", "DUT current monitor")
    INA219_CHG = I2CDevice(0x41, "INA219", "Charge current monitor")
    ADS1115_0 = I2CDevice(0x48, "ADS1115", "16-bit ADC (ch 0-3)")
    ADS1115_1 = I2CDevice(0x49, "ADS1115", "16-bit ADC (ch 4-7)")
    BMP390L = I2CDevice(0x76, "BMP390L", "Pressure sensor")
    BME280 = I2CDevice(0x77, "BME280", "Pressure/humidity/temp")

    # REV 1.2 only devices
    TCA9534A = I2CDevice(0x38, "TCA9534A", "8-bit GPIO expander")
    AT24C02C = I2CDevice(0x50, "AT24C02C", "2Kbit EEPROM")


@dataclass(frozen=True)
class HardwareSpecs:
    """Hardware specifications for a specific board revision.

    All revision-specific hardware parameters are defined here.
    This makes it easy to add new revisions or modify existing ones.
    """

    # Revision identifier
    revision_id: str
    revision_name: str

    # MCP4017 digital potentiometer
    mcp4017_pot_ohms: int  # Maximum pot resistance
    mcp4017_fixed_ohms: int  # Fixed feedback resistor

    # TPS63802 buck-boost voltage range
    voltage_min: float
    voltage_max: float

    # Feature flags
    has_gpio_expander: bool  # TCA9534A present
    has_eeprom: bool  # AT24C02C present
    has_jlink_mux: bool  # SN74CBT3257C present
    has_motor_power_switch: bool  # Switchable motor power

    # I2C devices unique to this revision (for detection)
    unique_i2c_devices: tuple[I2CDevice, ...]

    def calculate_wiper_position(self, target_voltage: float) -> int:
        """Calculate MCP4017 wiper position for target voltage.

        The TPS63802 feedback equation: Vout = 0.8 * (1 + R1/R2)
        MCP4017 acts as variable R1 in the feedback divider.

        Args:
            target_voltage: Desired output voltage in volts

        Returns:
            Wiper position (0-127)
        """
        # Clamp to valid voltage range
        target_voltage = max(self.voltage_min, min(self.voltage_max, target_voltage))

        # Solve for R1: R1 = R2 * (Vout/0.8 - 1)
        r1_needed = self.mcp4017_fixed_ohms * (target_voltage / 0.8 - 1)

        # Clamp to pot range
        r1_needed = max(0, min(self.mcp4017_pot_ohms, r1_needed))

        # Convert to wiper position (0-127)
        wiper = int(r1_needed / self.mcp4017_pot_ohms * 127)
        return wiper


# Hardware specifications for each revision
_REV_1_1_SPECS = HardwareSpecs(
    revision_id="1.1",
    revision_name="REV 1.1 (Feb 2025)",
    mcp4017_pot_ohms=100_000,  # 100kΩ (MCP4017T-104E)
    mcp4017_fixed_ohms=30_000,  # 30kΩ feedback resistor
    voltage_min=0.8,
    voltage_max=5.5,
    has_gpio_expander=False,
    has_eeprom=False,
    has_jlink_mux=False,
    has_motor_power_switch=False,
    unique_i2c_devices=(),  # No unique devices
)

_REV_1_2_SPECS = HardwareSpecs(
    revision_id="1.2",
    revision_name="REV 1.2 (Dec 2025)",
    mcp4017_pot_ohms=10_000,  # 10kΩ (MCP4017T-103E)
    mcp4017_fixed_ohms=3_000,  # 3kΩ feedback resistor
    voltage_min=0.8,
    voltage_max=5.5,
    has_gpio_expander=True,
    has_eeprom=True,
    has_jlink_mux=True,
    has_motor_power_switch=True,
    unique_i2c_devices=(I2CDevices.TCA9534A, I2CDevices.AT24C02C),
)


class HardwareRevision(Enum):
    """MTIB board hardware revisions.

    Each revision has associated hardware specifications that define
    the behavior of revision-specific features.
    """

    REV_1_1 = _REV_1_1_SPECS
    REV_1_2 = _REV_1_2_SPECS

    @property
    def specs(self) -> HardwareSpecs:
        """Get the hardware specifications for this revision."""
        return self.value

    @property
    def id(self) -> str:
        """Get the revision ID string (e.g., '1.1', '1.2')."""
        return self.value.revision_id

    @classmethod
    def from_string(cls, revision_str: str) -> HardwareRevision:
        """Create a HardwareRevision from a string identifier.

        Args:
            revision_str: Revision string like "1.1", "1.2", "REV1.1", "REV_1_1", etc.

        Returns:
            Corresponding HardwareRevision enum member

        Raises:
            ValueError: If the revision string is not recognized
        """
        # Normalize: remove "REV", underscores, spaces; keep dots
        normalized = revision_str.upper().replace("REV", "").replace("_", ".").replace(" ", "").strip(".")

        for revision in cls:
            if revision.specs.revision_id == normalized:
                return revision

        valid = ", ".join(r.specs.revision_id for r in cls)
        raise ValueError(f"Unknown hardware revision '{revision_str}'. Valid revisions: {valid}")

    @classmethod
    def from_env(cls, default: Optional[HardwareRevision] = None) -> Optional[HardwareRevision]:
        """Get the hardware revision from environment variable.

        Reads the MTIB_HARDWARE_REVISION environment variable.

        Args:
            default: Default revision if env var is not set

        Returns:
            HardwareRevision if env var is set and valid, default otherwise

        Raises:
            ValueError: If env var is set but contains an invalid revision
        """
        env_value = os.environ.get(ENV_HARDWARE_REVISION)
        if env_value is None:
            return default
        return cls.from_string(env_value)

    @classmethod
    def detect(cls, bus_num: int = 1) -> HardwareRevision:
        """Auto-detect the hardware revision by probing I2C devices.

        Probes for revision-specific I2C devices to determine which
        board revision is present.

        Args:
            bus_num: I2C bus number to probe (default: 1)

        Returns:
            Detected HardwareRevision (defaults to REV_1_1 if detection fails)
        """
        try:
            import smbus2

            bus = smbus2.SMBus(bus_num)
            try:
                return cls._detect_from_bus(bus)
            finally:
                bus.close()
        except ImportError:
            # smbus2 not available, fall back to default
            return cls.REV_1_1
        except OSError:
            # I2C bus not available
            return cls.REV_1_1

    @classmethod
    def _detect_from_bus(cls, bus: SMBus) -> HardwareRevision:
        """Detect revision from an open I2C bus.

        Args:
            bus: Open smbus2.SMBus instance

        Returns:
            Detected HardwareRevision
        """
        # Check for REV 1.2 specific devices
        for device in I2CDevices.TCA9534A, I2CDevices.AT24C02C:
            try:
                bus.read_byte(device.address)
                return cls.REV_1_2
            except OSError:
                continue

        # Default to REV 1.1
        return cls.REV_1_1

    @classmethod
    def resolve(cls, bus_num: int = 1) -> HardwareRevision:
        """Resolve the hardware revision using env var or auto-detection.

        Priority:
        1. MTIB_HARDWARE_REVISION env var (if set)
        2. Auto-detection via I2C probing (if MTIB_AUTO_DETECT_REVISION != "false")
        3. Default to REV_1_1

        Args:
            bus_num: I2C bus number for auto-detection

        Returns:
            Resolved HardwareRevision
        """
        # Check for explicit override
        env_revision = cls.from_env()
        if env_revision is not None:
            return env_revision

        # Check if auto-detection is disabled
        auto_detect = os.environ.get(ENV_AUTO_DETECT, "true").lower()
        if auto_detect in ("false", "0", "no", "off"):
            return cls.REV_1_1

        # Auto-detect
        return cls.detect(bus_num)

    def __str__(self) -> str:
        return self.specs.revision_name

    def __repr__(self) -> str:
        return f"HardwareRevision.{self.name}"
