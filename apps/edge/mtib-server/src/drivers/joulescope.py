"""Joulescope JS220 USB power analyzer driver.

Auto-detects a Joulescope on the USB bus and provides single-shot reads
and statistics collection. The device is optional — all methods return
errors gracefully when no Joulescope is connected.

    driver = JoulescopeDriver(logger)
    if driver.scan():
        driver.open()
        err, voltage_v, current_a, power_w = driver.read()
"""

import threading
from typing import Dict, Optional, Tuple

from corekinect.utils import Logger

# Optional import — server runs fine without it
try:
    import joulescope
    _HAS_JOULESCOPE = True
except ImportError:
    joulescope = None
    _HAS_JOULESCOPE = False

try:
    import numpy as np
    _HAS_NUMPY = True
except ImportError:
    np = None
    _HAS_NUMPY = False


class JoulescopeDriver:
    """Thread-safe Joulescope JS220 driver with USB auto-detection."""

    def __init__(self, logger: Logger):
        self.logger = logger.from_parent("joulescope") if hasattr(logger, "from_parent") else logger
        self._device = None
        self._connected = False
        self._serial = None
        self._lock = threading.Lock()

        if not _HAS_JOULESCOPE:
            self.logger.info("pyjoulescope_driver not installed — Joulescope support disabled")
        if not _HAS_NUMPY:
            self.logger.info("numpy not installed — Joulescope support disabled")

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def serial_number(self) -> Optional[str]:
        return self._serial

    def scan(self) -> bool:
        """Scan USB for a Joulescope JS220. Returns True if found."""
        if not _HAS_JOULESCOPE:
            return False

        with self._lock:
            try:
                devices = joulescope.scan()
                if not devices:
                    return False

                self._device = devices[0]
                self._serial = getattr(self._device, "serial_number", None)
                self.logger.info("Found Joulescope: %s", self._serial)
                return True
            except Exception as e:
                self.logger.warning("Joulescope scan failed: %s", e)
                self._device = None
                return False

    def open(self) -> Optional[str]:
        """Open the device for reading. Returns error string or None."""
        with self._lock:
            if self._device is None:
                return "No device found — call scan() first"

            try:
                self._device.open()
                # Configure for current+voltage measurement
                try:
                    self._device.parameter_set("i_range", "auto")
                    self._device.parameter_set("v_range", "15V")
                except Exception:
                    pass  # Some devices don't support all parameters

                self._connected = True
                self.logger.info("Joulescope opened: %s", self._serial)
                return None
            except Exception as e:
                self._connected = False
                self.logger.error("Failed to open Joulescope: %s", e)
                return str(e)

    def close(self) -> None:
        """Close the device. Safe to call when not connected."""
        with self._lock:
            self._connected = False
            if self._device is not None:
                try:
                    self._device.close()
                except Exception as e:
                    self.logger.warning("Joulescope close error: %s", e)

    def read(self, duration: float = 0.01) -> Tuple[Optional[str], float, float, float]:
        """Single-shot read returning (error, voltage_v, current_a, power_w).

        Args:
            duration: Capture window in seconds (default 10ms for a quick snapshot).
        """
        with self._lock:
            if not self._connected or self._device is None:
                return "Joulescope not connected", 0.0, 0.0, 0.0

            try:
                # read() returns Nx2 ndarray with columns [current_a, voltage_v]
                data = self._device.read(duration=duration, out_format="calibrated")

                if data is None or len(data) == 0:
                    return "No samples returned", 0.0, 0.0, 0.0

                # Average all samples in the window
                current_a = float(np.mean(data[:, 0]))
                voltage_v = float(np.mean(data[:, 1]))
                power_w = current_a * voltage_v

                return None, voltage_v, current_a, power_w
            except Exception as e:
                self._connected = False
                self.logger.error("Joulescope read failed: %s", e)
                return str(e), 0.0, 0.0, 0.0

    def read_statistics(self, duration_s: float) -> Tuple[Optional[str], Optional[Dict]]:
        """Collect samples over a duration and return statistics.

        Returns (error, stats_dict) where stats_dict has:
            average_a, min_a, max_a, average_v, sample_count, duration_s
        """
        with self._lock:
            if not self._connected or self._device is None:
                return "Joulescope not connected", None

            try:
                data = self._device.read(duration=duration_s, out_format="calibrated")

                if data is None or len(data) == 0:
                    return "No samples returned", None

                currents = data[:, 0]
                voltages = data[:, 1]

                stats = {
                    "average_a": float(np.mean(currents)),
                    "min_a": float(np.min(currents)),
                    "max_a": float(np.max(currents)),
                    "average_v": float(np.mean(voltages)),
                    "sample_count": len(data),
                    "duration_s": duration_s,
                }
                return None, stats
            except Exception as e:
                self._connected = False
                self.logger.error("Joulescope statistics failed: %s", e)
                return str(e), None
