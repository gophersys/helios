# Standard includes
import logging
import sys
import time
import traceback
from typing import List

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
from src.services.storage.client import init_storage_client
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
