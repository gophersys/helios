# Standard includes
import logging
import sys
import eventlet
from typing import List
import traceback

eventlet.monkey_patch(socket=True, select=False, time=False, os=False, thread=False)

# 3rd party includes
from flask import Flask
from flask_socketio import SocketIO

# Corekinect includes
from corekinect.utils import Logger, EnvConfig

# App includes
from config import env_config
from src.middleware.permissions import authMiddleware, AuthMiddlewareConfig
from src.services.proxy import ProxyServerConfiguration, appProxyServer
from api.v1.register import register_v1_routes
from api.v1.clusters.tests.exec_uuid import clusters_tests_exec_uuid_socketio_handler

# -------------------------------------------------
#                                            Server
# -------------------------------------------------
server = Flask(__name__)
socketio = SocketIO(server, debug=True, cors_allowed_origins="*", async_mode="eventlet", logger=True)


@socketio.on("exec_test")
def handle_ws_event_exec_test(data):
    clusters_tests_exec_uuid_socketio_handler(data, socketio)


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

        # Register the v1 routes
        register_v1_routes(server)

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
