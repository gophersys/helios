# Standard includes
import logging

# Library includes
from flask import Flask

# App includes
from config import conf

# Routes
from api.v1.health.healthcheck import healthcheck_bp, SuppressHealthCheckLoggingFilter

from api.v1.cluster.create import cluster_create_bp
from api.v1.cluster.read import cluster_read_bp
from api.v1.cluster.update import cluster_update_bp
from api.v1.cluster.delete import cluster_delete_bp
from api.v1.cluster.register import cluster_register_bp

from api.v1.cluster.deployment.get import cluster_get_deployment_bp

from api.v1.cluster.tests.list import cluster_tests_list_bp
# -------------------------------------------------------------------------------------------------
#                                                                                       HTTP Server
# -----------------------------------------------------------------------------------------------*/
app = Flask(__name__)

app.register_blueprint(healthcheck_bp)

app.register_blueprint(cluster_create_bp)
app.register_blueprint(cluster_read_bp)
app.register_blueprint(cluster_update_bp)
app.register_blueprint(cluster_delete_bp)
app.register_blueprint(cluster_register_bp)

app.register_blueprint(cluster_get_deployment_bp)

app.register_blueprint(cluster_tests_list_bp)


# -------------------------------------------------------------------------------------------------
#                                                                                              Main
# -----------------------------------------------------------------------------------------------*/
if __name__ == '__main__':
    logging.debug(f"App configuration: \n{conf}")
    
    # Remove healthcheck route hits from logs
    logger = logging.getLogger('werkzeug')
    logger.addFilter(SuppressHealthCheckLoggingFilter())
    
    # Start the server
    app.run(host='0.0.0.0', port=conf.SERVER_PORT, debug=False)
    
