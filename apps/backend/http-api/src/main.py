# Standard includes
import atexit
import logging
import signal
import sys
import time
import traceback
import eventlet

eventlet.monkey_patch(socket=True, select=False, time=False, os=False, thread=False)

from api.v2.router import register_v2_routes

# App includes
from config import env_config

# Corekinect includes
from corekinect.utils import EnvConfig, Logger, print_banner

# 3rd party includes
from flask import Flask
from flask_cors import CORS
from flask_socketio import SocketIO
from src.services.database.prisma import init_postgres_client
from src.services.influxdb.client import init_influxdb_client
from src.services.kubernetes.client import init_kubernetes_client
from src.services.log.logger import init_logger
from src.services.scheduler import start_scheduler
from src.services.storage.client import init_storage_client, close_storage_client
from src.services.mtib_observability import init_observability_service, get_observability_service
from src.services.proxy import ProxyServerConfiguration, appProxyServer

# -------------------------------------------------
#                                            Server
# -------------------------------------------------
server = Flask(__name__)
server.json.sort_keys = False
server.config["MAX_CONTENT_LENGTH"] = 100 * 1024 * 1024  # 100 MB upload limit

_cors_origins = [o.strip() for o in env_config.CORS_ORIGINS.split(",") if o.strip()]
CORS(server, origins=_cors_origins)
socketio = SocketIO(server, debug=(env_config.ENVIRONMENT == "development"), cors_allowed_origins=_cors_origins, async_mode="eventlet", logger=(env_config.ENVIRONMENT == "development"))


# -------------------------------------------------
#                                  Graceful Shutdown
# -------------------------------------------------
_shutdown_initiated = False


def graceful_shutdown(signum=None, frame=None):
    """Cleanly close all external service connections on shutdown."""
    global _shutdown_initiated
    if _shutdown_initiated:
        return
    _shutdown_initiated = True

    sig_name = signal.Signals(signum).name if signum else "atexit"
    logging.getLogger("server").info("Graceful shutdown initiated (%s)", sig_name)

    # 1. Stop MTIB observability polling and gRPC channels
    try:
        obs_service = get_observability_service()
        if obs_service is not None:
            obs_service.stop()
            logging.getLogger("server").info("MTIB observability service stopped")
    except Exception as e:
        logging.getLogger("server").warning("Error stopping observability service: %s", e)

    # 2. Close Prisma database connection
    try:
        from src.services.database.prisma import get_db_client
        client = get_db_client()
        if client is not None:
            client.disconnect()
            logging.getLogger("server").info("Database connection closed")
    except Exception as e:
        logging.getLogger("server").warning("Error closing database connection: %s", e)

    # 3. Close InfluxDB client
    try:
        from src.services.influxdb.client import close_influxdb_client
        close_influxdb_client()
        logging.getLogger("server").info("InfluxDB connection closed")
    except Exception as e:
        logging.getLogger("server").warning("Error closing InfluxDB connection: %s", e)

    # 4. Close MinIO storage client (clear urllib3 connection pool)
    try:
        close_storage_client()
        logging.getLogger("server").info("Storage client closed")
    except Exception as e:
        logging.getLogger("server").warning("Error closing storage client: %s", e)

    # 5. Close Kubernetes API client
    try:
        from src.services.kubernetes.client import close_kubernetes_client
        close_kubernetes_client()
        logging.getLogger("server").info("Kubernetes client closed")
    except Exception as e:
        logging.getLogger("server").warning("Error closing Kubernetes client: %s", e)

    logging.getLogger("server").info("Graceful shutdown complete")


signal.signal(signal.SIGTERM, graceful_shutdown)
signal.signal(signal.SIGINT, graceful_shutdown)
atexit.register(graceful_shutdown)


# -------------------------------------------------
#                                             Entry
# -------------------------------------------------
if __name__ == "__main__":
    logger: Logger = None

    try:
        # Initialize the logger
        log_config = Logger.Config(
            logger_name="server",
            log_directory=env_config.LOG_PATH,
            overall_log_level=env_config.LOG_LEVEL,
            console_log_level=env_config.LOG_LEVEL,
            file_log_level=logging.DEBUG,  # Always log everything to file
            enable_log_color=True,
        )
        logger: Logger = Logger(log_config)

        # Initialize the storage client
        init_storage_client()

        # Initialize the database client
        init_postgres_client()

        # Initialize the InfluxDB client
        init_influxdb_client()

        # Initialize the Kubernetes client
        init_kubernetes_client()

        # Initialize the logger
        init_logger(log_config)

        # Start background scheduler (audit log cleanup)
        start_scheduler()

        # Instantiate server with desired configuration
        app_config: ProxyServerConfiguration = ProxyServerConfiguration(
            logger=logger,
            db_storage_path=env_config.DB_STORAGE_PATH,
            db_storage_limit_gb=env_config.DB_STORAGE_LIMIT_GB,
            supported_registries=env_config.SUPPORTED_REGISTRIES,
        )
        appProxyServer.init(app_config)

        # Start observability polling service
        init_observability_service(poll_interval_s=5)

        # Routes
        register_v2_routes(logger, server, socketio)

        # Print startup banner with build metadata
        print_banner(
            "concord-http-api",
            logger=logger,
            Port=str(env_config.SERVER_PORT),
        )

        # Start the server
        socketio.run(
            app=server,
            host="0.0.0.0",
            port=env_config.SERVER_PORT,
            debug=False,
            log_output=True,
            log=logger,
        )

    except Exception as e:
        if logger:
            # Print the entire traceback
            logger.error(f"Failed to initialize or run the Proxy: {e}")
        else:
            print(f"Failed to initialize or run the Proxy: {e}\n{traceback.format_exc()}")
