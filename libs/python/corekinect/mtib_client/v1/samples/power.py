# Standard includes
import time

# Corekinect includes
from corekinect.utils import Logger

# Private includes
from corekinect.mtib_client.v1 import MtibV1Client, GpioDirection, GpioResistorConfig
from corekinect.mtib_client.v1.samples.helper import run_sample


def sample(client: MtibV1Client, logger: Logger) -> None:
    """
    Test the power management on the MTIB board.
    """
    logger.info("Testing power management")

    # Turn off everything
    if err := client.dut_power_disable():
        logger.fatal(f"Error disabling DUT power: {err}")

    if err := client.dut_charge_power_disable():
        logger.fatal(f"Error disabling DUT charge power: {err}")

    logger.info("DUT power and charge power disabled")

    # Turn on the DUT power and DUT charge power
    voltage_v = 3.3
    if err := client.dut_power_enable(voltage_v):
        logger.fatal(f"Error enabling DUT power: {err}")

    logger.info(f"DUT power enabled, voltage: {voltage_v}")

    if err := client.dut_charge_power_enable():
        logger.fatal(f"Error enabling DUT charge power: {err}")

    logger.info("DUT charge power enabled")

    # Wait a bit
    time.sleep(3)

    # Turn off everything
    if err := client.dut_charge_power_disable():
        logger.fatal(f"Error disabling DUT charge power: {err}")

    logger.info("DUT charge power disabled")

    if err := client.dut_power_disable():
        logger.fatal(f"Error disabling DUT power: {err}")

    logger.info("DUT power disabled")


if __name__ == "__main__":
    run_sample(sample, "gpio")
