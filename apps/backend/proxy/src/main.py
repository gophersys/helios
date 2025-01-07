# Standard includes
import logging

# App includes
from src.server import Proxy, ProxyEnvConfig, proxy_server

# Corekinect includes
from corekinect.utils import Logger

# API
from src.api.v1.register import api_v1_register
from src.api.v2.register import api_v2_register

# ----------------------------------------------------------------------------------
#                                                                              Entry
# --------------------------------------------------------------------------------*/
if __name__ == "__main__":
    logger: Logger = None

    try:
        # Load any environment variables
        env_config = ProxyEnvConfig()

        # Create the logger configuration for the global logger
        log_config = Logger.Config(
            logger_name="proxy",
            log_directory=env_config.LOG_PATH,
            overall_log_level=logging.DEBUG,
            console_log_level=logging.DEBUG,
            file_log_level=logging.DEBUG,
            enable_log_color=True,
        )

        # Instantiate the app logger
        logger: Logger = Logger(log_config)

        # Create the config for the Proxy server
        config = Proxy.Config(
            debug=True,
            addr="0.0.0.0",
            logger=logger,
            env=env_config,
        )

        # Initialize ProxyServer with the config
        proxy_server = Proxy(config)

        # Register the API routes
        api_v1_register(proxy_server.app)
        api_v2_register(proxy_server.app)

        # Listen for requests
        proxy_server.listen()

    except Exception as e:
        # If we have already setup our logger, then use that one so we can see fatal error in log files
        logger.error(f"Failed to initialize or run the ProxyServer: {e}")
