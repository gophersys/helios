# Standard library
import time
from typing import Dict, Iterator, Optional

# Third party
import grpc

# Corekinect
from corekinect.utils import Logger

# Proto types
from src.shared.types import (
    AdcReadRequest,
    AdcReadResponse,
    AdcReadAllResponse,
    AdcStreamRequest,
    AdcStreamSample,
    AdcStreamResponse,
    Empty,
    SnapshotAdc,
)

# Drivers
from src.drivers.ads1015 import ADS1015


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
        self._ads1015 = ADS1015(logger)

    def _read_raw(self, channel: int) -> tuple[Optional[str], int]:
        """Read raw value from ADC channel. Delegates to driver."""
        return self._ads1015.read_raw(channel)

    def _calculate_real_voltage(self, raw_value: int, channel: int) -> float:
        """Calculate the real voltage after accounting for voltage divider. Delegates to driver."""
        return self._ads1015.calculate_real_voltage(raw_value, channel)

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

        err, raw_value = self._ads1015.read_raw(physical_channel)
        if err:
            return AdcReadResponse(success=False, message=err, voltage_v=0.0)

        real_voltage = self._ads1015.calculate_real_voltage(raw_value, physical_channel)

        self.logger.debug(f"Physical channel {physical_channel} voltage: {real_voltage}V (raw: {raw_value})")
        return AdcReadResponse(success=True, message="", voltage_v=real_voltage)

    def read_all(self, request: Empty, context: grpc.ServicerContext) -> AdcReadAllResponse:
        """Read all ADC channels."""
        self.logger.info("AdcReadAll request received")

        voltages = []
        # Read all channels (0-7) with direct mapping
        for channel in range(8):
            self.logger.debug(f"Reading channel {channel}")

            err, raw_value = self._ads1015.read_raw(channel)
            if err:
                return AdcReadAllResponse(
                    success=False,
                    message=f"Failed to read channel {channel}: {err}",
                    voltages_v=[],
                )
            real_voltage = self._ads1015.calculate_real_voltage(raw_value, channel)
            voltages.append(real_voltage)

        return AdcReadAllResponse(success=True, message="", voltages_v=voltages)

    def stream(self, request: AdcStreamRequest, context: grpc.ServicerContext) -> Iterator[AdcStreamResponse]:
        """Server-streaming ADC samples at specified interval (V2 RPC)."""
        channels = list(request.channels) if request.channels else list(range(8))
        interval_ms = request.interval_ms if request.interval_ms > 0 else 100
        interval_s = interval_ms / 1000.0

        self.logger.info(f"AdcStream started: channels={channels}, interval={interval_ms}ms")
        start_time = time.time()

        try:
            while context.is_active():
                loop_start = time.time()
                samples = []

                for channel in channels:
                    if not (0 <= channel <= 7):
                        continue
                    err, raw_value = self._ads1015.read_raw(channel)
                    if err:
                        continue
                    real_voltage = self._ads1015.calculate_real_voltage(raw_value, channel)
                    elapsed_ms = int((time.time() - start_time) * 1000)
                    samples.append(AdcStreamSample(
                        timestamp_ms=elapsed_ms,
                        channel=channel,
                        voltage_v=real_voltage,
                    ))

                if samples:
                    yield AdcStreamResponse(samples=samples)

                elapsed = time.time() - loop_start
                sleep_time = interval_s - elapsed
                if sleep_time > 0:
                    time.sleep(sleep_time)
        except Exception as e:
            self.logger.error(f"AdcStream error: {e}")
        finally:
            self.logger.info("AdcStream ended")

    def get_snapshot_data(self) -> list:
        """Return current ADC readings for GetSnapshot."""
        result = []
        for channel in range(8):
            err, raw_value = self._ads1015.read_raw(channel)
            if not err:
                real_voltage = self._ads1015.calculate_real_voltage(raw_value, channel)
                result.append(SnapshotAdc(channel=channel, voltage_v=real_voltage))
        return result
