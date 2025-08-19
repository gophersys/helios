# Standard includes
import logging
import sys
import eventlet

eventlet.monkey_patch(socket=True, select=False, time=False, os=False, thread=False)

# Library includes
from flask import Flask
from flask_socketio import SocketIO

# App includes
from config import conf
from src.middleware.permissions import authMiddleware, AuthMiddlewareConfig
from src.services.proxy import ProxyServerConfiguration, appProxyServer
from api.v1.register import register_v1_routes

# Server
server = Flask(__name__)
socketio = SocketIO(server, debug=True, cors_allowed_origins="*", async_mode="eventlet")

# ----------------------------------------------------------------------------------
#                                                                              Entry
# --------------------------------------------------------------------------------*/
if __name__ == "__main__":
    # Initiate the middleware layer
    middleware_config: AuthMiddlewareConfig = AuthMiddlewareConfig(
        cc_auth_server_url=conf.AUTH_SERVER_URL,
        server_api_key=conf.AUTH_SERVER_API_KEY,
        server_client_id=conf.AUTH_SERVER_CREDENTIALS_USER,
        server_client_secret=conf.AUTH_SERVER_CREDENTIALS_PASS,
    )
    error = authMiddleware.init(middleware_config)
    if error:
        logging.error(f"Could not initialize middleware: {error}")
        sys.exit(1)

    # Instantiate server with desired configuration
    app_config: ProxyServerConfiguration = ProxyServerConfiguration(
        db_storage_path=conf.DB_STORAGE_PATH,
        db_storage_limit_gb=conf.DB_STORAGE_LIMIT_GB,
        supported_registries=conf.SUPPORTED_REGISTRIES,
    )
    appProxyServer.init(app_config)

    # Register the v1 routes
    register_v1_routes(server, socketio)

    # Start the server
    socketio.run(
        app=server,
        host="0.0.0.0",
        port=conf.SERVER_PORT,
        debug=False,
        log_output=True,
        log=logging.getLogger(),
    )
