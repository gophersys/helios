# Standard includes
import logging
import traceback
import sys
from typing import Callable, Optional, Any

# Corekinect includes
from corekinect.utils import EnvConfig, Logger

# Private includes
from corekinect.mtib_client.v1 import *


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
