"""ADS1015 12-bit ADC driver.

Reads voltage from ADS1015 devices via Linux IIO sysfs interface.
Two chips are expected: 0x48 (channels 0-3) and 0x49 (channels 4-7).
"""

import glob
import os
from typing import Optional

from corekinect.utils import Logger


class ADS1015:
    """Driver for ADS1015 12-bit ADC via IIO sysfs.

    Channel Mapping:
    - Chip 0 (I2C address 0x48): Channels 0-3 (AN0-AN3)
    - Chip 1 (I2C address 0x49): Channels 4-7 (AN0-AN3)
    """

    def __init__(self, logger: Logger):
        self.logger = logger
        self.devices: dict[str, str] = {}  # address -> device_path mapping
        self.scale_factors: dict[int, float] = {}  # channel -> scale_factor mapping

        # Voltage divider ratio (R1 + R2) / R2
        # For 82k + 33k divider: (82000 + 33000) / 33000 = 115000 / 33000 = 3.48
        self.divider_ratio = 3.48
        self.logger.info(f"Using voltage divider ratio: {self.divider_ratio}")

        # Optimal scale factor for +/-6.144V range (recommended for VCC up to 4.75V)
        self.optimal_scale = 0.187500000

        # Find and map ADS1015 devices
        self._discover_ads1015_devices()

        if not self.devices:
            raise Exception("No ADS1015 IIO devices found")

        if "48" not in self.devices:
            raise Exception("ADC device at address 0x48 not found")
        if "49" not in self.devices:
            raise Exception("ADC device at address 0x49 not found")

        self.logger.info(f"Found ADS1015 devices: 0x48 -> {self.devices['48']}, 0x49 -> {self.devices['49']}")

        # Initialize scale factors for all channels
        self._initialize_scale_factors()

    def _discover_ads1015_devices(self):
        """Discover ADS1015 devices by I2C address."""
        try:
            device_dirs = glob.glob("/sys/bus/iio/devices/iio:device*")

            for device_dir in device_dirs:
                try:
                    name_file = os.path.join(device_dir, "name")
                    with open(name_file, "r") as f:
                        device_name = f.read().strip()

                    if device_name == "ads1015":
                        link_target = os.readlink(device_dir)
                        parts = link_target.split("/")
                        for part in parts:
                            if part.startswith("3-") and len(part) == 6:
                                address = part[2:]
                                if len(address) == 4:
                                    address = address[2:]
                                self.devices[address] = device_dir
                                self.logger.info(f"Found ADS1015 device at address 0x{address}: {device_dir}")
                                break

                except Exception as e:
                    self.logger.debug(f"Error reading device {device_dir}: {e}")
                    continue

        except Exception as e:
            self.logger.error(f"Error discovering ADS1015 devices: {e}")

    def _initialize_scale_factors(self):
        """Initialize scale factors for all channels by writing optimal scale and reading back."""
        for channel in range(8):
            device_path = self._get_device_path_for_channel(channel)
            device_channel = self._get_device_channel_for_channel(channel)

            scale_path = os.path.join(device_path, f"in_voltage{device_channel}_scale")

            try:
                with open(scale_path, "w") as f:
                    f.write(f"{self.optimal_scale:.9f}")

                with open(scale_path, "r") as f:
                    scale_str = f.read().strip()
                    scale_factor = float(scale_str)
                    self.scale_factors[channel] = scale_factor

                self.logger.info(f"Channel {channel} initialized with scale factor: {scale_factor:.9f} mV/unit")

            except Exception as e:
                self.logger.warning(f"Failed to set scale factor for channel {channel}: {e}")
                self.scale_factors[channel] = self.optimal_scale

    def _get_device_path_for_channel(self, channel: int) -> str:
        """Get device path for a given channel.

        Channels 0-3: Device at I2C address 0x48
        Channels 4-7: Device at I2C address 0x49
        """
        if 0 <= channel <= 3:
            return self.devices["48"]
        elif 4 <= channel <= 7:
            return self.devices["49"]
        else:
            raise ValueError(f"Invalid channel {channel}. Must be between 0 and 7.")

    def _get_device_channel_for_channel(self, channel: int) -> int:
        """Get device channel (0-3) for a given logical channel (0-7)."""
        if 0 <= channel <= 3:
            return channel
        elif 4 <= channel <= 7:
            return channel - 4
        else:
            raise ValueError(f"Invalid channel {channel}. Must be between 0 and 7.")

    def _calculate_real_voltage(self, raw_value: int, channel: int) -> float:
        """Calculate the real voltage after accounting for voltage divider."""
        scale_factor = self.scale_factors.get(channel, self.optimal_scale)
        voltage_mV = float(raw_value) * scale_factor
        real_voltage_mV = voltage_mV * self.divider_ratio
        voltage_V = real_voltage_mV / 1000.0
        return round(voltage_V, 4)

    def read_raw(self, channel: int) -> tuple[Optional[str], int]:
        """Read raw value from ADC channel.

        Args:
            channel: Logical channel number (0-7)

        Returns:
            Tuple of (error, raw_value). Error is None on success.
        """
        try:
            device_path = self._get_device_path_for_channel(channel)
            device_channel = self._get_device_channel_for_channel(channel)

            raw_path = os.path.join(device_path, f"in_voltage{device_channel}_raw")
            with open(raw_path, "r") as f:
                raw = int(f.read().strip())
                return None, raw
        except Exception as e:
            return f"Failed to read ADC channel {channel}: {str(e)}", 0

    def read_voltage(self, channel: int) -> tuple[Optional[str], float]:
        """Read voltage from ADC channel.

        Args:
            channel: Logical channel number (0-7)

        Returns:
            Tuple of (error, voltage_v). Error is None on success.
        """
        if not 0 <= channel <= 7:
            return f"Invalid channel number {channel}. Must be between 0 and 7.", 0.0

        err, raw_value = self.read_raw(channel)
        if err:
            return err, 0.0

        voltage = self._calculate_real_voltage(raw_value, channel)
        return None, voltage
