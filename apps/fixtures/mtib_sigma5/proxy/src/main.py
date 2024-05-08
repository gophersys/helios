# Standard includes
import logging

# Library includes
from flask import Flask, request
from flask_socketio import SocketIO, join_room, emit
import eventlet.wsgi

# App includes
from config import conf
from src.services.proxy import appProxyServer, ProxyServerConfiguration

# Server
server = Flask(__name__) 
socketio = SocketIO(server,debug=True,cors_allowed_origins='*',async_mode='eventlet')
    
# ----------------------------------------------------------------------------------
#                                                                             Routes
# --------------------------------------------------------------------------------*/
# Log filter
from api.v1.log_filter import LogFilter

# Healthcheck
from api.v1.healthcheck import (healthcheck_bp)                                         # GET /v1/healthcheck                                                    
server.register_blueprint(healthcheck_bp)

# Clusters
from api.v1.clusters.create import clusters_create_bp                                   # POST /v1/clusters
server.register_blueprint(clusters_create_bp)

from api.v1.clusters.get_uuid import clusters_get_uuid_bp                               # GET /v1/clusters/<uuid>
server.register_blueprint(clusters_get_uuid_bp)

from api.v1.clusters.list import clusters_list_bp                                       # GET /v1/clusters
server.register_blueprint(clusters_list_bp)

from api.v1.clusters.delete_all import clusters_delete_all_bp                           # DELETE /v1/clusters
server.register_blueprint(clusters_delete_all_bp)

from api.v1.clusters.delete_uuid import clusters_delete_uuid_bp                         # DELETE /v1/clusters/<uuid>
server.register_blueprint(clusters_delete_uuid_bp)

from api.v1.clusters.register_uuid import clusters_register_uuid_bp                     # POST /v1/clusters/<uuid>/register
server.register_blueprint(clusters_register_uuid_bp)

# Cluster Deployments
from api.v1.clusters.deployments.create import clusters_deployments_create_bp           # POST /v1/clusters/<uuid>/deployments
server.register_blueprint(clusters_deployments_create_bp)

from api.v1.clusters.deployments.get_uuid import clusters_deployments_get_uuid_bp       # GET /v1/clusters/<uuid>/deployments/<uuid>
server.register_blueprint(clusters_deployments_get_uuid_bp)

from api.v1.clusters.deployments.status_uuid import clusters_deployments_status_uuid_bp # GET /v1/clusters/<uuid>/deployments/<uuid>/status
server.register_blueprint(clusters_deployments_status_uuid_bp)

from api.v1.clusters.deployments.list import clusters_deployments_list_bp               # GET /v1/clusters/<uuid>/deployments
server.register_blueprint(clusters_deployments_list_bp)

from api.v1.clusters.deployments.delete_all import clusters_deployments_delete_all_bp   # DELETE /v1/clusters/<uuid>/deployments
server.register_blueprint(clusters_deployments_delete_all_bp)

from api.v1.clusters.deployments.delete_uuid import clusters_deployments_delete_uuid_bp # DELETE /v1/clusters/<uuid>/deployments/<uuid>
server.register_blueprint(clusters_deployments_delete_uuid_bp)

from api.v1.clusters.deployments.apply_uuid import clusters_deployments_apply_uuid_bp   # POST /v1/clusters/<uuid>/deployments/<uuid>/apply
server.register_blueprint(clusters_deployments_apply_uuid_bp)

# Cluster Tests

from api.v1.clusters.tests.get_uuid import clusters_tests_get_uuid_bp                   # GET /v1/clusters/<uuid>/tests/<uuid>
server.register_blueprint(clusters_tests_get_uuid_bp)

from api.v1.clusters.tests.list import clusters_tests_list_bp                           # GET /v1/clusters/<uuid>/tests
server.register_blueprint(clusters_tests_list_bp)

from api.v1.clusters.tests.exec_uuid import clusters_tests_exec_uuid_bp                # POST /v1/clusters/<uuid>/tests/<uuid>/exec
server.register_blueprint(clusters_tests_exec_uuid_bp)

from api.v1.clusters.tests.exec_uuid import clusters_tests_exec_uuid_socketio_handler  # ws://<url>/exec_test
@socketio.on('exec_test')
def handle_ws_event_exec_test(data):
    clusters_tests_exec_uuid_socketio_handler(data, socketio)
        
# ----------------------------------------------------------------------------------
#                                                                              Entry 
# --------------------------------------------------------------------------------*/
if __name__ == '__main__':
    logging.debug(f"App configuration: \n{conf}")
    
    # Add a log filter to avoid spamming the logs with commonly hit routes
    logging.getLogger().addFilter(LogFilter())
    
    # Instantiate server with desired configuration
    app_config:ProxyServerConfiguration = ProxyServerConfiguration(
        db_storage_path=conf.DB_STORAGE_PATH,
        db_storage_limit_gb=conf.DB_STORAGE_LIMIT_GB,
        supported_registries=conf.SUPPORTED_REGISTRIES,
        socketio=socketio
    )
    appProxyServer.init(app_config)
    
    # Start the server
    socketio.run(app=server,
                 host='0.0.0.0',
                 port=conf.SERVER_PORT,
                 debug=False,
                 log_output=True,
                 log=logging.getLogger())
    
