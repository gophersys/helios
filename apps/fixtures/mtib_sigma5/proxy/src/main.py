# Standard includes
import logging

# Library includes
from flask import Flask

# App includes
from config import conf
from src.services.proxy import appProxyServer, ProxyServerConfiguration

# Server
server = Flask(__name__) 

# ----------------------------------------------------------------------------------
#                                                                             Routes
# --------------------------------------------------------------------------------*/
from api.v1.health.healthcheck import (                                                 
    healthcheck_bp,                                                                     # POST /v1/healthcheck
    HealthLogFilter
    )
server.register_blueprint(healthcheck_bp)

# Clusters
from api.v1.clusters.create import clusters_create_bp                                   # POST /v1/clusters
server.register_blueprint(clusters_create_bp)

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

from api.v1.clusters.deployments.delete_uuid import clusters_deployments_delete_uuid_bp # DELETE /v1/clusters/<uuid>/deployments/<uuid>
server.register_blueprint(clusters_deployments_delete_uuid_bp)

# ----------------------------------------------------------------------------------
#                                                                              Entry 
# --------------------------------------------------------------------------------*/
if __name__ == '__main__':
    logging.debug(f"App configuration: \n{conf}")
    
    # Remove healthcheck route hits from logs
    logger = logging.getLogger('werkzeug')
    logger.addFilter(HealthLogFilter()) # <- More info here
    
    # Instantiate server with desired configuration
    app_config:ProxyServerConfiguration = ProxyServerConfiguration(
        db_storage_path=conf.DB_STORAGE_PATH,
        db_storage_limit_gb=conf.DB_STORAGE_LIMIT_GB,
        supported_registries=conf.SUPPORTED_REGISTRIES,
    )
    appProxyServer.init(app_config)
    
    # Start the server
    server.run(host='0.0.0.0', port=conf.SERVER_PORT, debug=False)
    
