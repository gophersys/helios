# Standard includes
import time
import sys

# Corekinect includes
from corekinect.utils import Logger

# Private includes
from corekinect.mtib_client.v1 import MtibV1Client, GpioDirection, GpioResistorConfig
from test.helper import run_sample


def sample(client: MtibV1Client, logger: Logger) -> None:
    """
    Blink the GPIOs on the MTIB board.
    """
    logger.info("Testing GPIO")

    # The LEDs in the back of the board are connected to GPIOs 0-7.
    # You should see the LEDs blink in a pattern.
    for i in range(9):
        error = client.GpioConfig(i, GpioDirection.OUTPUT, GpioResistorConfig.NONE)
        if error:
            logger.error(f"Error configuring GPIO {i}: {error}")
            return

        error = client.GpioWrite(i, True)
        if error:
            logger.error(f"Error writing to GPIO {i}: {error}")
            return

        time.sleep(0.1)
        error = client.GpioWrite(i, False)
        if error:
            logger.error(f"Error writing to GPIO {i}: {error}")
            return

        time.sleep(0.1)
        error = client.GpioWrite(i, True)
        if error:
            logger.error(f"Error writing to GPIO {i}: {error}")
            return

    # Now in reverse order
    for i in range(7, -1, -1):
        error = client.GpioConfig(i, GpioDirection.OUTPUT, GpioResistorConfig.NONE)
        if error:
            logger.error(f"Error configuring GPIO {i}: {error}")
            return

        error = client.GpioWrite(i, True)
        if error:
            logger.error(f"Error writing to GPIO {i}: {error}")
            return

        time.sleep(0.1)
        error = client.GpioWrite(i, False)
        if error:
            logger.error(f"Error writing to GPIO {i}: {error}")
            return

        time.sleep(0.1)
        error = client.GpioWrite(i, True)
        if error:
            logger.error(f"Error writing to GPIO {i}: {error}")
            return

    # Now read the values of the GPIOs
    for i in range(9):
        error = client.GpioConfig(i, GpioDirection.INPUT, GpioResistorConfig.NONE)
        if error:
            logger.error(f"Error configuring GPIO {i}: {error}")
            return

        value, error = client.GpioRead(i)
        if error:
            logger.error(f"Error reading from GPIO {i}: {error}")
            return
        logger.info(f"GPIO {i}: {value}")


if __name__ == "__main__":
    run_sample(sample, "gpio")
