# Standard includes
import time
import sys

# Corekinect includes
from corekinect.utils import Logger

# Private includes
from corekinect.mtib_client.v1 import MtibV1Client
from corekinect.mtib_client.v1.samples.helper import run_sample


def sample(client: MtibV1Client, logger: Logger) -> None:
    """
    Read the ADCs on the MTIB board.
    """
    logger.info("Testing ADC")

    readings = []
    for i in range(8):
        voltage, error = client.adc_read(i)
        if error:
            logger.error(f"Error reading ADC {i}: {error}")
            sys.exit(1)

        readings.append(voltage)

    # Print the readings
    logger.info(f"Readings: {readings}")


if __name__ == "__main__":
    run_sample(sample, "gpio")
