"""ADC observer for ADS1115 devices — reads all 8 channels via sysfs IIO interface."""

import glob
import os
from typing import Dict, List

from corekinect.utils import Logger


class AdcObserver:
    """Reads ADC channels from two ADS1115 devices (0x48 and 0x49) via sysfs.

    Channel Mapping:
    - Chip 0 (I2C address 0x48): Channels 0-3
    - Chip 1 (I2C address 0x49): Channels 4-7

    Applies voltage divider compensation and scale factor to produce
    real voltage readings.
    """

    def __init__(self, logger: Logger):
        self.logger = logger
        self.devices: Dict[str, str] = {}  # address -> device_path mapping
        self.scale_factors: Dict[int, float] = {}  # channel -> scale_factor mapping

        # Voltage divider ratio (R1 + R2) / R2
        # For 82k + 33k divider: (82000 + 33000) / 33000 = 3.48
        self.divider_ratio = 3.48

        # Optimal scale factor for +/-6.144V range
        self.optimal_scale = 0.187500000

        self._warned_no_devices = False

        # Discover and initialize
        self._discover_devices()

        if self.devices:
            self._initialize_scale_factors()
            self.logger.info(f"AdcObserver: Found {len(self.devices)} ADS1115 device(s)")
        else:
            self.logger.warning("AdcObserver: No ADS1115 IIO devices found — ADC readings will be empty")
            self._warned_no_devices = True

    def _discover_devices(self) -> None:
        """Discover ADS1115 devices by scanning sysfs IIO directory."""
        try:
            device_dirs = glob.glob("/sys/bus/iio/devices/iio:device*")

            for device_dir in device_dirs:
                try:
                    name_file = os.path.join(device_dir, "name")
                    with open(name_file, "r") as f:
                        device_name = f.read().strip()

                    if device_name in ("ads1115", "ads1015"):
                        link_target = os.readlink(device_dir)
                        parts = link_target.split("/")
                        for part in parts:
                            if part.startswith("3-") and len(part) == 6:
                                address = part[2:]
                                if len(address) == 4:
                                    address = address[2:]
                                self.devices[address] = device_dir
                                self.logger.info(
                                    f"AdcObserver: Found {device_name} at 0x{address}: {device_dir}"
                                )
                                break
                except Exception as e:
                    self.logger.debug(f"AdcObserver: Error reading device {device_dir}: {e}")
                    continue

        except Exception as e:
            self.logger.error(f"AdcObserver: Error discovering IIO devices: {e}")

    def _initialize_scale_factors(self) -> None:
        """Initialize scale factors for all available channels."""
        for channel in range(8):
            try:
                device_path = self._get_device_path(channel)
            except ValueError:
                continue

            device_channel = channel % 4
            scale_path = os.path.join(device_path, f"in_voltage{device_channel}_scale")

            try:
                with open(scale_path, "w") as f:
                    f.write(f"{self.optimal_scale:.9f}")

                with open(scale_path, "r") as f:
                    self.scale_factors[channel] = float(f.read().strip())
            except Exception:
                self.scale_factors[channel] = self.optimal_scale

    def _get_device_path(self, channel: int) -> str:
        """Get sysfs device path for a given logical channel (0-7).

        Args:
            channel: Logical channel number (0-7).

        Returns:
            Sysfs device path string.

        Raises:
            ValueError: If the channel is invalid or the device is not found.
        """
        if 0 <= channel <= 3:
            key = "48"
        elif 4 <= channel <= 7:
            key = "49"
        else:
            raise ValueError(f"Invalid channel {channel}. Must be 0-7.")

        if key not in self.devices:
            raise ValueError(f"ADC device at 0x{key} not found")

        return self.devices[key]

    def _read_raw(self, channel: int) -> float:
        """Read raw ADC count from a channel.

        Args:
            channel: Logical channel number (0-7).

        Returns:
            Raw ADC count as float.
        """
        device_path = self._get_device_path(channel)
        device_channel = channel % 4
        raw_path = os.path.join(device_path, f"in_voltage{device_channel}_raw")

        with open(raw_path, "r") as f:
            return float(f.read().strip())

    def _calculate_voltage(self, raw_value: float, channel: int) -> float:
        """Calculate compensated voltage from raw ADC value.

        Args:
            raw_value: Raw ADC count.
            channel: Logical channel number (0-7).

        Returns:
            Voltage in volts after divider compensation.
        """
        scale = self.scale_factors.get(channel, self.optimal_scale)
        voltage_mv = raw_value * scale
        real_voltage_mv = voltage_mv * self.divider_ratio
        return round(real_voltage_mv / 1000.0, 4)

    def get_all_readings(self) -> List[dict]:
        """Read all 8 ADC channels and return compensated voltage readings.

        Returns:
            List of dicts with keys: channel (int), voltage_v (float), raw_value (float).
            Returns empty list if ADC devices are not available.
        """
        if not self.devices:
            if not self._warned_no_devices:
                self.logger.warning("AdcObserver: No ADC devices available")
                self._warned_no_devices = True
            return []

        readings: List[dict] = []
        for channel in range(8):
            try:
                raw_value = self._read_raw(channel)
                voltage_v = self._calculate_voltage(raw_value, channel)
                readings.append({
                    "channel": channel,
                    "voltage_v": voltage_v,
                    "raw_value": raw_value,
                })
            except Exception as e:
                self.logger.debug(f"AdcObserver: Failed to read channel {channel}: {e}")
                readings.append({
                    "channel": channel,
                    "voltage_v": 0.0,
                    "raw_value": 0.0,
                })

        return readings
