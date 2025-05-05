# Standard includes
import logging
import traceback

# Corekinect includes
from corekinect.utils import EnvConfig, Logger

# Private includes
from corekinect.mtib_client.v1 import MtibV1Client, NetConfig

# Environment variables for the Mtib client
class MtibCliEnvConfig(EnvConfig):
    LOG_LEVEL: int
    LOG_PATH: str
    SERVER_HOST: str
    SERVER_PORT: int


if __name__ == "__main__":
    logger: Logger = None
    
    try:
        env_config = MtibCliEnvConfig()
    
        # Good logging is a must
        log_config = Logger.Config(
            logger_name="mtib",
            log_directory=env_config.LOG_PATH,
            overall_log_level=env_config.LOG_LEVEL,
            console_log_level=env_config.LOG_LEVEL,
            file_log_level=logging.DEBUG,  # Always log everything to file
            enable_log_color=True,
        )
        logger: Logger = Logger(log_config)
        
        # Initialize the client
        client = MtibV1Client(
            config=MtibV1Client.Config(
                net=NetConfig(
                    addr=env_config.SERVER_HOST,
                    port=env_config.SERVER_PORT,
                )
            )
        )
        
        # Connect to the server
        if err := client.connect():
            logger.error(f"Error connecting to server: {err}")
            exit(1)
            
        # Health check
        ready, errors = client.health_check()
        if not ready:
            logger.error(f"Error checking health: {errors}")
            exit(1)
            
        logger.info("Health check passed for server at %s:%d", env_config.SERVER_HOST, env_config.SERVER_PORT)
        
        # Disconnect from the server
        if err := client.disconnect():
            logger.error(f"Error disconnecting from server: {err}")
            exit(1)
        
    except Exception as e:
        if logger:
            # Print the entire traceback
            logger.error(f"Failed to initialize or run the MtibServer: {e}")
        else:
            print(f"Failed to initialize or run the MtibServer: {e}\n{traceback.format_exc()}")

