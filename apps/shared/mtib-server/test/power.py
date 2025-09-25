# Standard includes
import logging
import signal
import sys
import time
import traceback
from typing import Any, Callable, Optional

# Private includes
from corekinect.mtib_client.v1 import *

# Corekinect includes
from corekinect.utils import EnvConfig, Logger


# Environment variables for the Mtib client
class MtibCliEnvConfig(EnvConfig):
    LOG_LEVEL: int
    LOG_PATH: str
    SERVER_HOST: str
    SERVER_PORT: int


def run_sample(sample_func: Callable[[MtibV1Client, Logger], None], sample_name: str = "mtib_sample") -> None:
    """
    Run a sample function with standardized error handling, logging, and setup.

    Args:
        sample_func: Function that takes a MtibV1Client and Logger and performs the sample operations
        sample_name: Name of the sample (used for logging)
    """
    logger: Optional[Logger] = None
    client: Optional[MtibV1Client] = None

    try:
        env_config = MtibCliEnvConfig()

        # Setup logging
        log_config = Logger.Config(
            logger_name=sample_name,
            log_directory=env_config.LOG_PATH,
            overall_log_level=env_config.LOG_LEVEL,
            console_log_level=env_config.LOG_LEVEL,
            file_log_level=logging.DEBUG,  # Always log everything to file
            enable_log_color=True,
        )
        logger = Logger(log_config)

        # Initialize the client
        client = MtibV1Client(
            config=MtibV1Client.Config(
                net=NetConfig(
                    addr=env_config.SERVER_HOST,
                    port=env_config.SERVER_PORT,
                )
            ),
            logger=logger,
        )

        # Connect to the server
        if err := client.connect():
            logger.error(f"Error connecting to server: {err}")
            sys.exit(1)

        # Health check
        ready, errors, error = client.HealthCheck()
        if error:
            logger.error(f"Error checking health: {error}")
            sys.exit(1)

        if not ready:
            logger.error(f"Error checking health: {errors}")
            sys.exit(1)

        logger.info("Health check passed for server at %s:%d", env_config.SERVER_HOST, env_config.SERVER_PORT)

        # Run the actual sample function
        sample_func(client, logger)

    except Exception as e:
        if logger:
            # Print the entire traceback
            logger.error(f"Failed to run the sample: {e}")
            logger.error(traceback.format_exc())
        else:
            print(f"Failed to run the sample: {e}\n{traceback.format_exc()}")
        sys.exit(1)
    finally:
        # Ensure we disconnect even if there was an error
        if client:
            if err := client.disconnect():
                if logger:
                    logger.error(f"Error disconnecting from server: {err}")
                else:
                    print(f"Error disconnecting from server: {err}")


def cleanup_power(client: MtibV1Client, logger: Logger) -> None:
    """
    Cleanup function to turn off all power when script exits.
    """
    logger.info("Cleaning up - turning off all power")

    # Turn off DUT charge power
    if err := client.DutChargePowerDisable():
        logger.error(f"Error disabling DUT charge power during cleanup: {err}")
    else:
        logger.info("DUT charge power disabled")

    # Turn off DUT power
    if err := client.DutPowerDisable():
        logger.error(f"Error disabling DUT power during cleanup: {err}")
    else:
        logger.info("DUT power disabled")


def sample(client: MtibV1Client, logger: Logger) -> None:
    """
    Test the power management on the MTIB board.
    """
    logger.info("Testing power management")

    # Set up signal handlers for graceful shutdown
    def signal_handler(signum, frame):
        logger.info(f"Received signal {signum}, cleaning up...")
        cleanup_power(client, logger)
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)  # Ctrl+C
    signal.signal(signal.SIGTERM, signal_handler)  # Termination signal

    try:
        # # Turn off everything
        if err := client.DutPowerDisable():
            logger.fatal(f"Error disabling DUT power: {err}")

        if err := client.DutChargePowerDisable():
            logger.fatal(f"Error disabling DUT charge power: {err}")

        time.sleep(2)

        # Turn on the DUT power (connected to the battery)
        voltage_v = 4.0
        if err := client.DutPowerEnable(voltage_v):
            logger.fatal(f"Error enabling DUT power: {err}")

        if err := client.DutChargePowerEnable():
            logger.fatal(f"Error enabling DUT charge power: {err}")

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

    finally:
        # Always cleanup power when exiting the function
        cleanup_power(client, logger)


if __name__ == "__main__":
    run_sample(sample, "gpio")
