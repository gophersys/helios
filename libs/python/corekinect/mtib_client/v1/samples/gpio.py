# Standard includes
import logging
import traceback
import time

# Corekinect includes
from corekinect.utils import EnvConfig, Logger

# Private includes
from corekinect.mtib_client.v1 import *  # Library is configured to only export the needed types


# -------------------------------------------------
#                                             Config
# -------------------------------------------------
# .env
class MtibCliEnvConfig(EnvConfig):
    LOG_LEVEL: int
    LOG_PATH: str
    SERVER_HOST: str
    SERVER_PORT: int


# Test
OUTPUT_GPIO = 1
INPUT_GPIO = 2


# -------------------------------------------------
#                                              Test
# -------------------------------------------------
def test_gpio(client: MtibV1Client, logger: Logger):
    logger.info("Testing GPIO")

    # Blink a few times
    for i in range(12):
        client.gpio_config(i, GpioDirection.OUTPUT, GpioResistorConfig.NONE)
        client.gpio_write(i, True)
        time.sleep(0.05)
        client.gpio_write(i, False)
        time.sleep(0.05)
        client.gpio_write(i, True)


# -------------------------------------------------
#                                              Main
# -------------------------------------------------
if __name__ == "__main__":
    logger: Logger = None

    try:
        env_config = MtibCliEnvConfig()

        # Good logging is a must
        logger = Logger(
            config=Logger.Config(
                logger_name="mtib",
                log_directory=env_config.LOG_PATH,
                overall_log_level=env_config.LOG_LEVEL,
                console_log_level=env_config.LOG_LEVEL,
                file_log_level=logging.DEBUG,
                enable_log_color=True,
            )
        )

        client = MtibV1Client(
            config=MtibV1Client.Config(
                net=NetConfig(
                    addr=env_config.SERVER_HOST,
                    port=env_config.SERVER_PORT,
                )
            )
        )

        if err := client.connect():
            logger.error(f"Error connecting to server: {err}")
            exit(1)

        ready, errors = client.health_check()
        if not ready:
            logger.error(f"Error checking health: {errors}")
            exit(1)

        logger.info("Health check passed for server at %s:%d", env_config.SERVER_HOST, env_config.SERVER_PORT)

        # Run the actual test
        test_gpio(client, logger)

        if err := client.disconnect():
            logger.error(f"Error disconnecting from server: {err}")
            exit(1)

    except Exception as e:
        if logger:
            # Print the entire traceback
            logger.error(f"Failed to initialize or run the MtibServer: {e}")
        else:
            print(f"Failed to initialize or run the MtibServer: {e}\n{traceback.format_exc()}")
