"""Power management handler for V2 protocol."""

import glob
import os
import time
from typing import TYPE_CHECKING, Iterator, Optional, Tuple

import gpiod

from corekinect.utils import Logger
from src.services.gpio import Gpio, Pin
from src.services.mcp4017 import MCP4017
from src.shared.types import (
    PowerChannel,
    PowerDisableRequest,
    PowerEnableRequest,
    PowerMeasureRequest,
    PowerMeasureResponse,
    PowerSample,
    PowerStatusRequest,
    PowerStatusResponse,
    PowerStreamRequest,
    PowerStreamResponse,
    Response,
    Timestamp,
)

if TYPE_CHECKING:
    from src.hardware import HardwareContext

# INA219 hwmon channel mapping
# POWER_MAIN (DUT power) -> INA219 @ 0x40
# POWER_VBAT (charge power) -> INA219 @ 0x41
CHANNEL_INA_MAP = {
    PowerChannel.POWER_MAIN: 0x40,
    PowerChannel.POWER_VBAT: 0x41,
}


class PowerHandler:
    """Handles V2 power RPCs."""

    def __init__(self, logger: Logger, hardware: "HardwareContext", power_monitor=None):
        self.logger = logger
        self.hardware = hardware
        self.mcp4017 = MCP4017(logger=logger)
        self._power_monitor = power_monitor  # ObservabilityEngine's PowerMonitor (for cached reads)

        # Discover INA219 hwmon paths
        self._ina_paths: dict[int, str] = {}  # i2c_addr -> hwmon path
        for hwmon in glob.glob("/sys/class/hwmon/hwmon*"):
            try:
                with open(os.path.join(hwmon, "name"), "r") as f:
                    if f.read().strip() != "ina219":
                        continue
                with open(os.path.join(hwmon, "device/of_node/reg"), "rb") as f:
                    reg = int.from_bytes(f.read(), byteorder="big")
                    self._ina_paths[reg] = hwmon
                    self.logger.info(f"Found INA219 at 0x{reg:02X}: {hwmon}")
            except Exception:
                continue

        # Power enable GPIOs
        # DUT_PWR_EN on SODIMM_55, DUT_CHG_EN on SODIMM_53
        self._pwr_en = Gpio(consumer="mtib-dut-pwr-en", pin=Pin.SODIMM_55, direction=gpiod.line.Direction.OUTPUT)
        self._chg_en = Gpio(consumer="mtib-dut-chg-en", pin=Pin.SODIMM_53, direction=gpiod.line.Direction.OUTPUT)

        self._gpio_available = True
        if err := self._pwr_en.init():
            self.logger.warning(f"DUT power enable GPIO not available: {err}")
            self._gpio_available = False
        if err := self._chg_en.init():
            self.logger.warning(f"DUT charge enable GPIO not available: {err}")
            self._gpio_available = False

        # Start with power off
        if self._gpio_available:
            self._pwr_en.write(False)
            self._chg_en.write(False)
        self._pwr_enabled = False
        self._chg_enabled = False

    def _get_ina_path(self, channel: int) -> Optional[str]:
        """Get INA219 hwmon path for a power channel."""
        addr = CHANNEL_INA_MAP.get(channel)
        if addr is None:
            return None
        return self._ina_paths.get(addr)

    def _read_ina219(self, hwmon_path: str) -> Tuple[float, float, float]:
        """Read voltage (V), current (mA), power (mW) from INA219 hwmon."""
        with open(os.path.join(hwmon_path, "in1_input"), "r") as f:
            voltage_v = float(f.read().strip()) / 1000.0
        with open(os.path.join(hwmon_path, "curr1_input"), "r") as f:
            current_ma = float(f.read().strip())
        with open(os.path.join(hwmon_path, "power1_input"), "r") as f:
            power_mw = float(f.read().strip()) / 1000.0  # uW -> mW
        return voltage_v, current_ma, power_mw

    def _set_voltage(self, target_v: float) -> Optional[str]:
        """Set DUT power voltage via MCP4017 with feedback loop.

        Uses binary search across the full MCP4017 range (0-127) with INA219
        voltage feedback. Starts from midpoint like V1 server.
        """
        MAX_ATTEMPTS = 10
        VOLTAGE_TOLERANCE = 0.05
        STEP_DELAY = 0.2

        try:
            # Full-range binary search starting from midpoint
            min_step = 0
            max_step = MCP4017.MAX_VALUE  # 127
            current_step = max_step // 2  # Start at 63

            voltage_v = 0.0
            for _ in range(MAX_ATTEMPTS):
                self.mcp4017.set_step(current_step)
                time.sleep(STEP_DELAY)

                ina_path = self._get_ina_path(PowerChannel.POWER_MAIN)
                if not ina_path:
                    return "DUT power INA219 not found"
                voltage_v, _, _ = self._read_ina219(ina_path)

                if abs(voltage_v - target_v) <= VOLTAGE_TOLERANCE:
                    self.logger.info(f"Voltage set: {voltage_v:.3f}V (target: {target_v}V, step: {current_step})")
                    return None

                # Higher wiper step = higher resistance = lower voltage (MCP4017 is R2)
                if voltage_v > target_v:
                    min_step = current_step
                    current_step = (current_step + max_step + 1) // 2
                else:
                    max_step = current_step
                    current_step = (min_step + current_step) // 2

                if min_step == max_step:
                    break

            return f"Voltage did not converge: {voltage_v:.3f}V (target: {target_v}V)"
        except Exception as e:
            return str(e)

    def enable(self, request: PowerEnableRequest, context) -> Response:
        """Enable power on a channel."""
        try:
            config = request.config
            channel = config.channel

            if channel == PowerChannel.POWER_MAIN:
                if err := self._pwr_en.write(True):
                    return Response(success=False, message=f"GPIO error: {err}")
                self._pwr_enabled = True

                if config.voltage_v > 0:
                    if err := self._set_voltage(config.voltage_v):
                        return Response(success=False, message=f"Voltage error: {err}")

            elif channel == PowerChannel.POWER_VBAT:
                if err := self._chg_en.write(True):
                    return Response(success=False, message=f"GPIO error: {err}")
                self._chg_enabled = True
            else:
                return Response(success=False, message=f"Unsupported channel: {channel}")

            return Response(success=True, message="Power enabled")
        except Exception as e:
            return Response(success=False, message=str(e))

    def disable(self, request: PowerDisableRequest, context) -> Response:
        """Disable power on a channel."""
        try:
            if request.channel == PowerChannel.POWER_MAIN:
                if err := self._pwr_en.write(False):
                    return Response(success=False, message=f"GPIO error: {err}")
                self._pwr_enabled = False
            elif request.channel == PowerChannel.POWER_VBAT:
                if err := self._chg_en.write(False):
                    return Response(success=False, message=f"GPIO error: {err}")
                self._chg_enabled = False
            else:
                return Response(success=False, message=f"Unsupported channel: {request.channel}")

            return Response(success=True, message="Power disabled")
        except Exception as e:
            return Response(success=False, message=str(e))

    def status(self, request: PowerStatusRequest, context) -> PowerStatusResponse:
        """Read power status for a channel.

        Uses the PowerMonitor cache when available (at most 100ms stale at 10Hz)
        to avoid redundant I2C traffic. Falls back to direct hwmon read.
        """
        try:
            # Try cached read from PowerMonitor first (avoids duplicate I2C bus hits)
            channel_idx = 0 if request.channel == PowerChannel.POWER_MAIN else 1
            if self._power_monitor:
                cached = self._power_monitor.get_reading(channel_idx)
                if cached:
                    enabled = (
                        self._pwr_enabled if request.channel == PowerChannel.POWER_MAIN
                        else self._chg_enabled
                    )
                    return PowerStatusResponse(
                        success=True,
                        message="",
                        enabled=enabled,
                        voltage_v=cached["voltage_v"],
                        current_ma=cached["current_ma"],
                        power_mw=cached["power_mw"],
                    )

            # Fallback: direct hwmon read
            ina_path = self._get_ina_path(request.channel)
            if not ina_path:
                return PowerStatusResponse(
                    success=False,
                    message=f"No INA219 for channel {request.channel}",
                )

            voltage_v, current_ma, power_mw = self._read_ina219(ina_path)
            enabled = (
                self._pwr_enabled if request.channel == PowerChannel.POWER_MAIN
                else self._chg_enabled
            )

            return PowerStatusResponse(
                success=True,
                message="",
                enabled=enabled,
                voltage_v=voltage_v,
                current_ma=current_ma,
                power_mw=power_mw,
            )
        except Exception as e:
            return PowerStatusResponse(success=False, message=str(e))

    def stream(self, request: PowerStreamRequest, context) -> Iterator[PowerStreamResponse]:
        """Server-streaming power samples at requested rate."""
        ina_path = self._get_ina_path(request.channel)
        if not ina_path:
            yield PowerStreamResponse(
                success=False,
                message=f"No INA219 for channel {request.channel}",
            )
            return

        sample_rate = max(1, min(request.sample_rate_hz, 1000))
        interval = 1.0 / sample_rate

        self.logger.info(f"Power stream started: channel={request.channel}, rate={sample_rate}Hz")
        try:
            while context.is_active():
                start = time.time()
                try:
                    voltage_v, current_ma, _ = self._read_ina219(ina_path)
                    now = time.time()
                    sample = PowerSample(
                        timestamp=Timestamp(seconds=int(now), nanos=int((now % 1) * 1e9)),
                        current_ua=current_ma * 1000.0,
                        voltage_mv=voltage_v * 1000.0,
                    )
                    yield PowerStreamResponse(success=True, message="", samples=[sample])
                except Exception as e:
                    yield PowerStreamResponse(success=False, message=str(e))

                elapsed = time.time() - start
                sleep_time = interval - elapsed
                if sleep_time > 0:
                    time.sleep(sleep_time)
        finally:
            self.logger.info("Power stream ended")

    def measure(self, request: PowerMeasureRequest, context) -> PowerMeasureResponse:
        """Measure power over a duration and compute statistics."""
        try:
            ina_path = self._get_ina_path(request.channel)
            if not ina_path:
                return PowerMeasureResponse(
                    success=False,
                    message=f"No INA219 for channel {request.channel}",
                )

            sample_rate = max(1, min(request.sample_rate_hz, 1000))
            interval = 1.0 / sample_rate
            duration = request.duration_s
            samples = []

            start_time = time.time()
            while (time.time() - start_time) < duration:
                sample_start = time.time()
                voltage_v, current_ma, _ = self._read_ina219(ina_path)
                now = time.time()
                samples.append(PowerSample(
                    timestamp=Timestamp(seconds=int(now), nanos=int((now % 1) * 1e9)),
                    current_ua=current_ma * 1000.0,
                    voltage_mv=voltage_v * 1000.0,
                ))
                elapsed = time.time() - sample_start
                sleep_time = interval - elapsed
                if sleep_time > 0:
                    time.sleep(sleep_time)

            if not samples:
                return PowerMeasureResponse(success=False, message="No samples collected")

            # Compute statistics
            currents = [s.current_ua for s in samples]
            voltages = [s.voltage_mv for s in samples]
            avg_current = sum(currents) / len(currents)
            min_current = min(currents)
            max_current = max(currents)

            # Energy = sum(V * I * dt) in microjoules
            actual_duration = time.time() - start_time
            dt = actual_duration / len(samples) if samples else 0
            energy_uj = sum(v * i * dt / 1e6 for v, i in zip(voltages, currents))

            return PowerMeasureResponse(
                success=True,
                message="",
                duration_s=actual_duration,
                average_ua=avg_current,
                min_ua=min_current,
                max_ua=max_current,
                energy_uj=energy_uj,
                sample_count=len(samples),
                samples=samples,
            )
        except Exception as e:
            return PowerMeasureResponse(success=False, message=str(e))
