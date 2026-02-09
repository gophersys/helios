"""Mock hardware for testing MTIB V2 handlers without real I2C/GPIO."""

import os
import tempfile
from dataclasses import dataclass, field
from typing import Dict, Optional
from unittest.mock import MagicMock, patch

from src.hardware.revision import HardwareRevision, HardwareSpecs


class MockHardwareContext:
    """Mock HardwareContext that simulates hardware behavior."""

    def __init__(self, revision: HardwareRevision = HardwareRevision.REV_1_1):
        self.revision = revision
        self.specs = revision.specs
        self._initialized = True

    def init(self) -> None:
        self._initialized = True

    def close(self) -> None:
        self._initialized = False

    def calculate_voltage_wiper(self, target_voltage: float) -> int:
        return self.specs.calculate_wiper_position(target_voltage)

    @property
    def has_gpio_expander(self) -> bool:
        return self.specs.has_gpio_expander

    @property
    def has_eeprom(self) -> bool:
        return self.specs.has_eeprom

    @property
    def has_jlink_mux(self) -> bool:
        return self.specs.has_jlink_mux

    @property
    def has_motor_power_switch(self) -> bool:
        return self.specs.has_motor_power_switch

    def set_motor_power(self, enable: bool) -> None:
        pass

    def set_jlink_mux(self, swap: bool) -> None:
        pass


class MockLogger:
    """Mock logger that captures log messages."""

    def __init__(self):
        self.messages: list[tuple[str, str]] = []

    def info(self, msg: str, *args) -> None:
        self.messages.append(("info", msg % args if args else msg))

    def debug(self, msg: str, *args) -> None:
        self.messages.append(("debug", msg % args if args else msg))

    def warning(self, msg: str, *args) -> None:
        self.messages.append(("warning", msg % args if args else msg))

    def error(self, msg: str, *args) -> None:
        self.messages.append(("error", msg % args if args else msg))

    def from_parent(self, name: str) -> "MockLogger":
        return self


class MockGrpcContext:
    """Mock gRPC ServicerContext."""

    def __init__(self):
        self._peer = "test_peer"
        self._active = True
        self._code = None
        self._details = None

    def peer(self) -> str:
        return self._peer

    def is_active(self) -> bool:
        return self._active

    def set_code(self, code) -> None:
        self._code = code

    def set_details(self, details: str) -> None:
        self._details = details

    def cancel(self) -> None:
        self._active = False


class MockINA219:
    """Mock INA219 hwmon sysfs interface."""

    def __init__(self, base_dir: str, address: int, voltage_mv: float = 3300.0, current_ma: float = 100.0):
        self.base_dir = base_dir
        self.address = address
        self.voltage_mv = voltage_mv
        self.current_ma = current_ma
        self.power_uw = voltage_mv * current_ma  # V * mA = uW (approximately)

        # Create sysfs files
        hwmon_dir = os.path.join(base_dir, f"hwmon_ina219_{address:02x}")
        os.makedirs(hwmon_dir, exist_ok=True)

        # Write name file
        with open(os.path.join(hwmon_dir, "name"), "w") as f:
            f.write("ina219\n")

        # Write measurement files
        with open(os.path.join(hwmon_dir, "in1_input"), "w") as f:
            f.write(f"{int(voltage_mv)}\n")

        with open(os.path.join(hwmon_dir, "curr1_input"), "w") as f:
            f.write(f"{int(current_ma)}\n")

        with open(os.path.join(hwmon_dir, "power1_input"), "w") as f:
            f.write(f"{int(self.power_uw)}\n")

        # Create device/of_node/reg file
        of_node_dir = os.path.join(hwmon_dir, "device", "of_node")
        os.makedirs(of_node_dir, exist_ok=True)
        with open(os.path.join(of_node_dir, "reg"), "wb") as f:
            f.write(address.to_bytes(4, byteorder="big"))

        self.path = hwmon_dir

    def update_voltage(self, voltage_mv: float) -> None:
        """Update the voltage reading."""
        with open(os.path.join(self.path, "in1_input"), "w") as f:
            f.write(f"{int(voltage_mv)}\n")

    def update_current(self, current_ma: float) -> None:
        """Update the current reading."""
        with open(os.path.join(self.path, "curr1_input"), "w") as f:
            f.write(f"{int(current_ma)}\n")


class MockMCP4017:
    """Mock MCP4017 digital potentiometer."""

    MAX_VALUE = 127

    def __init__(self, **kwargs):
        self._step = 0

    def set_step(self, step: int) -> None:
        self._step = max(0, min(step, self.MAX_VALUE))

    def get_step(self) -> int:
        return self._step

    @property
    def step(self) -> int:
        return self._step


class MockGpio:
    """Mock GPIO that doesn't require real gpiod."""

    def __init__(self, consumer: str, pin: object, direction: object):
        self.consumer = consumer
        self.pin = pin
        self.direction = direction
        self._value = 0
        self._initialized = False

    def init(self) -> Optional[str]:
        self._initialized = True
        return None

    def write(self, value) -> Optional[str]:
        if not self._initialized:
            return "GPIO not initialized"
        self._value = 1 if value else 0
        return None

    def read(self) -> tuple[Optional[str], int]:
        if not self._initialized:
            return "GPIO not initialized", 0
        return None, self._value

    def deinit(self) -> Optional[str]:
        self._initialized = False
        return None
