# Standard includes
import time

# Corekinect includes
from corekinect.utils import Logger

# Private includes
from corekinect.mtib_client.v1 import MtibV1Client, GpioDirection, GpioResistorConfig
from corekinect.mtib_client.v1.samples.helper import run_sample

GPIO_COUNT = 7

def gpio_sample(client: MtibV1Client, logger: Logger) -> None:
    """
    Sample that demonstrates GPIO functionality of the MTIB server.
    """
    # Configure all GPIOs as outputs
    for gpio_idx in range(GPIO_COUNT):
        if err := client.gpio_config(gpio_idx, GpioDirection.OUTPUT, GpioResistorConfig.NONE):
            logger.error(f"Error configuring GPIO {gpio_idx} as output: {err}")
            return
    
    # Write to all GPIOs
    for gpio_idx in range(GPIO_COUNT):
        if err := client.gpio_write(gpio_idx, True):
            logger.error(f"Error setting GPIO {gpio_idx} high: {err}")
        time.sleep(0.1)
        if err := client.gpio_write(gpio_idx, False):
            logger.error(f"Error setting GPIO {gpio_idx} low: {err}")
        time.sleep(0.1)
        
    # Configure all GPIOs as inputs
    for gpio_idx in range(GPIO_COUNT):
        if err := client.gpio_config(gpio_idx, GpioDirection.INPUT, GpioResistorConfig.NONE):
            logger.error(f"Error configuring GPIO {gpio_idx} as input: {err}")
            return
        
    # Read from all GPIOs
    for gpio_idx in range(GPIO_COUNT):
        state, err = client.gpio_read(gpio_idx)
        if err:
            logger.error(f"Error reading GPIO {gpio_idx}: {err}")
        else:
            logger.info(f"GPIO {gpio_idx} state: {state}")


if __name__ == "__main__":
    run_sample(gpio_sample, "gpio_sample")

