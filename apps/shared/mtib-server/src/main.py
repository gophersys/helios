# Standard includes
import logging
from concurrent import futures
import signal
import sys
import traceback

# 3rd party includes
import grpc

# Corekinect includes
from corekinect.utils import Logger, EnvConfig

# Protocol includes
from protocols.mtib import mtib_pb2_grpc

# Application includes
from src.providers import ProviderConfig, DevProvider, MtibV1Provider


# -------------------------------------------------
#                                        Env Config
# -------------------------------------------------
class MtibEnvConfig(EnvConfig):
    ENVIRONMENT: str
    LOG_LEVEL: int
    LOG_PATH: str
    ASSETS_PATH: str
    GRPC_SERVER_PORT: int
    MTIB_SERIAL_PORT: str
    MTIB_SERIAL_BAUD: int
    FW_FILE_STORAGE_DIR: str
    MCU_9160_USB_BUS: str
    MCU_52840_USB_BUS: str
    SERVER_RESET_ENABLED: bool
    SERVER_RESET_GPIO: int
    USB_ENABLE_GPIO: int

    # Pinout configuration
    FLUIDNC_SERIAL_PORT: str
    FLUIDNC_RESET_PIN: str


# -------------------------------------------------
#                                          Shutdown
# -------------------------------------------------
def handle_shutdown(signum, frame, server, logger):
    """Handle graceful shutdown on SIGINT and SIGTERM"""
    signal_name = "SIGTERM" if signum == signal.SIGTERM else "SIGINT"
    logger.info(f"Received {signal_name}. Initiating graceful shutdown...")

    # Stop accepting new requests
    server.stop(grace=5)  # 5 seconds grace period for ongoing requests
    logger.info("Server shutdown complete")
    sys.exit(0)


# -------------------------------------------------
#                                             Entry
# -------------------------------------------------
if __name__ == "__main__":
    logger: Logger = None
    server = None

    try:
        # Load any environment variables
        env_config = MtibEnvConfig()

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

        # A provider is the class that implements the gRPC methods
        try:
            if env_config.ENVIRONMENT == "development":
                provider = DevProvider(
                    config=ProviderConfig(
                        ASSETS_DIR=env_config.ASSETS_PATH,
                    ),
                    logger=logger,
                )
            elif env_config.ENVIRONMENT == "production":
                provider = MtibV1Provider(
                    config=ProviderConfig(
                        ASSETS_DIR=env_config.ASSETS_PATH,
                    ),
                    logger=logger,
                )
            else:
                raise ValueError(f"Invalid environment: {env_config.ENVIRONMENT}")
        except Exception as e:
            logger.error(f"Failed to initialize the provider: {e}")
            sys.exit(1)

        # Instantiate the gRPC server by adding the provider to it
        server = grpc.server(futures.ThreadPoolExecutor(max_workers=50))
        mtib_pb2_grpc.add_MtibV1Servicer_to_server(provider, server)
        server.add_insecure_port(f"[::]:{env_config.GRPC_SERVER_PORT}")

        # Setup signal handlers for OS signals
        for sig in (signal.SIGTERM, signal.SIGINT):
            signal.signal(sig, lambda signum, frame: handle_shutdown(signum, frame, server, logger))

        # Run baby run
        server.start()
        logger.info(f"Server started on port {env_config.GRPC_SERVER_PORT}")

        # Let's clean up after ourselves
        server.wait_for_termination()

    except Exception as e:
        if logger:
            # Print the entire traceback
            logger.error(f"Failed to initialize or run the MtibServer: {e}")
        else:
            print(f"Failed to initialize or run the MtibServer: {e}\n{traceback.format_exc()}")

    finally:
        # Ensure server is properly stopped if it was created
        if server:
            server.stop(0)
