# Standard includes
import logging
import sys
import time
import traceback
from typing import List

import eventlet

eventlet.monkey_patch(socket=True, select=False, time=False, os=False, thread=False)

from api.v1.register import register_v1_routes
from api.v2.register import register_v2_routes

# App includes
from config import env_config

# Corekinect includes
from corekinect.utils import EnvConfig, Logger

# 3rd party includes
from flask import Flask
from flask_cors import CORS
from flask_socketio import SocketIO
from src.middleware.permissions import AuthMiddlewareConfig, authMiddleware
from src.services.database.prisma import init_postgres_client
from src.services.kubernetes.client import init_kubernetes_client
from src.services.log.logger import init_logger
from src.services.storage.client import init_storage_client
from src.services.proxy import ProxyServerConfiguration, appProxyServer

# -------------------------------------------------
#                                            Server
# -------------------------------------------------
server = Flask(__name__)
server.json.sort_keys = False
CORS(server, origins=["http://localhost:4200"])
socketio = SocketIO(server, debug=True, cors_allowed_origins="*", async_mode="eventlet", logger=True)


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

        # Initialize the Kubernetes client
        init_kubernetes_client()

        # Initialize the logger
        init_logger(log_config)

        # Initiate the middleware layer
        middleware_config: AuthMiddlewareConfig = AuthMiddlewareConfig(
            cc_auth_server_url=env_config.AUTH_SERVER_URL,
            server_api_key=env_config.AUTH_SERVER_API_KEY,
            server_client_id=env_config.AUTH_SERVER_CREDENTIALS_USER,
            server_client_secret=env_config.AUTH_SERVER_CREDENTIALS_PASS,
        )
        error = authMiddleware.init(logger=logger, auth_enabled=env_config.AUTH_ENABLED, config=middleware_config)
        if error:
            logger.error(f"Could not initialize middleware: {error}")
            sys.exit(1)

        # Instantiate server with desired configuration
        app_config: ProxyServerConfiguration = ProxyServerConfiguration(
            logger=logger,
            db_storage_path=env_config.DB_STORAGE_PATH,
            db_storage_limit_gb=env_config.DB_STORAGE_LIMIT_GB,
            supported_registries=env_config.SUPPORTED_REGISTRIES,
        )
        appProxyServer.init(app_config)

        # Routes
        register_v1_routes(logger, server, socketio)
        register_v2_routes(logger, server, socketio)

        logger.info(f"Server initialized on port {env_config.SERVER_PORT}, in {env_config.ENVIRONMENT} environment")

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
