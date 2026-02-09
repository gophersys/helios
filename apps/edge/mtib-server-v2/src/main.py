# Standard imports
import logging
import signal
import sys
import traceback
from concurrent import futures
from typing import Optional

# 3rd party imports
import grpc

# Corekinect imports
from corekinect.utils import EnvConfig, Logger

# Protocol imports
from protocols.mtib_v2 import mtib_v2_pb2_grpc

# Application imports
from src.hardware import HardwareContext, HardwareRevision
from src.providers.mtib import MtibV2Provider, MtibV2ProviderConfig

# -------------------------------------------------
#                                        Env Config
# -------------------------------------------------


# These get loaded from environment variables
class MtibEnvConfig(EnvConfig):
    # Hardware configuration
    # Set MTIB_HARDWARE_REVISION to override auto-detection (e.g., "1.1", "1.2")
    # Set MTIB_AUTO_DETECT_REVISION=false to disable auto-detection
    HARDWARE_REVISION: Optional[str] = None  # None = auto-detect

    # Logging configuration
    LOG_LEVEL: int
    LOG_PATH: str

    # Where this app will listen for incoming requests
    SERVER_PORT: int

    # Where this app will look for assets for all of its components
    # that need configurations or firmware files (e.g. FluidNC)
    ASSETS_PATH: str

    # Metrics configuration
    METRICS_ENABLED: bool
    METRICS_BROKER_URL: str

    MOTION_ENABLED: bool


# -------------------------------------------------
#                                          Shutdown
# -------------------------------------------------
def handle_shutdown(signum, frame, server, logger):
    """Handle graceful shutdown on SIGINT and SIGTERM"""
    signal_name = "SIGTERM" if signum == signal.SIGTERM else "SIGINT"

    if logger:
        logger.info(f"Received {signal_name}. Initiating graceful shutdown...")

    if server:
        server.stop(grace=5)  # 5 seconds grace period for ongoing requests

    if logger:
        logger.info("Server shutdown complete")

    sys.exit(0)


# -------------------------------------------------
#                                             Entry
# -------------------------------------------------
if __name__ == "__main__":
    logger: Logger = None
    server: grpc.Server = None
    hardware: HardwareContext = None
    provider: MtibV2Provider = None

    try:
        # Try to handle shutdown gracefully
        for sig in (signal.SIGTERM, signal.SIGINT):
            signal.signal(sig, lambda signum, frame: handle_shutdown(signum, frame, server, logger))

        # Load any environment variables
        env_config = MtibEnvConfig()

        print(f"\n{env_config}\n")

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

        # Resolve hardware revision (from env var or auto-detect)
        # Priority: MTIB_HARDWARE_REVISION env var > auto-detection > default (REV 1.1)
        # IMPORTANT: TorizonOS maps Verdin I2C_1 to /dev/i2c-3 (bus 3)
        if env_config.HARDWARE_REVISION:
            revision = HardwareRevision.from_string(env_config.HARDWARE_REVISION)
            logger.info(f"Using hardware revision from config: {revision}")
        else:
            revision = HardwareRevision.resolve(bus_num=3)
            logger.info(f"Auto-detected hardware revision: {revision}")

        # Initialize hardware context
        hardware = HardwareContext.create(revision=revision, logger=logger)
        hardware.init()

        logger.info(f"Hardware features available:")
        logger.info(f"  - GPIO expander (TCA9534A): {hardware.has_gpio_expander}")
        logger.info(f"  - EEPROM (AT24C02C): {hardware.has_eeprom}")
        logger.info(f"  - J-Link multiplexer: {hardware.has_jlink_mux}")
        logger.info(f"  - Motor power switch: {hardware.has_motor_power_switch}")

        # Instantiate the provider that will be used to implement the gRPC methods
        provider = MtibV2Provider(
            config=MtibV2ProviderConfig(
                HARDWARE=hardware,
                ASSETS_DIR=env_config.ASSETS_PATH,
                METRICS_ENABLED=env_config.METRICS_ENABLED,
                METRICS_BROKER_URL=env_config.METRICS_BROKER_URL,
                MOTION_ENABLED=env_config.MOTION_ENABLED,
            ),
            logger=logger,
        )

        # Start observability engine before gRPC server
        provider.start_observability()

        server = grpc.server(futures.ThreadPoolExecutor(max_workers=50))
        mtib_v2_pb2_grpc.add_MtibV2Servicer_to_server(provider, server)
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
        # Stop observability engine
        if provider:
            provider.stop_observability()

        # Ensure hardware is properly closed
        if hardware:
            hardware.close()

        # Ensure server is properly stopped if it was created
        if server:
            server.stop(0)
