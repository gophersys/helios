"""INA219 current/power monitor driver.

Reads voltage, current, and power from INA219 devices via Linux hwmon sysfs.
Two devices are expected: 0x40 (DUT power) and 0x41 (charger power).
"""

import glob
import os
from typing import Optional

from corekinect.utils import Logger


class INA219:
    """Driver for INA219 current/power monitors via hwmon sysfs."""

    def __init__(self, logger: Logger):
        self.logger = logger
        self.paths: dict[int, str] = {}  # i2c_addr -> hwmon path

        # Scan hwmon devices to find INA219s
        for hwmon in glob.glob("/sys/class/hwmon/hwmon*"):
            try:
                with open(os.path.join(hwmon, "name"), "r") as f:
                    if f.read().strip() != "ina219":
                        continue

                # Read the I2C address from the device tree
                with open(os.path.join(hwmon, "device/of_node/reg"), "rb") as f:
                    reg = int.from_bytes(f.read(), byteorder="big")
                    self.paths[reg] = hwmon
                    self.logger.info(f"Found INA219 at 0x{reg:02X}: {hwmon}")
            except Exception as e:
                self.logger.warning(f"Error checking hwmon device {hwmon}: {e}")
                continue

        if 0x40 not in self.paths or 0x41 not in self.paths:
            self.logger.error("Failed to find both INA219 power monitoring devices")
            raise Exception("Required INA219 power monitoring devices not found")

    def read(self, addr: int) -> tuple[Optional[str], float, float, float]:
        """Read voltage, current, and power from an INA219 device.

        Args:
            addr: I2C address of the INA219 (0x40 or 0x41)

        Returns:
            Tuple of (error, voltage_v, current_ma, power_mw).
            Error is None on success.
        """
        hwmon_path = self.paths.get(addr)
        if not hwmon_path:
            return f"No INA219 found at address 0x{addr:02X}", 0.0, 0.0, 0.0

        try:
            with open(os.path.join(hwmon_path, "in1_input"), "r") as f:
                voltage_v = float(f.read().strip()) / 1000.0  # mV -> V
            with open(os.path.join(hwmon_path, "curr1_input"), "r") as f:
                current_ma = float(f.read().strip())  # already in mA
            with open(os.path.join(hwmon_path, "power1_input"), "r") as f:
                power_mw = float(f.read().strip()) / 1000.0  # uW -> mW
            return None, voltage_v, current_ma, power_mw
        except Exception as e:
            self.logger.error(f"Failed to read INA219 at {hwmon_path}: {e}")
            return str(e), 0.0, 0.0, 0.0
