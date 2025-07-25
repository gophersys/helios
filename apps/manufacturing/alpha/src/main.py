# Standard includes
import logging
import traceback
import requests
import sys
from typing import Callable, Optional, Any
import signal
import urllib3

# Suppress HTTP requests warnings when (verify=False)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Corekinect includes
from corekinect.utils import EnvConfig, Logger

# Private includes
from corekinect.mtib_client.v1 import *

from config.env import AlphaEnvConfig
from src.steps.personalization import personalization_step


def graceful_shutdown(client, logger):
    if client:
        if err := client.disconnect():
            if logger:
                logger.error(f"Error disconnecting from server: {err}")
            else:
                print(f"Error disconnecting from server: {err}")


if __name__ == "__main__":
    logger: Optional[Logger] = None
    client = None

    def handle_signal(signum, frame):
        print("\n")
        if logger:
            logger.info("Received shutdown signal. Disconnecting client...")
        graceful_shutdown(client, logger)
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    try:
        env_config = AlphaEnvConfig()
        # Setup logging
        log_config = Logger.Config(
            logger_name="alpha-manufacturing",
            log_directory=env_config.LOG_PATH,
            overall_log_level=env_config.LOG_LEVEL,
            console_log_level=env_config.LOG_LEVEL,
            file_log_level=logging.DEBUG,  # Always log everything to file
            enable_log_color=True,
        )
        logger = Logger(log_config)

        client = MtibV1Client(
            config=MtibV1Client.Config(
                net=NetConfig(
                    addr=env_config.MTIB_SERVER_HOST,
                    port=env_config.MTIB_SERVER_PORT,
                )
            ),
            logger=logger,
        )

        if err := client.connect():
            logger.error(f"Error connecting to server: {err}")
            sys.exit(1)

        ready, errors, error = client.HealthCheck()
        if error or not ready:
            logger.error(f"Error checking health: {error}")
            sys.exit(1)

        logger.info(
            "Health check passed for server at %s:%d", env_config.MTIB_SERVER_HOST, env_config.MTIB_SERVER_PORT
        )

        # Turn off everything
        if err := client.DutPowerDisable():
            logger.fatal(f"Error disabling DUT power: {err}")

        if err := client.DutChargePowerDisable():
            logger.fatal(f"Error disabling DUT charge power: {err}")

        err = personalization_step(client, logger, env_config, "1234567890")
        if err is not None:
            logger.error(f"Error during personalization: {err}")
            sys.exit(1)

        # Main loop for barcode scanning
        while True:
            try:
                serial_number = input("\033[92mScan or enter serial number:\033[0m ")
                if not serial_number.strip():
                    print("\033[91mNo serial number entered. Please try again.\033[0m")
                    continue
                err = personalization_step(client, logger, env_config, serial_number)
                if err is not None:
                    print(f"\033[91mError: {err}\033[0m")
                else:
                    print("\033[92mPersonalization successful!\033[0m")
            except KeyboardInterrupt:
                print("\nExiting...")
                break
    except Exception as e:
        if logger:
            # Print the entire traceback
            logger.error(f"Failed to run the sample: {e}")
            logger.error(traceback.format_exc())
        else:
            print(f"Failed to run the sample: {e}\n{traceback.format_exc()}")
        sys.exit(1)
    finally:
        graceful_shutdown(client, logger)
