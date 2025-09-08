from typing import List, Optional, Dict
import grpc
import os
import glob
from corekinect.utils import Logger
from src.shared.types import *


class AdcHandler:
    """
    ADC Handler for ADS1015 devices.

    Channel Mapping:
    - Chip 0 (I2C address 0x48): Channels 0-3 (AN0-AN3)
    - Chip 1 (I2C address 0x49): Channels 4-7 (AN0-AN3)

    Direct mapping: When user calls AdcRead channel 0, it reads physical channel 0,
    channel 1 reads physical channel 1, etc., up to channel 7.
    """

    def __init__(self, logger: Logger):
        self.logger = logger
        self.devices: Dict[str, str] = {}  # address -> device_path mapping
        self.scale_factors: Dict[int, float] = {}  # channel -> scale_factor mapping

        # Voltage divider ratio (R1 + R2) / R2
        # For 82k + 33k divider: (82000 + 33000) / 33000 = 115000 / 33000 = 3.48
        self.divider_ratio = 3.48
        self.logger.info(f"Using voltage divider ratio: {self.divider_ratio}")

        # Optimal scale factor for ±6.144V range (recommended for VCC up to 4.75V)
        self.optimal_scale = 0.187500000

        # Find and map ADS1015 devices
        self._discover_ads1015_devices()

        if not self.devices:
            raise Exception("No ADS1015 IIO devices found")

        # Verify we have both required devices
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
            # Scan all IIO devices
            device_dirs = glob.glob("/sys/bus/iio/devices/iio:device*")

            for device_dir in device_dirs:
                try:
                    # Read the device name
                    name_file = os.path.join(device_dir, "name")
                    with open(name_file, "r") as f:
                        device_name = f.read().strip()

                    if device_name == "ads1015":
                        # Read the I2C address from the device path
                        # The path format is: /sys/bus/iio/devices/iio:deviceX -> ../../../devices/platform/soc@0/30800000.bus/30a50000.i2c/i2c-3/3-0048/iio:deviceX
                        # We need to extract the address (0048 or 0049) from the symlink target
                        link_target = os.readlink(device_dir)

                        # Extract I2C address from the path
                        parts = link_target.split("/")
                        for part in parts:
                            if part.startswith("3-") and len(part) == 6:
                                # Extract the address part (last 2 characters, removing leading zeros)
                                address = part[2:]
                                # Remove leading zeros to get 2-character address
                                if len(address) == 4:
                                    address = address[2:]  # Take last 2 characters
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

            # Set optimal scale for this channel
            scale_path = os.path.join(device_path, f"in_voltage{device_channel}_scale")

            try:
                # Write optimal scale factor
                with open(scale_path, "w") as f:
                    f.write(f"{self.optimal_scale:.9f}")

                # Read back the actual scale factor
                with open(scale_path, "r") as f:
                    scale_str = f.read().strip()
                    scale_factor = float(scale_str)
                    self.scale_factors[channel] = scale_factor

                self.logger.info(f"Channel {channel} initialized with scale factor: {scale_factor:.9f} mV/unit")

            except Exception as e:
                self.logger.warning(f"Failed to set scale factor for channel {channel}: {e}")
                # Use default scale factor if setting fails
                self.scale_factors[channel] = self.optimal_scale

    def _get_device_path_for_channel(self, channel: int) -> str:
        """
        Get device path for a given channel.

        Channel mapping:
        - Channels 0-3: Device at I2C address 0x48
        - Channels 4-7: Device at I2C address 0x49
        """
        if 0 <= channel <= 3:
            return self.devices["48"]  # Device 0x48 for channels 0-3
        elif 4 <= channel <= 7:
            return self.devices["49"]  # Device 0x49 for channels 4-7
        else:
            raise ValueError(f"Invalid channel {channel}. Must be between 0 and 7.")

    def _get_device_channel_for_channel(self, channel: int) -> int:
        """
        Get device channel (0-3) for a given logical channel (0-7).

        Each ADS1015 chip has 4 channels (AN0-AN3), so we need to map:
        - Channels 0-3 (device 0x48): map to device channels 0-3
        - Channels 4-7 (device 0x49): map to device channels 0-3
        """
        if 0 <= channel <= 3:
            # Channels 0-3 (device 0x48): map to device channels 0-3
            return channel
        elif 4 <= channel <= 7:
            # Channels 4-7 (device 0x49): map to device channels 0-3
            return channel - 4
        else:
            raise ValueError(f"Invalid channel {channel}. Must be between 0 and 7.")

    def _read_raw(self, channel: int) -> tuple[Optional[str], int]:
        """Read raw value from ADC channel."""
        try:
            device_path = self._get_device_path_for_channel(channel)
            device_channel = self._get_device_channel_for_channel(channel)

            raw_path = os.path.join(device_path, f"in_voltage{device_channel}_raw")
            with open(raw_path, "r") as f:
                raw = int(f.read().strip())
                return None, raw
        except Exception as e:
            return f"Failed to read ADC channel {channel}: {str(e)}", 0

    def _format_voltage(self, voltage: float) -> float:
        """Format voltage to 4 decimal places."""
        return round(voltage, 4)

    def _calculate_real_voltage(self, raw_value: int, channel: int) -> float:
        """Calculate the real voltage after accounting for voltage divider."""
        # Get the scale factor for this specific channel
        scale_factor = self.scale_factors.get(channel, self.optimal_scale)

        # Match Go program logic exactly:
        # 1. Multiply raw value by scale factor to get voltage in mV
        voltage_mV = float(raw_value) * scale_factor

        # 2. Apply voltage divider compensation
        real_voltage_mV = voltage_mV * self.divider_ratio

        # 3. Convert to volts
        voltage_V = real_voltage_mV / 1000.0

        return self._format_voltage(voltage_V)

    def read(self, request: AdcReadRequest, context: grpc.ServicerContext) -> AdcReadResponse:
        """Read a single ADC channel."""
        self.logger.info(f"AdcRead request received for channel {request.channel}")

        if not 0 <= request.channel <= 7:
            return AdcReadResponse(
                success=False,
                message=f"Invalid channel number {request.channel}. Must be between 0 and 7.",
                voltage_v=0.0,
            )

        # Direct mapping: channel 0-7 maps to physical channels 0-7
        physical_channel = request.channel
        self.logger.debug(f"Channel {request.channel} maps to physical channel {physical_channel}")

        err, raw_value = self._read_raw(physical_channel)
        if err:
            return AdcReadResponse(success=False, message=err, voltage_v=0.0)

        real_voltage = self._calculate_real_voltage(raw_value, physical_channel)
        device_path = self._get_device_path_for_channel(physical_channel)

        self.logger.debug(f"Physical channel {physical_channel} voltage: {real_voltage}V (raw: {raw_value})")
        return AdcReadResponse(success=True, message="", voltage_v=real_voltage)

    def read_all(self, request: Empty, context: grpc.ServicerContext) -> AdcReadAllResponse:
        """Read all ADC channels."""
        self.logger.info("AdcReadAll request received")

        voltages = []
        # Read all channels (0-7) with direct mapping
        for channel in range(8):
            self.logger.debug(f"Reading channel {channel}")

            err, raw_value = self._read_raw(channel)
            if err:
                return AdcReadAllResponse(
                    success=False,
                    message=f"Failed to read channel {channel}: {err}",
                    voltages_v=[],
                )
            real_voltage = self._calculate_real_voltage(raw_value, channel)
            voltages.append(real_voltage)

        return AdcReadAllResponse(success=True, message="", voltages_v=voltages)
