import grpc
from corekinect.utils import Logger
from src.shared.types import *

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

    def dut_power_enable(self, request: DutPowerRequest, context: grpc.ServicerContext) -> DutPowerResponse:
        """Enable DUT power with specified voltage."""
        self.logger.info(f"DutPowerEnable request received with voltage {request.voltage_v}V")
        return DutPowerResponse(success=False, message="Not implemented")

    def dut_power_disable(self, request: Empty, context: grpc.ServicerContext) -> DutPowerResponse:
        """Disable DUT power."""
        self.logger.info("DutPowerDisable request received")
        return DutPowerResponse(success=False, message="Not implemented")

    def dut_charge_power_enable(self, request: DutPowerRequest, context: grpc.ServicerContext) -> DutPowerResponse:
        """Enable DUT charging power."""
        self.logger.info(f"DutChargePowerEnable request received with voltage {request.voltage_v}V")
        return DutPowerResponse(success=False, message="Not implemented")

    def dut_charge_power_disable(self, request: Empty, context: grpc.ServicerContext) -> DutPowerResponse:
        """Disable DUT charging power."""
        self.logger.info("DutChargePowerDisable request received")
        return DutPowerResponse(success=False, message="Not implemented")

    def dut_power_read(self, request: Empty, context: grpc.ServicerContext) -> DutPowerReadResponse:
        """Read DUT power measurements."""
        self.logger.info("DutPowerRead request received")
        return DutPowerReadResponse(
            success=False,
            message="Not implemented",
            current_a=0.0,
            voltage_v=0.0,
            power_w=0.0
        ) 