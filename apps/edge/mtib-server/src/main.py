# Standard imports
import logging
import signal
import sys
import traceback
from concurrent import futures

# 3rd party imports
import grpc

# Corekinect imports
from corekinect.utils import Logger
from corekinect.utils.banner import print_banner

# Protocol imports
from protocols.mtib import mtib_pb2_grpc

# Application imports
from src.server import MtibV1Provider
from src.config import MtibEnvConfig, MtibV1ProviderConfig


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
    server: grpc.Server = None

    try:
        # Try to handle shutdown gracefully
        for sig in (signal.SIGTERM, signal.SIGINT):
            signal.signal(sig, lambda signum, frame: handle_shutdown(signum, frame, server, logger))

        # Load any environment variables
        env_config = MtibEnvConfig()

        # Setup logging
        log_config = Logger.Config(
            logger_name="mtib",
            log_directory=env_config.LOG_PATH,
            overall_log_level=env_config.LOG_LEVEL,
            console_log_level=env_config.LOG_LEVEL,
            file_log_level=logging.DEBUG,  # Always log everything to file
            enable_log_color=True,
        )
        logger: Logger = Logger(log_config)

        # Print startup banner with build info
        print_banner("mtib-server", logger=logger, hw_rev=env_config.HARDWARE_VERSION)

        # Instantiate the provider that will be used to implement the gRPC methods, and add it to the server
        provider = MtibV1Provider(
            config=MtibV1ProviderConfig(
                HARDWARE_VERSION=env_config.HARDWARE_VERSION,
                ASSETS_DIR=env_config.ASSETS_PATH,
                METRICS_ENABLED=env_config.METRICS_ENABLED,
                METRICS_BROKER_URL=env_config.METRICS_BROKER_URL,
                MOTION_ENABLED=env_config.MOTION_ENABLED,
            ),
            logger=logger,
        )

        server = grpc.server(futures.ThreadPoolExecutor(max_workers=50))
        mtib_pb2_grpc.add_MtibV1Servicer_to_server(provider, server)
        server.add_insecure_port(f"[::]:{env_config.SERVER_PORT}")

        # Start the gRPC server
        server.start()
        logger.info(f"Server started on port {env_config.SERVER_PORT}")
        server.wait_for_termination()  # Runs forever until the server is stopped

    except Exception as e:
        if logger:
            # Print the entire traceback for debugging
            logger.error(f"Failed to initialize or run the MtibServer: {e}")
        else:
            print(f"Failed to initialize or run the MtibServer: {e}\n{traceback.format_exc()}")

    finally:

        # Ensure server is properly stopped if it was created
        if server:
            server.stop(0)
