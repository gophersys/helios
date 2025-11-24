# Standard includes
import asyncio
import logging

LOG_MODULE = "validation-sigma5"
from typing import Optional

logging.basicConfig(level=logging.WARN, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
import sys
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Corekinect includes
from corekinect.utils.logx import Logger

# App includes
from config.env import env_config
from services.mtib import init_mtib_client
from services.storage import init_storage_client
from tests.electrical import run_electrical_test
from tests.app_post import run_app_post_test
from tests.comm_post import run_comm_post_test


def setup_environment() -> Optional[str]:
    """Setup the environment for the validation test"""
    err = init_mtib_client(env_config.MTIB_HOST, env_config.MTIB_PORT)
    if err:
        return f"Failed to initialize MTIB client: {err}"

    err = init_storage_client()
    if err:
        return f"Failed to initialize storage client: {err}"

    return None


if __name__ == "__main__":
    try:
        # Create the logger
        log_config = Logger.Config(
            logger_name=LOG_MODULE,
            log_directory=env_config.LOG_PATH,
            console_log_level=logging.DEBUG,
        )
        logger: Logger = Logger(log_config)

        # Initial this app services
        err = setup_environment()
        if err:
            logging.error(f"Failed to setup environment: {err}")
            sys.exit(1)

        # Run tests based on configuration flags
        if env_config.TEST_ENABLE_ELECTRICAL:
            err = run_electrical_test(logger)
            if err:
                logger.error(f"Failed to run electrical test: {err}")
                sys.exit(1)

        if env_config.TEST_ENABLE_APP_POST:
            err = run_app_post_test(logger)
            if err:
                logger.error(f"Failed to run app post test: {err}")
                sys.exit(1)

        if env_config.TEST_ENABLE_COMM_POST:
            err = run_comm_post_test(logger)
            if err:
                logger.error(f"Failed to run comm post test: {err}")
                sys.exit(1)

        logger.info("Sigma5 validation tests completed successfully after change")
        sys.exit(0)

    except Exception as e:
        logging.error(f"Validation test setup failed: {e}")
        sys.exit(1)
