# Corekinect imports
from corekinect.utils import Logger

# Private imports
from src.shared.types import *
from src.lib.mcp4017 import MCP4017
from src.lib.gpio import Gpio, Pin

# 3rd party imports
import grpc
import gpiod
import os
import glob
import time
from typing import Optional, Tuple


# The EN FETs in the carrier board are connected to the following pins:
# - DUT_PWR_EN_1V8 is connected to IMX8_I2C1_DSI_SCL_1V8 (SODIMM_53)
# - DUT_CHG_EN_1V8 is connected to IMX8_I2C1_DSI_SDA_1V8 (SODIMM_55)
#
# There's also a 1/2 voltage divider on the device power voltage, so that we,
# can implement a feedback loop to control the device power voltage, and get as close as we can to the
# target voltage, by adjusting a I2C wiper potentiometer, which is connected to the buck converter that
# outputs the device power voltage.
#
# - DUT_PWR_SENSE_2V5 is connected to IMX8_ADC1_3V3
# - MCP4017T is connected to IMX8_I2C1_SDA_3V3 & IMX8_I2C1_SCL_3V3 with address 0101111 (0x2F)
#
# There are current measurements ICs, one for the DUT power and one for the DUT charging power.
# - INA219 for DUT power is connected to IMX8_I2C1_SDA_3V3 & IMX8_I2C1_SCL_3V3 with address 1000000 (0x40)
# - INA219 for DUT charging power is connected to IMX8_I2C1_SDA_3V3 & IMX8_I2C1_SCL_3V3 with address 1000001 (0x41)
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
        self.power_ina_path = None  # Will store path for INA219 at 0x40 (DUT power)
        self.chg_power_ina_path = None  # Will store path for INA219 at 0x41 (DUT charging power)

        # Scan hwmon devices to find our INA219s
        for hwmon in glob.glob("/sys/class/hwmon/hwmon*"):
            try:
                with open(os.path.join(hwmon, "name"), "r") as f:
                    if f.read().strip() != "ina219":
                        continue

                # Read the I2C address from the device tree
                with open(os.path.join(hwmon, "device/of_node/reg"), "rb") as f:
                    reg = int.from_bytes(f.read(), byteorder="big")
                    if reg == 0x40:
                        self.power_ina_path = hwmon
                        self.logger.info(f"Found DUT power INA219 at {hwmon}")
                    elif reg == 0x41:
                        self.chg_power_ina_path = hwmon
                        self.logger.info(f"Found DUT charging power INA219 at {hwmon}")
            except Exception as e:
                self.logger.warning(f"Error checking hwmon device {hwmon}: {e}")
                continue

        if not self.power_ina_path or not self.chg_power_ina_path:
            self.logger.error("Failed to find both INA219 power monitoring devices")
            raise Exception("Required INA219 power monitoring devices not found")

        # We use GPIOs to control the power to the DUT and the charging power to the DUT.
        # - DUT_PWR_EN_1V8 is connected to IMX8_I2C1_DSI_SCL_1V8 (SODIMM_53)
        # - DUT_CHG_EN_1V8 is connected to IMX8_I2C1_DSI_SDA_1V8 (SODIMM_55)
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

    def _read_adc_voltage(self) -> Tuple[Optional[float], Optional[str]]:
        """Read voltage from ADS1015 ADC channel 3.

        The ADC is connected through a 2:1 voltage divider, so the actual voltage
        is twice the measured voltage.

        Returns:
            Actual voltage in volts (after accounting for voltage divider)
        """
        try:
            voltage_v = 0.0

            # Read bus voltage (in mV) and convert to V
            with open(os.path.join(self.power_ina_path, "in1_input"), "r") as f:
                voltage_v = float(f.read().strip()) / 1000.0  # Convert mV to V

            return voltage_v, None
        except Exception as e:
            self.logger.error(f"Error reading ADC voltage: {e}")
            return None, str(e)

    def _set_dut_power_voltage(self, target_voltage_v: float) -> Optional[str]:
        """Set the DUT power voltage by adjusting the MCP4017 wiper potentiometer.

        Uses binary search to find the wiper position that gives closest voltage to target.
        Uses ADS1015 ADC for voltage measurement.
        Returns None on success, error message on failure.
        """
        try:
            # Constants for voltage control
            MAX_ATTEMPTS = 10  # Maximum number of adjustment attempts
            VOLTAGE_TOLERANCE = 0.05  # Acceptable voltage error in V
            STEP_DELAY = 0.2  # Delay between adjustments in seconds

            # Binary search bounds
            min_step = 0
            max_step = MCP4017.MAX_VALUE
            current_step = int(max_step / 2)  # Start in the middle

            for _ in range(MAX_ATTEMPTS):
                # Set the wiper position
                self.mcp4017.set_step(current_step)
                time.sleep(STEP_DELAY)  # Wait for voltage to settle

                # Read current voltage from ADC
                current_voltage_v, error = self._read_adc_voltage()
                if error or current_voltage_v is None:
                    return error

                # Check if we're close enough
                if abs(current_voltage_v - target_voltage_v) <= VOLTAGE_TOLERANCE:
                    self.logger.info(f"Voltage control achieved: {current_voltage_v}V (target: {target_voltage_v}V)")
                    return None

                # Adjust wiper position based on voltage
                if current_voltage_v > target_voltage_v:
                    # Voltage too high, increase wiper value (decrease voltage)
                    min_step = current_step
                    current_step = (current_step + max_step + 1) // 2
                else:
                    # Voltage too low, decrease wiper value (increase voltage)
                    max_step = current_step
                    current_step = (min_step + current_step) // 2

                # If we've converged to a single step, we're done
                if min_step == max_step:
                    break

            # If we get here, we didn't achieve target voltage within tolerance
            final_voltage = current_voltage_v
            self.logger.warning(
                f"Voltage control did not converge: final={final_voltage}V, target={target_voltage_v}V"
            )
            return f"Could not achieve target voltage. Final voltage: {final_voltage}V"

        except Exception as e:
            self.logger.error(f"Error in voltage control: {e}")
            return str(e)

    def dut_power_enable(self, request: DutPowerRequest, context: grpc.ServicerContext) -> DutPowerResponse:
        """Enable DUT power with specified voltage."""
        self.logger.info(f"DutPowerEnable request received with voltage {request.voltage_v}V")

        # Enable the DUT power
        if err := self.dut_pwr_en.write(True):
            return DutPowerResponse(success=False, message=f"Error enabling DUT power: {err}")

        if err := self._set_dut_power_voltage(request.voltage_v):
            return DutPowerResponse(success=False, message=f"Error setting DUT power voltage: {err}")

        return DutPowerResponse(success=True)

    def dut_power_disable(self, request: Empty, context: grpc.ServicerContext) -> DutPowerResponse:
        """Disable DUT power."""
        self.logger.info("DutPowerDisable request received")

        # Disable the DUT power
        if err := self.dut_pwr_en.write(False):
            return DutPowerResponse(success=False, message=f"Error disabling DUT power: {err}")

        return DutPowerResponse(success=True)

    def dut_charge_power_enable(self, request: Empty, context: grpc.ServicerContext) -> DutPowerResponse:
        """Enable DUT charging power."""
        self.logger.info("DutChargePowerEnable request received")

        # Enable the DUT charging power
        if err := self.dut_chg_en.write(True):
            return DutPowerResponse(success=False, message=f"Error enabling DUT charging power: {err}")

        return DutPowerResponse(success=True)

    def dut_charge_power_disable(self, request: Empty, context: grpc.ServicerContext) -> DutPowerResponse:
        """Disable DUT charging power."""
        self.logger.info("DutChargePowerDisable request received")

        # Disable the DUT charging power
        if err := self.dut_chg_en.write(False):
            return DutPowerResponse(success=False, message=f"Error disabling DUT charging power: {err}")

        return DutPowerResponse(success=True)

    def dut_power_read(self, request: Empty, context: grpc.ServicerContext) -> DutPowerReadResponse:
        """Read DUT power measurements."""
        self.logger.info("DutPowerRead request received")

        try:
            # Read bus voltage (in mV) and convert to V
            with open(os.path.join(self.power_ina_path, "in1_input"), "r") as f:
                voltage_v = float(f.read().strip()) / 1000.0  # Convert mV to V

            # Read current (in mA) and convert to A
            with open(os.path.join(self.power_ina_path, "curr1_input"), "r") as f:
                current_a = float(f.read().strip()) / 1000.0  # Convert mA to A

            # Read power (in µW) and convert to W
            with open(os.path.join(self.power_ina_path, "power1_input"), "r") as f:
                power_w = float(f.read().strip()) / 1000000.0  # Convert µW to W

            return DutPowerReadResponse(success=True, current_a=current_a, voltage_v=voltage_v, power_w=power_w)
        except Exception as e:
            self.logger.error(f"Error reading DUT power measurements: {e}")
            return DutPowerReadResponse(
                success=False,
                message=f"Error reading power measurements: {e}",
                current_a=0.0,
                voltage_v=0.0,
                power_w=0.0,
            )

    def dut_charge_power_read(self, request: Empty, context: grpc.ServicerContext) -> DutPowerReadResponse:
        """Read DUT charging power measurements."""
        self.logger.info("DutChargePowerRead request received")

        try:
            # Read bus voltage (in mV) and convert to V
            with open(os.path.join(self.chg_power_ina_path, "in1_input"), "r") as f:
                voltage_v = float(f.read().strip()) / 1000.0  # Convert mV to V

            # Read current (in mA) and convert to A
            with open(os.path.join(self.chg_power_ina_path, "curr1_input"), "r") as f:
                current_a = float(f.read().strip()) / 1000.0  # Convert mA to A

            # Read power (in µW) and convert to W
            with open(os.path.join(self.chg_power_ina_path, "power1_input"), "r") as f:
                power_w = float(f.read().strip()) / 1000000.0  # Convert µW to W

            return DutPowerReadResponse(success=True, current_a=current_a, voltage_v=voltage_v, power_w=power_w)
        except Exception as e:
            self.logger.error(f"Error reading DUT charging power measurements: {e}")
            return DutPowerReadResponse(
                success=False,
                message=f"Error reading charging power measurements: {e}",
                current_a=0.0,
                voltage_v=0.0,
                power_w=0.0,
            )
