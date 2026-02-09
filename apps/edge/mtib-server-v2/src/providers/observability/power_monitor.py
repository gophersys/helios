"""Background power monitor that continuously samples INA219 sensors via hwmon sysfs."""

import glob
import os
import threading
import time
from typing import TYPE_CHECKING, Dict, List, Optional, Tuple

from corekinect.utils import Logger

if TYPE_CHECKING:
    from src.hardware import HardwareContext

# INA219 I2C address to power channel index
CHANNEL_ADDRESSES = {
    0: 0x40,  # POWER_MAIN (DUT)
    1: 0x41,  # POWER_VBAT (charge)
}


class PowerMonitor:
    """Background daemon thread that continuously reads INA219 power monitors.

    Samples voltage, current, and power from hwmon sysfs at the configured rate
    and caches the latest readings for instant retrieval.
    """

    def __init__(self, logger: Logger, hardware: "HardwareContext", sample_rate_hz: float = 10):
        self.logger = logger
        self.hardware = hardware
        self._sample_rate_hz = max(1, min(sample_rate_hz, 100))
        self._interval = 1.0 / self._sample_rate_hz

        self._readings: Dict[int, dict] = {}
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

        # Discover INA219 hwmon paths
        self._ina_paths: Dict[int, str] = {}  # channel -> hwmon path
        self._discover_ina219()

    def _discover_ina219(self) -> None:
        """Scan /sys/class/hwmon for INA219 devices and map them to channels."""
        for hwmon in glob.glob("/sys/class/hwmon/hwmon*"):
            try:
                with open(os.path.join(hwmon, "name"), "r") as f:
                    if f.read().strip() != "ina219":
                        continue
                with open(os.path.join(hwmon, "device/of_node/reg"), "rb") as f:
                    reg = int.from_bytes(f.read(), byteorder="big")

                # Map I2C address to channel index
                for channel, addr in CHANNEL_ADDRESSES.items():
                    if reg == addr:
                        self._ina_paths[channel] = hwmon
                        self.logger.info(f"PowerMonitor: Found INA219 ch{channel} at 0x{reg:02X}: {hwmon}")
            except Exception:
                continue

        if not self._ina_paths:
            self.logger.warning("PowerMonitor: No INA219 devices found — power monitoring disabled")

    def _read_ina219(self, hwmon_path: str) -> Tuple[float, float, float]:
        """Read voltage (V), current (mA), power (mW) from INA219 hwmon."""
        with open(os.path.join(hwmon_path, "in1_input"), "r") as f:
            voltage_v = float(f.read().strip()) / 1000.0
        with open(os.path.join(hwmon_path, "curr1_input"), "r") as f:
            current_ma = float(f.read().strip())
        with open(os.path.join(hwmon_path, "power1_input"), "r") as f:
            power_mw = float(f.read().strip()) / 1000.0  # uW -> mW
        return voltage_v, current_ma, power_mw

    def _sample_loop(self) -> None:
        """Continuously sample all INA219 channels."""
        while not self._stop.is_set():
            start = time.time()
            for channel, hwmon_path in self._ina_paths.items():
                try:
                    voltage_v, current_ma, power_mw = self._read_ina219(hwmon_path)
                    now = time.time()
                    reading = {
                        "channel": channel,
                        "voltage_v": voltage_v,
                        "current_ma": current_ma,
                        "power_mw": power_mw,
                        "enabled": current_ma > 1.0,
                        "timestamp": now,
                    }
                    with self._lock:
                        self._readings[channel] = reading
                except Exception as e:
                    self.logger.warning(f"PowerMonitor: Read error on ch{channel}: {e}")

            elapsed = time.time() - start
            sleep_time = self._interval - elapsed
            if sleep_time > 0:
                self._stop.wait(sleep_time)

    def start(self) -> None:
        """Start the background sampling thread."""
        if self._thread is not None and self._thread.is_alive():
            return
        if not self._ina_paths:
            return

        self._stop.clear()
        self._thread = threading.Thread(
            target=self._sample_loop, daemon=True, name="power-monitor"
        )
        self._thread.start()
        self.logger.info(f"PowerMonitor: Started at {self._sample_rate_hz}Hz")

    def stop(self) -> None:
        """Stop the background sampling thread."""
        self._stop.set()
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        self._thread = None
        self.logger.info("PowerMonitor: Stopped")

    def get_reading(self, channel: int) -> Optional[dict]:
        """Return the latest cached reading for a channel, or None."""
        with self._lock:
            return self._readings.get(channel)

    def get_all_readings(self) -> List[dict]:
        """Return latest cached readings for all channels."""
        with self._lock:
            return list(self._readings.values())
