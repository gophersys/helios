# Standard includes
import time
import sys
import os

# Corekinect includes
from corekinect.utils import Logger

# Private includes
from corekinect.mtib_client.v1 import MtibV1Client, GpioDirection, GpioResistorConfig
from test.helper import run_sample


def sample(client: MtibV1Client, logger: Logger) -> None:
    """
    Test the power management on the MTIB board.
    """
    logger.info("Testing power management")

    # # # Turn off everything
    # if err := client.DutPowerDisable():
    #     logger.fatal(f"Error disabling DUT power: {err}")

    # if err := client.DutChargePowerDisable():
    #     logger.fatal(f"Error disabling DUT charge power: {err}")

    # # sys.exit(0)
    # time.sleep(2)

    # # Turn on the DUT power (connected to the battery)
    # voltage_v = 4.0
    # if err := client.DutPowerEnable(voltage_v):
    #     logger.fatal(f"Error enabling DUT power: {err}")

    # if err := client.DutChargePowerEnable():
    #     logger.fatal(f"Error enabling DUT charge power: {err}")

    # Display the readings for a few seconds
    count = 0
    while True:
        # Normal Power
        current_a, voltage_v, power_w, err = client.DutPowerRead()
        if err:
            logger.fatal(f"Error reading DUT power: {err}")

        # Charge Power
        chg_current_a, chg_voltage_v, chg_power_w, err = client.DutChargePowerRead()
        if err:
            logger.fatal(f"Error reading DUT charge power: {err}")

        logger.info(
            f"DUT  power: {power_w} W, current: {current_a} A, voltage: {voltage_v} V charge power: {chg_power_w} W, current: {chg_current_a} A, voltage: {chg_voltage_v} V"
        )

        # Wait a bit
        time.sleep(1)
        count += 1

    # # Turn off everything
    # if err := client.DutChargePowerDisable():
    #     logger.fatal(f"Error disabling DUT charge power: {err}")

    # logger.info("DUT charge power disabled")

    # if err := client.DutPowerDisable():
    #     logger.fatal(f"Error disabling DUT power: {err}")

    # logger.info("DUT power disabled")


if __name__ == "__main__":
    run_sample(sample, "gpio")
