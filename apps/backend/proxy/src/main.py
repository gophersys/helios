# Standard includes
import logging
import sys
import eventlet

eventlet.monkey_patch(socket=True, select=False, time=False, os=False, thread=False)

# Library includes
from flask import Flask, request
from flask_socketio import SocketIO, emit, join_room

# App includes
from config import conf
from src.middleware.permissions import authMiddleware, AuthMiddlewareConfig
from src.services.proxy import ProxyServerConfiguration, appProxyServer

# Server
server = Flask(__name__)
socketio = SocketIO(server, debug=True, cors_allowed_origins="*", async_mode="eventlet")


# ----------------------------------------------------------------------------------
#                                                                             Routes
# --------------------------------------------------------------------------------*/
# Log filter
from api.v1.log_filter import LogFilter

# Healthcheck
from api.v1.healthcheck import healthcheck_bp  # GET /v1/healthcheck

server.register_blueprint(healthcheck_bp)  # GET /v1/healthcheck

# Storage
from api.v1.storage import storage_bp

server.register_blueprint(storage_bp)  # GET /v1/storage

# Auth
from api.v1.auth.tokens.request import tokens_request_bp

server.register_blueprint(tokens_request_bp)  # POST /v1/auth/tokens/request

from api.v1.auth.tokens.refresh import token_refresh_bp

server.register_blueprint(token_refresh_bp)  # POST /v1/auth/tokens/refresh

# Devices
from api.v1.devices.validate_snr import devices_snr_validate_bp

server.register_blueprint(devices_snr_validate_bp)  # POST /v1/devices/snr/validate

from api.v1.devices.assign_device_id import devices_assign_id_bp

server.register_blueprint(devices_assign_id_bp)  # POST /v1/devices/ids/assign

from api.v1.devices.save_iccid import devices_save_iccid_bp

server.register_blueprint(devices_save_iccid_bp)  # POST /v1/devices/iccids/save

from api.v1.devices.upload_pub_key import devices_save_pub_key_bp

server.register_blueprint(devices_save_pub_key_bp)  # POST /v1/devices/keys/upload

# Clusters
from api.v1.clusters.create import clusters_create_bp

server.register_blueprint(clusters_create_bp)  # POST /v1/clusters

from api.v1.clusters.get_uuid import clusters_get_uuid_bp

server.register_blueprint(clusters_get_uuid_bp)  # GET /v1/clusters/<uuid>

from api.v1.clusters.list import clusters_list_bp

server.register_blueprint(clusters_list_bp)  # GET /v1/clusters

from api.v1.clusters.delete_all import clusters_delete_all_bp

server.register_blueprint(clusters_delete_all_bp)  # DELETE /v1/clusters

from api.v1.clusters.delete_uuid import clusters_delete_uuid_bp

server.register_blueprint(clusters_delete_uuid_bp)  # DELETE /v1/clusters/<uuid>

from api.v1.clusters.register_uuid import clusters_register_uuid_bp

server.register_blueprint(clusters_register_uuid_bp)  # POST /v1/clusters/<uuid>/register

# Cluster Deployments
from api.v1.clusters.deployments.create import clusters_deployments_create_bp

server.register_blueprint(clusters_deployments_create_bp)  # POST /v1/clusters/<uuid>/deployments

from api.v1.clusters.deployments.get_uuid import clusters_deployments_get_uuid_bp

server.register_blueprint(clusters_deployments_get_uuid_bp)  # GET /v1/clusters/<uuid>/deployments/<uuid>

from api.v1.clusters.deployments.status_uuid import clusters_deployments_status_uuid_bp

server.register_blueprint(clusters_deployments_status_uuid_bp)  # GET /v1/clusters/<uuid>/deployments/<uuid>/status

from api.v1.clusters.deployments.list import clusters_deployments_list_bp

server.register_blueprint(clusters_deployments_list_bp)  # GET /v1/clusters/<uuid>/deployments

from api.v1.clusters.deployments.delete_all import clusters_deployments_delete_all_bp

server.register_blueprint(clusters_deployments_delete_all_bp)  # DELETE /v1/clusters/<uuid>/deployments

from api.v1.clusters.deployments.delete_uuid import clusters_deployments_delete_uuid_bp

server.register_blueprint(clusters_deployments_delete_uuid_bp)  # DELETE /v1/clusters/<uuid>/deployments/<uuid>

from api.v1.clusters.deployments.apply_uuid import clusters_deployments_apply_uuid_bp

server.register_blueprint(clusters_deployments_apply_uuid_bp)  # POST /v1/clusters/<uuid>/deployments/<uuid>/apply

# Cluster Tests
from api.v1.clusters.tests.get_uuid import clusters_tests_get_uuid_bp

server.register_blueprint(clusters_tests_get_uuid_bp)  # GET /v1/clusters/<uuid>/tests/<uuid>

from api.v1.clusters.tests.list import clusters_tests_list_bp

server.register_blueprint(clusters_tests_list_bp)  # GET /v1/clusters/<uuid>/tests

from api.v1.clusters.tests.exec_uuid import clusters_tests_exec_uuid_bp

server.register_blueprint(clusters_tests_exec_uuid_bp)  # ws://<url>/exec_test

from api.v1.clusters.tests.exec_uuid import clusters_tests_exec_uuid_socketio_handler


@socketio.on("exec_test")
def handle_ws_event_exec_test(data):
    clusters_tests_exec_uuid_socketio_handler(data, socketio)


from api.v1.clusters.tests.stop_uuid import clusters_tests_stop_uuid_bp

server.register_blueprint(clusters_tests_stop_uuid_bp)  # POST /v1/clusters/<uuid>/tests/<uuid>/stop

# Cluster executions
from api.v1.clusters.executions.list import clusters_executions_list_bp

server.register_blueprint(clusters_executions_list_bp)  # GET /v1/clusters/<uuid>/executions

from api.v1.clusters.executions.get_uuid import clusters_executions_get_uuid_bp

server.register_blueprint(clusters_executions_get_uuid_bp)  # GET /v1/clusters/<uuid>/executions/<uuid>

from api.v1.clusters.executions.delete_uuid import clusters_executions_delete_uuid_bp

server.register_blueprint(clusters_executions_delete_uuid_bp)  # DELETE /v1/clusters/<uuid>/executions/<uuid>

from api.v1.clusters.executions.delete_all import clusters_executions_delete_all_bp

server.register_blueprint(clusters_executions_delete_all_bp)  # DELETE /v1/clusters/<uuid>/executions

# ----------------------------------------------------------------------------------
#                                                                              Entry
# --------------------------------------------------------------------------------*/
if __name__ == "__main__":
    logging.debug(f"App configuration: \n{conf}")

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

    # Add a log filter to avoid spamming the logs with commonly hit routes
    logging.getLogger().addFilter(LogFilter())

    # Instantiate server with desired configuration
    app_config: ProxyServerConfiguration = ProxyServerConfiguration(
        db_storage_path=conf.DB_STORAGE_PATH,
        db_storage_limit_gb=conf.DB_STORAGE_LIMIT_GB,
        supported_registries=conf.SUPPORTED_REGISTRIES,
    )
    appProxyServer.init(app_config)

    # Start the server
    socketio.run(
        app=server,
        host="0.0.0.0",
        port=conf.SERVER_PORT,
        debug=False,
        log_output=True,
        log=logging.getLogger(),
    )
