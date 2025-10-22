# Standard includes
import logging
import signal
import sys
import traceback
from typing import Optional

import urllib3

# Suppress HTTP requests warnings when (verify=False)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Private includes
from corekinect.mtib_client.v1 import *

# Corekinect includes
from corekinect.utils import Logger
from config.env import env_config
from src.steps.personalization import run_manufacturing


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

        # Main
        while True:
            try:
                # We need the serial number to be able to run the manufacturing
                serial_number = input("\033[92mScan or enter serial number:\033[0m ")
                if not serial_number.strip():
                    print("\033[91mNo serial number entered. Please try again.\033[0m")
                    continue

                # Run the manufacturing logic (tests, flashing, etc.)
                err = run_manufacturing(client, logger, serial_number)
                if err is not None:
                    print(f"\033[91mError: {err}\033[0m")
                else:
                    print("\033[92mManufacturing successful!\033[0m")
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
