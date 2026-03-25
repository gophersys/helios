# Standard library
import glob
import os
import struct
import threading
import time
from typing import Dict, Iterator, Optional, Tuple

# Third party
import gpiod
import grpc

# Corekinect
from corekinect.utils import Logger

# Proto types
from src.shared.types import (
    PowerChannel,
    PowerResponse,
    PowerEnableRequest,
    PowerDisableRequest,
    PowerReadRequest,
    PowerReadResponse,
    PowerMeasureRequest,
    PowerMeasureResponse,
    PowerSample,
    PowerStreamRequest,
    PowerStreamResponse,
    SnapshotPower,
)

# Drivers
from src.drivers.gpio import Gpio, Pin
from src.drivers.ina219 import INA219
from src.drivers.mcp4017 import MCP4017

# Shared
from src.shared.streaming import BatchConfig, BatchStrategy, StreamBroadcaster


# INA219 I2C address mapping per power channel
_CHANNEL_INA_ADDR = {
    PowerChannel.POWER_CHANNEL_DUT: 0x40,
    PowerChannel.POWER_CHANNEL_CHARGER: 0x41,
}

# Voltage bounds for hardware protection
_MIN_VOLTAGE_V = 0.0
_MAX_VOLTAGE_V = 5.5


class PowerHandler:
    def __init__(self, logger: Logger, mcp4017: MCP4017):
        self.logger = logger
        self.mcp4017 = mcp4017
        self._ina219 = INA219(logger)

        # We use GPIOs to control the power to the DUT and the charging power to the DUT.
        self.dut_pwr_en = Gpio(consumer="mtib-dut-pwr-en", pin=Pin.SODIMM_55, direction=gpiod.line.Direction.OUTPUT)
        if err := self.dut_pwr_en.init():
            self.logger.error(f"Failed to initialize DUT power enable GPIO: {err}")
            raise Exception(err)

        self.dut_chg_en = Gpio(consumer="mtib-dut-chg-en", pin=Pin.SODIMM_53, direction=gpiod.line.Direction.OUTPUT)
        if err := self.dut_chg_en.init():
            self.logger.error(f"Failed to initialize DUT charge power enable GPIO: {err}")
            raise Exception(err)

        # Turn off the DUT power and charging power
        if err := self.dut_pwr_en.write(False):
            self.logger.error(f"Failed to disable DUT power: {err}")
            raise Exception(err)

        if err := self.dut_chg_en.write(False):
            self.logger.error(f"Failed to disable DUT charging power: {err}")
            raise Exception(err)

        # Track enable state
        self._pwr_enabled = False
        self._chg_enabled = False

        # Multi-subscriber power streaming
        self._power_broadcasters: Dict[int, StreamBroadcaster] = {}
        self._broadcaster_lock = threading.Lock()

    # -------------------------------------------------
    #                           Internal helpers
    # -------------------------------------------------

    def _get_ina_addr(self, channel: int) -> Optional[int]:
        """Get INA219 I2C address for a power channel enum value."""
        return _CHANNEL_INA_ADDR.get(channel)

    def _read_ina219(self, addr: int) -> Tuple[Optional[str], float, float, float]:
        """Read voltage (V), current (mA), power (mW) from INA219.

        Returns (error, voltage_v, current_ma, power_mw). Error is None on success.
        """
        return self._ina219.read(addr)

    def _get_en_gpio(self, channel: int) -> Tuple[Gpio, str]:
        """Get the enable GPIO and label for a channel."""
        if channel == PowerChannel.POWER_CHANNEL_DUT:
            return self.dut_pwr_en, "DUT"
        else:
            return self.dut_chg_en, "charger"

    def _is_enabled(self, channel: int) -> bool:
        if channel == PowerChannel.POWER_CHANNEL_DUT:
            return self._pwr_enabled
        return self._chg_enabled

    def _set_enabled(self, channel: int, val: bool):
        if channel == PowerChannel.POWER_CHANNEL_DUT:
            self._pwr_enabled = val
        else:
            self._chg_enabled = val

    def _read_adc_voltage(self) -> Tuple[Optional[float], Optional[str]]:
        """Read voltage from INA219 at DUT address (for feedback loop)."""
        try:
            err, voltage_v, _, _ = self._ina219.read(0x40)
            if err:
                return None, err
            return voltage_v, None
        except Exception as e:
            self.logger.error(f"Error reading ADC voltage: {e}")
            return None, str(e)

    def _set_dut_power_voltage(self, target_voltage_v: float) -> Optional[str]:
        """Set the DUT power voltage by adjusting the MCP4017 wiper potentiometer."""
        try:
            MAX_ATTEMPTS = 10
            VOLTAGE_TOLERANCE = 0.05
            STEP_DELAY = 0.2

            min_step = 0
            max_step = MCP4017.MAX_VALUE
            current_step = int(max_step / 2)

            for _ in range(MAX_ATTEMPTS):
                self.mcp4017.set_step(current_step)
                time.sleep(STEP_DELAY)

                current_voltage_v, error = self._read_adc_voltage()
                if error or current_voltage_v is None:
                    return error

                if abs(current_voltage_v - target_voltage_v) <= VOLTAGE_TOLERANCE:
                    self.logger.info(f"Voltage control achieved: {current_voltage_v}V (target: {target_voltage_v}V)")
                    return None

                if current_voltage_v > target_voltage_v:
                    min_step = current_step
                    current_step = (current_step + max_step + 1) // 2
                else:
                    max_step = current_step
                    current_step = (min_step + current_step) // 2

                if min_step == max_step:
                    break

            final_voltage = current_voltage_v
            self.logger.warning(
                f"Voltage control did not converge: final={final_voltage}V, target={target_voltage_v}V"
            )
            return f"Could not achieve target voltage. Final voltage: {final_voltage}V"

        except Exception as e:
            self.logger.error(f"Error in voltage control: {e}")
            return str(e)

    # -------------------------------------------------
    #                        Power RPCs
    # -------------------------------------------------

    def power_enable(self, request: PowerEnableRequest, context: grpc.ServicerContext) -> PowerResponse:
        """Enable power on a channel."""
        self.logger.info(f"PowerEnable: channel={request.channel}, voltage={request.voltage_v}V")

        # Bounds check voltage before setting power
        if request.voltage_v < _MIN_VOLTAGE_V or request.voltage_v > _MAX_VOLTAGE_V:
            return PowerResponse(
                success=False,
                message=f"Voltage {request.voltage_v}V out of safe range ({_MIN_VOLTAGE_V}-{_MAX_VOLTAGE_V}V)"
            )

        try:
            gpio, label = self._get_en_gpio(request.channel)
            if err := gpio.write(True):
                return PowerResponse(success=False, message=f"Error enabling {label} power: {err}")
            self._set_enabled(request.channel, True)

            # Set voltage only for DUT channel
            if request.channel == PowerChannel.POWER_CHANNEL_DUT and request.voltage_v > 0:
                if err := self._set_dut_power_voltage(request.voltage_v):
                    return PowerResponse(success=False, message=f"Error setting voltage: {err}")

            return PowerResponse(success=True, message=f"{label} power enabled")
        except Exception as e:
            return PowerResponse(success=False, message=str(e))

    def power_disable(self, request: PowerDisableRequest, context: grpc.ServicerContext) -> PowerResponse:
        """Disable power on a channel ."""
        self.logger.info(f"PowerDisable: channel={request.channel}")
        try:
            gpio, label = self._get_en_gpio(request.channel)
            if err := gpio.write(False):
                return PowerResponse(success=False, message=f"Error disabling {label} power: {err}")
            self._set_enabled(request.channel, False)
            return PowerResponse(success=True, message=f"{label} power disabled")
        except Exception as e:
            return PowerResponse(success=False, message=str(e))

    def power_read(self, request: PowerReadRequest, context: grpc.ServicerContext) -> PowerReadResponse:
        """Read power status for a channel ."""
        self.logger.info(f"PowerRead: channel={request.channel}")
        try:
            addr = self._get_ina_addr(request.channel)
            if addr is None:
                return PowerReadResponse(success=False, message=f"No INA219 for channel {request.channel}")

            err, voltage_v, current_ma, power_mw = self._read_ina219(addr)
            if err:
                return PowerReadResponse(success=False, message=f"Failed to read INA219: {err}")
            return PowerReadResponse(
                success=True,
                enabled=self._is_enabled(request.channel),
                voltage_v=voltage_v,
                current_ma=current_ma,
                power_mw=power_mw,
            )
        except Exception as e:
            return PowerReadResponse(success=False, message=str(e))

    def power_measure(self, request: PowerMeasureRequest, context: grpc.ServicerContext) -> PowerMeasureResponse:
        """Measure power over a duration and compute statistics ."""
        self.logger.info(f"PowerMeasure: channel={request.channel}, duration={request.duration_s}s")
        try:
            addr = self._get_ina_addr(request.channel)
            if addr is None:
                return PowerMeasureResponse(success=False, message=f"No INA219 for channel {request.channel}")

            currents_ma = []
            voltages_mv = []
            start_time = time.time()

            while (time.time() - start_time) < request.duration_s:
                if not context.is_active():
                    break
                err, voltage_v, current_ma, _ = self._read_ina219(addr)
                if err:
                    continue  # skip bad samples, keep collecting
                currents_ma.append(current_ma)
                voltages_mv.append(voltage_v * 1000.0)
                time.sleep(0.01)  # ~100 Hz max sample rate

            if not currents_ma:
                return PowerMeasureResponse(success=False, message="No samples collected")

            actual_duration = time.time() - start_time
            return PowerMeasureResponse(
                success=True,
                duration_s=actual_duration,
                average_ma=sum(currents_ma) / len(currents_ma),
                min_ma=min(currents_ma),
                max_ma=max(currents_ma),
                average_mv=sum(voltages_mv) / len(voltages_mv),
                sample_count=len(currents_ma),
            )
        except Exception as e:
            self.logger.error(f"PowerMeasure error: {e}")
            return PowerMeasureResponse(success=False, message=str(e))

    def _get_or_create_broadcaster(self, channel: int) -> StreamBroadcaster:
        """Get or create a power stream broadcaster for a channel.

        Uses lazy initialization - broadcaster is only started when
        the first subscriber connects.
        """
        with self._broadcaster_lock:
            if channel in self._power_broadcasters:
                broadcaster = self._power_broadcasters[channel]
                if broadcaster.running:
                    return broadcaster
                # Broadcaster stopped, recreate it
                del self._power_broadcasters[channel]

            # Create new broadcaster with timeout-based batching
            batch_config = BatchConfig(
                strategy=BatchStrategy.TIMEOUT_OR_BYTES,
                max_bytes=4096,
                timeout_ms=10,  # Batch samples every 10ms
            )
            broadcaster = StreamBroadcaster(
                name=f"power-ch{channel}",
                logger=self.logger,
                batch_config=batch_config,
            )

            addr = self._get_ina_addr(channel)
            if addr is None:
                raise ValueError(f"No INA219 for channel {channel}")

            start_time = time.time()

            def read_power() -> Optional[bytes]:
                err, voltage_v, current_ma, _ = self._read_ina219(addr)
                if err:
                    time.sleep(0.1)
                    return None

                elapsed_ms = int((time.time() - start_time) * 1000)
                # Pack sample as binary: timestamp(4), voltage_mv(4), current_ma(4)
                data = struct.pack(
                    "<iff", elapsed_ms, voltage_v * 1000.0, current_ma
                )
                time.sleep(0.01)  # ~100 Hz sample rate
                return data

            broadcaster.start_with_source(read_power)
            self._power_broadcasters[channel] = broadcaster
            self.logger.info(f"Started power broadcaster for channel {channel}")
            return broadcaster

    def _stop_broadcaster_if_idle(self, channel: int):
        """Stop broadcaster if no subscribers remain."""
        with self._broadcaster_lock:
            if channel in self._power_broadcasters:
                broadcaster = self._power_broadcasters[channel]
                if broadcaster.stats.subscriber_count == 0:
                    broadcaster.stop()
                    del self._power_broadcasters[channel]
                    self.logger.info(f"Stopped idle power broadcaster for channel {channel}")

    def power_stream(self, request: PowerStreamRequest, context: grpc.ServicerContext) -> Iterator[PowerStreamResponse]:
        """Server-streaming power samples until client cancels.

        Uses multi-subscriber broadcasting so multiple clients can
        receive the same power data without duplicating hardware reads.
        """
        addr = self._get_ina_addr(request.channel)
        if addr is None:
            yield PowerStreamResponse(samples=[])
            return

        self.logger.info(f"PowerStream started: channel={request.channel}")
        subscription = None

        try:
            # Get or create broadcaster for this channel
            broadcaster = self._get_or_create_broadcaster(request.channel)
            subscription = broadcaster.subscribe()

            while context.is_active():
                # Get batched samples from broadcaster
                data = subscription.get(timeout=0.1)
                if data:
                    # Unpack binary samples
                    samples = []
                    offset = 0
                    sample_size = 12  # 4 + 4 + 4 bytes
                    while offset + sample_size <= len(data):
                        elapsed_ms, voltage_mv, current_ma = struct.unpack(
                            "<iff", data[offset : offset + sample_size]
                        )
                        samples.append(
                            PowerSample(
                                timestamp_ms=int(elapsed_ms),
                                voltage_mv=voltage_mv,
                                current_ma=current_ma,
                            )
                        )
                        offset += sample_size

                    if samples:
                        yield PowerStreamResponse(samples=samples)

        finally:
            if subscription:
                subscription.unsubscribe()
            self._stop_broadcaster_if_idle(request.channel)
            self.logger.info("PowerStream ended")

    # -------------------------------------------------
    #                    Snapshot helper
    # -------------------------------------------------

    def get_snapshot_data(self) -> list:
        """Return current power readings for GetSnapshot."""
        result = []
        for channel, addr in _CHANNEL_INA_ADDR.items():
            err, voltage_v, current_ma, _ = self._read_ina219(addr)
            if err:
                continue
            result.append(SnapshotPower(
                channel=channel,
                enabled=self._is_enabled(channel),
                voltage_v=voltage_v,
                current_ma=current_ma,
            ))
        return result
