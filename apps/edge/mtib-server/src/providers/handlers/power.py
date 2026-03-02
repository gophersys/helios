# Corekinect imports
import glob
import os
import time
from typing import Iterator, Optional, Tuple

import gpiod

# 3rd party imports
import grpc
from corekinect.utils import Logger
from src.services.mcp4017 import MCP4017

# Private imports
from src.shared.types import *

from .gpio import Gpio, Pin


# INA219 I2C address mapping per power channel
_CHANNEL_INA_ADDR = {
    PowerChannel.POWER_CHANNEL_DUT: 0x40,
    PowerChannel.POWER_CHANNEL_CHARGER: 0x41,
}


class PowerHandler:
    def __init__(self, logger: Logger):
        self.logger = logger
        self.mcp4017 = MCP4017(logger=logger)

        # Find the ADS1015 ADC device
        self.adc_path = None
        for device in glob.glob("/sys/bus/iio/devices/iio:device*"):
            try:
                with open(os.path.join(device, "name"), "r") as f:
                    if f.read().strip() == "ads1015":
                        self.adc_path = device
                        # Read the scale factor for voltage3
                        with open(os.path.join(device, "in_voltage3_scale"), "r") as sf:
                            self.adc_scale = float(sf.read().strip())
                        self.logger.info(f"Found ADS1015 ADC at {device} with scale {self.adc_scale}")
                        break
            except Exception as e:
                self.logger.warning(f"Error checking IIO device {device}: {e}")
                continue

        if not self.adc_path:
            self.logger.error("Failed to find ADS1015 ADC device")
            raise Exception("Required ADS1015 ADC device not found")

        # Voltage divider ratio (actual voltage is 2x the ADC reading)
        self.voltage_divider_ratio = 2.0

        # Initialize INA219 power monitoring devices
        self._ina_paths: dict[int, str] = {}  # i2c_addr -> hwmon path

        # Scan hwmon devices to find our INA219s
        for hwmon in glob.glob("/sys/class/hwmon/hwmon*"):
            try:
                with open(os.path.join(hwmon, "name"), "r") as f:
                    if f.read().strip() != "ina219":
                        continue

                # Read the I2C address from the device tree
                with open(os.path.join(hwmon, "device/of_node/reg"), "rb") as f:
                    reg = int.from_bytes(f.read(), byteorder="big")
                    self._ina_paths[reg] = hwmon
                    self.logger.info(f"Found INA219 at 0x{reg:02X}: {hwmon}")
            except Exception as e:
                self.logger.warning(f"Error checking hwmon device {hwmon}: {e}")
                continue

        if 0x40 not in self._ina_paths or 0x41 not in self._ina_paths:
            self.logger.error("Failed to find both INA219 power monitoring devices")
            raise Exception("Required INA219 power monitoring devices not found")

        # Convenience aliases
        self.power_ina_path = self._ina_paths[0x40]
        self.chg_power_ina_path = self._ina_paths[0x41]

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

    # -------------------------------------------------
    #                           Internal helpers
    # -------------------------------------------------

    def _get_ina_path(self, channel: int) -> Optional[str]:
        """Get INA219 hwmon path for a power channel enum value."""
        addr = _CHANNEL_INA_ADDR.get(channel)
        if addr is None:
            return None
        return self._ina_paths.get(addr)

    def _read_ina219(self, hwmon_path: str) -> Tuple[Optional[str], float, float, float]:
        """Read voltage (V), current (mA), power (mW) from INA219 hwmon.

        Returns (error, voltage_v, current_ma, power_mw). Error is None on success.
        """
        try:
            with open(os.path.join(hwmon_path, "in1_input"), "r") as f:
                voltage_v = float(f.read().strip()) / 1000.0  # mV -> V
            with open(os.path.join(hwmon_path, "curr1_input"), "r") as f:
                current_ma = float(f.read().strip())  # already in mA
            with open(os.path.join(hwmon_path, "power1_input"), "r") as f:
                power_mw = float(f.read().strip()) / 1000.0  # uW -> mW
            return None, voltage_v, current_ma, power_mw
        except Exception as e:
            self.logger.error(f"Failed to read INA219 at {hwmon_path}: {e}")
            return str(e), 0.0, 0.0, 0.0

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
        """Read voltage from ADS1015 ADC channel 3 (for feedback loop)."""
        try:
            with open(os.path.join(self.power_ina_path, "in1_input"), "r") as f:
                voltage_v = float(f.read().strip()) / 1000.0
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
    #                  Legacy V1 RPCs (aliases)
    # -------------------------------------------------

    def dut_power_enable(self, request: DutPowerRequest, context: grpc.ServicerContext) -> DutPowerResponse:
        """Enable DUT power with specified voltage (legacy V1 RPC)."""
        self.logger.info(f"DutPowerEnable request received with voltage {request.voltage_v}V")

        if err := self.dut_pwr_en.write(True):
            return DutPowerResponse(success=False, message=f"Error enabling DUT power: {err}")
        self._pwr_enabled = True

        if err := self._set_dut_power_voltage(request.voltage_v):
            return DutPowerResponse(success=False, message=f"Error setting DUT power voltage: {err}")

        return DutPowerResponse(success=True)

    def dut_power_disable(self, request: Empty, context: grpc.ServicerContext) -> DutPowerResponse:
        """Disable DUT power (legacy V1 RPC)."""
        self.logger.info("DutPowerDisable request received")
        if err := self.dut_pwr_en.write(False):
            return DutPowerResponse(success=False, message=f"Error disabling DUT power: {err}")
        self._pwr_enabled = False
        return DutPowerResponse(success=True)

    def dut_charge_power_enable(self, request: Empty, context: grpc.ServicerContext) -> DutPowerResponse:
        """Enable DUT charging power (legacy V1 RPC)."""
        self.logger.info("DutChargePowerEnable request received")
        if err := self.dut_chg_en.write(True):
            return DutPowerResponse(success=False, message=f"Error enabling DUT charging power: {err}")
        self._chg_enabled = True
        return DutPowerResponse(success=True)

    def dut_charge_power_disable(self, request: Empty, context: grpc.ServicerContext) -> DutPowerResponse:
        """Disable DUT charging power (legacy V1 RPC)."""
        self.logger.info("DutChargePowerDisable request received")
        if err := self.dut_chg_en.write(False):
            return DutPowerResponse(success=False, message=f"Error disabling DUT charging power: {err}")
        self._chg_enabled = False
        return DutPowerResponse(success=True)

    def dut_power_read(self, request: Empty, context: grpc.ServicerContext) -> DutPowerReadResponse:
        """Read DUT power measurements (legacy V1 RPC)."""
        self.logger.info("DutPowerRead request received")
        err, voltage_v, current_ma, power_mw = self._read_ina219(self.power_ina_path)
        if err:
            return DutPowerReadResponse(success=False, message=f"Error reading power measurements: {err}")
        return DutPowerReadResponse(
            success=True,
            current_a=current_ma / 1000.0,
            voltage_v=voltage_v,
            power_w=power_mw / 1000.0,
        )

    def dut_charge_power_read(self, request: Empty, context: grpc.ServicerContext) -> DutPowerReadResponse:
        """Read DUT charging power measurements (legacy V1 RPC)."""
        self.logger.info("DutChargePowerRead request received")
        err, voltage_v, current_ma, power_mw = self._read_ina219(self.chg_power_ina_path)
        if err:
            return DutPowerReadResponse(success=False, message=f"Error reading charging power measurements: {err}")
        return DutPowerReadResponse(
            success=True,
            current_a=current_ma / 1000.0,
            voltage_v=voltage_v,
            power_w=power_mw / 1000.0,
        )

    # -------------------------------------------------
    #                       V2 unified RPCs
    # -------------------------------------------------

    def power_enable(self, request: PowerEnableRequest, context: grpc.ServicerContext) -> DutPowerResponse:
        """Enable power on a channel (V2 unified RPC)."""
        self.logger.info(f"PowerEnable: channel={request.channel}, voltage={request.voltage_v}V")
        try:
            gpio, label = self._get_en_gpio(request.channel)
            if err := gpio.write(True):
                return DutPowerResponse(success=False, message=f"Error enabling {label} power: {err}")
            self._set_enabled(request.channel, True)

            # Set voltage only for DUT channel
            if request.channel == PowerChannel.POWER_CHANNEL_DUT and request.voltage_v > 0:
                if err := self._set_dut_power_voltage(request.voltage_v):
                    return DutPowerResponse(success=False, message=f"Error setting voltage: {err}")

            return DutPowerResponse(success=True, message=f"{label} power enabled")
        except Exception as e:
            return DutPowerResponse(success=False, message=str(e))

    def power_disable(self, request: PowerDisableRequest, context: grpc.ServicerContext) -> DutPowerResponse:
        """Disable power on a channel (V2 unified RPC)."""
        self.logger.info(f"PowerDisable: channel={request.channel}")
        try:
            gpio, label = self._get_en_gpio(request.channel)
            if err := gpio.write(False):
                return DutPowerResponse(success=False, message=f"Error disabling {label} power: {err}")
            self._set_enabled(request.channel, False)
            return DutPowerResponse(success=True, message=f"{label} power disabled")
        except Exception as e:
            return DutPowerResponse(success=False, message=str(e))

    def power_read(self, request: PowerReadRequest, context: grpc.ServicerContext) -> PowerReadResponse:
        """Read power status for a channel (V2 unified RPC)."""
        self.logger.info(f"PowerRead: channel={request.channel}")
        try:
            ina_path = self._get_ina_path(request.channel)
            if not ina_path:
                return PowerReadResponse(success=False, message=f"No INA219 for channel {request.channel}")

            err, voltage_v, current_ma, power_mw = self._read_ina219(ina_path)
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
        """Measure power over a duration and compute statistics (V2 RPC)."""
        self.logger.info(f"PowerMeasure: channel={request.channel}, duration={request.duration_s}s")
        try:
            ina_path = self._get_ina_path(request.channel)
            if not ina_path:
                return PowerMeasureResponse(success=False, message=f"No INA219 for channel {request.channel}")

            currents_ma = []
            voltages_mv = []
            start_time = time.time()

            while (time.time() - start_time) < request.duration_s:
                if not context.is_active():
                    break
                err, voltage_v, current_ma, _ = self._read_ina219(ina_path)
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

    def power_stream(self, request: PowerStreamRequest, context: grpc.ServicerContext) -> Iterator[PowerStreamResponse]:
        """Server-streaming power samples until client cancels (V2 RPC)."""
        ina_path = self._get_ina_path(request.channel)
        if not ina_path:
            yield PowerStreamResponse(samples=[])
            return

        self.logger.info(f"PowerStream started: channel={request.channel}")
        start_time = time.time()
        try:
            while context.is_active():
                err, voltage_v, current_ma, _ = self._read_ina219(ina_path)
                if err:
                    time.sleep(0.1)  # back off on read errors
                    continue
                elapsed_ms = int((time.time() - start_time) * 1000)
                sample = PowerSample(
                    timestamp_ms=elapsed_ms,
                    voltage_mv=voltage_v * 1000.0,
                    current_ma=current_ma,
                )
                yield PowerStreamResponse(samples=[sample])
                time.sleep(0.01)  # ~100 Hz
        finally:
            self.logger.info("PowerStream ended")

    # -------------------------------------------------
    #                    Snapshot helper
    # -------------------------------------------------

    def get_snapshot_data(self) -> list:
        """Return current power readings for GetSnapshot."""
        result = []
        for channel, addr in _CHANNEL_INA_ADDR.items():
            hwmon = self._ina_paths.get(addr)
            if not hwmon:
                continue
            err, voltage_v, current_ma, _ = self._read_ina219(hwmon)
            if err:
                continue
            result.append(SnapshotPower(
                channel=channel,
                enabled=self._is_enabled(channel),
                voltage_v=voltage_v,
                current_ma=current_ma,
            ))
        return result
