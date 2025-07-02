from typing import List, Optional, Dict
import grpc
import os
from corekinect.utils import Logger
from src.shared.types import *


class AdcHandler:
    def __init__(self, logger: Logger):
        self.logger = logger
        self.ads1015_devices: Dict[int, str] = {}  # channel -> device_path mapping

        # Find and map ADS1015 devices to channels
        self._discover_ads1015_devices()

        if not self.ads1015_devices:
            raise Exception("No ADS1015 IIO devices found")

        self.logger.info(f"Found {len(self.ads1015_devices)} ADS1015 devices: {self.ads1015_devices}")

        # ADS1015 is a 12-bit ADC with programmable gain
        # We'll use the default ±4.096V range
        self.max_raw = 2047  # 12-bit signed max value
        self.max_voltage = 4.096  # Maximum voltage in volts
        self.scale_factor = self.max_voltage / self.max_raw

        # Voltage divider ratio (R1 + R2) / R2
        # For 10k + 20k divider: (10000 + 20000) / 20000 = 1.5
        self.divider_ratio = 1.5
        self.logger.info(f"Using voltage divider ratio: {self.divider_ratio}")

    def _discover_ads1015_devices(self):
        """Discover ADS1015 devices and map them to channels."""
        try:
            # Scan all IIO devices
            for device_path in os.listdir("/sys/bus/iio/devices"):
                device_full_path = f"/sys/bus/iio/devices/{device_path}"

                try:
                    with open(os.path.join(device_full_path, "name"), "r") as f:
                        device_name = f.read().strip()

                    if device_name == "ads1015":
                        # Read the device address to identify which chip this is
                        # We'll use the device number as a proxy for now
                        device_num = int(device_path.replace("iio:device", ""))

                        # Map channels based on device number
                        # Assuming device0 = 0x48 (channels 0-3), device1 = 0x49 (channels 4-7)
                        if device_num == 0:  # First ADS1015 (0x48)
                            for channel in range(4):
                                self.ads1015_devices[channel] = device_full_path
                        elif device_num == 1:  # Second ADS1015 (0x49)
                            for channel in range(4, 8):
                                self.ads1015_devices[channel] = device_full_path
                        elif device_num == 2:  # Third ADS1015 (if present)
                            # This one might be used for other purposes, skip for now
                            self.logger.info(f"Found third ADS1015 at {device_full_path}, skipping")

                except Exception as e:
                    self.logger.debug(f"Error reading device {device_path}: {e}")
                    continue

        except Exception as e:
            self.logger.error(f"Error discovering ADS1015 devices: {e}")

    def _read_raw(self, channel: int) -> tuple[Optional[str], int]:
        """Read raw value from ADC channel."""
        if channel not in self.ads1015_devices:
            return f"Channel {channel} not mapped to any ADS1015 device", 0

        device_path = self.ads1015_devices[channel]

        try:
            # Calculate the channel number within the device (0-3)
            device_channel = channel % 4

            with open(os.path.join(device_path, f"in_voltage{device_channel}_raw"), "r") as f:
                raw = int(f.read().strip())
                self.logger.debug(
                    f"Raw ADC value for channel {channel} (device {device_path}, device_channel {device_channel}): {raw}"
                )
                return None, raw
        except Exception as e:
            return f"Failed to read ADC channel {channel}: {str(e)}", 0

    def _format_voltage(self, voltage: float) -> float:
        """Format voltage to 4 decimal places."""
        return round(voltage, 4)

    def _calculate_real_voltage(self, raw_value: int) -> float:
        """Calculate the real voltage after accounting for voltage divider."""
        measured_voltage = raw_value * self.scale_factor
        real_voltage = measured_voltage * self.divider_ratio
        return self._format_voltage(real_voltage)

    def read(self, request: AdcReadRequest, context: grpc.ServicerContext) -> AdcReadResponse:
        """Read a single ADC channel."""
        self.logger.info(f"AdcRead request received for channel {request.channel}")

        if not 0 <= request.channel <= 7:
            return AdcReadResponse(
                success=False,
                message=f"Invalid channel number {request.channel}. Must be between 0 and 7.",
                voltage_v=0.0,
            )

        err, raw_value = self._read_raw(request.channel)
        if err:
            return AdcReadResponse(success=False, message=err, voltage_v=0.0)

        real_voltage = self._calculate_real_voltage(raw_value)
        device_path = self.ads1015_devices.get(request.channel, "unknown")
        self.logger.debug(
            f"Channel {request.channel} voltage: {real_voltage:.4f}V "
            f"(raw: {raw_value}, device: {device_path}, divider: {self.divider_ratio:.2f})"
        )
        return AdcReadResponse(success=True, message="", voltage_v=real_voltage)

    def read_all(self, request: Empty, context: grpc.ServicerContext) -> AdcReadAllResponse:
        """Read all ADC channels."""
        self.logger.info("AdcReadAll request received")

        voltages = []
        for channel in range(8):
            err, raw_value = self._read_raw(channel)
            if err:
                return AdcReadAllResponse(
                    success=False, message=f"Failed to read channel {channel}: {err}", voltages_v=[]
                )
            real_voltage = self._calculate_real_voltage(raw_value)
            device_path = self.ads1015_devices.get(channel, "unknown")
            self.logger.debug(
                f"Channel {channel} voltage: {real_voltage:.4f}V "
                f"(raw: {raw_value}, device: {device_path}, divider: {self.divider_ratio:.2f})"
            )
            voltages.append(real_voltage)

        return AdcReadAllResponse(success=True, message="", voltages_v=voltages)
