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
from src.providers import MtibV1Provider, MtibV1ProviderConfig
from src.lib.data_logger import DataLoggerClient, DataLoggerClientConfig


# -------------------------------------------------
#                                        Env Config
# -------------------------------------------------
class MtibEnvConfig(EnvConfig):
    # Logging configuration
    LOG_LEVEL: int
    LOG_PATH: str

    # Server port configuration
    SERVER_PORT: int

    # Server firmware and assets configuration
    ASSETS_PATH: str

    # FluidNC configuration
    FLUIDNC_SERIAL_PORT: str
    FLUIDNC_RESET_PIN: str

    # Data logger configuration
    DATA_LOGGER_ENABLED: bool
    DATA_LOGGER_MQTT_BROKER_URL: str


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
        provider = MtibV1Provider(
            config=MtibV1ProviderConfig(
                ASSETS_DIR=env_config.ASSETS_PATH,
            ),
            logger=logger,
        )

        # Instantiate the gRPC server by adding the provider to it
        server = grpc.server(futures.ThreadPoolExecutor(max_workers=50))
        mtib_pb2_grpc.add_MtibV1Servicer_to_server(provider, server)
        server.add_insecure_port(f"[::]:{env_config.SERVER_PORT}")

        # Setup signal handlers for OS signals
        for sig in (signal.SIGTERM, signal.SIGINT):
            signal.signal(sig, lambda signum, frame: handle_shutdown(signum, frame, server, logger))

        # Run baby run
        server.start()
        logger.info(f"Server started on port {env_config.SERVER_PORT} with new updates!!!")

        # Instantiate a data logger client that will be used to plot/listen for data
        if env_config.DATA_LOGGER_ENABLED:
            data_logger_client = DataLoggerClient(
                config=DataLoggerClientConfig(
                    MQTT_BROKER_URL=env_config.DATA_LOGGER_MQTT_BROKER_URL,
                    SERVER_PORT=env_config.SERVER_PORT,
                ),
                logger=logger,
            )
            error = data_logger_client.init()
            if error:
                logger.error(f"Failed to initialize data logger client: {error}")
                sys.exit(1)

        # Let's clean up after ourselves
        server.wait_for_termination()

    except Exception as e:
        if logger:
            # Print the entire traceback
            logger.error(f"Failed to initialize or run the MtibServer: {e}")
        else:
            print(f"Failed to initialize or run the MtibServer: {e}\n{traceback.format_exc()}")

    finally:
        # Ensure data logger client is properly deinitialized
        if data_logger_client is not None:
            data_logger_client.deinit()

        # Ensure server is properly stopped if it was created
        if server:
            server.stop(0)
