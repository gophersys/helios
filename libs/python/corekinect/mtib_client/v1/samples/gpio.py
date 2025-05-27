# Standard includes
import time

# Corekinect includes
from corekinect.utils import Logger

# Private includes
from corekinect.mtib_client.v1 import MtibV1Client, GpioDirection, GpioResistorConfig
from corekinect.mtib_client.v1.samples.helper import run_sample


def sample(client: MtibV1Client, logger: Logger) -> None:
    """
    Blink the GPIOs on the MTIB board.
    """
    logger.info("Testing GPIO")

    # The LEDs in the back of the board are connected to GPIOs 0-7.
    # You should see the LEDs blink in a pattern.
    for i in range(7):
        client.gpio_config(i, GpioDirection.OUTPUT, GpioResistorConfig.NONE)
        client.gpio_write(i, True)
        time.sleep(0.1)
        client.gpio_write(i, False)
        time.sleep(0.1)
        client.gpio_write(i, True)

    # Now in reverse order
    for i in range(7, -1, -1):
        client.gpio_config(i, GpioDirection.OUTPUT, GpioResistorConfig.NONE)
        client.gpio_write(i, True)
        time.sleep(0.1)
        client.gpio_write(i, False)
        time.sleep(0.1)
        client.gpio_write(i, True)


if __name__ == "__main__":
    run_sample(sample, "gpio")
