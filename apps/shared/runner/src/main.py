# Standard includes
import sys
import grpc
import logging
import signal
import logging
from concurrent.futures import ThreadPoolExecutor

# Corekinect includes
from corekinect.utils import Logger

# Protocol includes
from protos.mtib_runner.mtib_runner_pb2_grpc import MtibRunnerV1Servicer, add_MtibRunnerV1Servicer_to_server

# App includes
from src.config.env import ServerEnvConfig
from providers.runner import ServerProvider
from providers.mock import MockServerProvider


def graceful_shutdown(server: grpc.Server, provider: MtibRunnerV1Servicer, log: Logger):
    log.warning("Kill signal detected, stopping server...")

    try:
        if provider is not None:
            err = provider.stop()
            if err is not None:
                log.error(f"An error occurred stopping runner service provider: {err}")

        server.stop(0)
    finally:
        log.info("Exiting application...")
        sys.exit(0)


# ----------------------------------------------------------------------------------
#                                                                               Main
# --------------------------------------------------------------------------------*/

if __name__ == "__main__":
    # Instantiate a global server logger
    log: Logger = Logger(
        config=Logger.Config(
            logger_name="runner",
            console_log_level=logging.DEBUG,
        )
    )

    try:
        # Load configuration from environment
        env_config: ServerEnvConfig = ServerEnvConfig()

        # Create gRPC server
        server = grpc.server(ThreadPoolExecutor(max_workers=10))
        server.add_insecure_port(f"[::]:{env_config.RUNNER_GRPC_SERVER_PORT}")

        # Instantiate a runner service provider (mock or actual server)
        provider: MtibRunnerV1Servicer = None
        if env_config.MOCK_SERVER:
            provider = MockServerProvider(env_config=env_config, logger=log)
        else:
            provider = ServerProvider(env_config=env_config, logger=log)

        add_MtibRunnerV1Servicer_to_server(provider, server)

        # Start server
        server.start()
        log.info(f"Server started, listening on port {env_config.RUNNER_GRPC_SERVER_PORT}.")

        # Set up signal handlers
        signal.signal(signal.SIGINT, lambda sig, frame: graceful_shutdown(server, provider, log))
        signal.signal(signal.SIGTERM, lambda sig, frame: graceful_shutdown(server, provider, log))

        # Block until the server terminates
        server.wait_for_termination()

    except Exception as e:
        log.error(f"Server crashed due to an exception: {e}")
        sys.exit(1)
