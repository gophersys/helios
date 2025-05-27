from typing import List, Optional
import grpc
import os
from corekinect.utils import Logger
from src.shared.types import *


class AdcHandler:
    def __init__(self, logger: Logger):
        self.logger = logger
        self.iio_device_path = None

        # Find the AD7689 IIO device
        for device_path in os.listdir("/sys/bus/iio/devices"):
            try:
                with open(f"/sys/bus/iio/devices/{device_path}/name", "r") as f:
                    if f.read().strip() == "ad7689":
                        self.iio_device_path = f"/sys/bus/iio/devices/{device_path}"
                        break
            except Exception:
                continue

        if not self.iio_device_path:
            raise Exception("AD7689 IIO device not found")

        self.logger.info(f"Found AD7689 at {self.iio_device_path}")

        # AD7689 is a 16-bit ADC with 0-4.096V range
        self.max_raw = 65535  # 16-bit max value
        self.max_voltage = 4.096  # Maximum voltage in volts
        self.scale_factor = self.max_voltage / self.max_raw

        # Voltage divider ratio (R1 + R2) / R2
        # For 10k + 20k divider: (10000 + 20000) / 20000 = 1.5
        self.divider_ratio = 1.5
        self.logger.info(f"Using voltage divider ratio: {self.divider_ratio}")

    def _read_raw(self, channel: int) -> tuple[Optional[str], int]:
        """Read raw value from ADC channel."""
        try:
            with open(os.path.join(self.iio_device_path, f"in_voltage{channel}_raw"), "r") as f:
                raw = int(f.read().strip())
                self.logger.debug(f"Raw ADC value for channel {channel}: {raw}")
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
        self.logger.debug(
            f"Channel {request.channel} voltage: {real_voltage:.4f}V "
            f"(raw: {raw_value}, divider: {self.divider_ratio:.2f})"
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
            self.logger.debug(
                f"Channel {channel} voltage: {real_voltage:.4f}V "
                f"(raw: {raw_value}, divider: {self.divider_ratio:.2f})"
            )
            voltages.append(real_voltage)

        return AdcReadAllResponse(success=True, message="", voltages_v=voltages)
