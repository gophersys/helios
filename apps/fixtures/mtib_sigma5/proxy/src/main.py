# Standard includes
import logging

# Library includes
from flask import Flask

# App includes
from config import conf

# Routes
from v1.health.healthcheck import healthcheck_bp
from v1.cluster.register import cluster_register_bp
from v1.cluster.list import cluster_list_bp
from v1.cluster.info import cluster_info_bp
from v1.cluster.tests.list import tests_list_bp
from v1.cluster.tests.exec import test_execute_bp

# -------------------------------------------------------------------------------------------------
#                                                                                       HTTP Server
# -----------------------------------------------------------------------------------------------*/
app = Flask(__name__)

# Route Blue Prints
app.register_blueprint(healthcheck_bp)
app.register_blueprint(cluster_register_bp)
app.register_blueprint(cluster_list_bp)
app.register_blueprint(cluster_info_bp)
app.register_blueprint(tests_list_bp)
app.register_blueprint(test_execute_bp)


# -------------------------------------------------------------------------------------------------
#                                                                                              Main
# -----------------------------------------------------------------------------------------------*/
if __name__ == '__main__':
    logging.debug(f"App configuration: \n{conf}")
    app.run(port=conf.SERVER_PORT,debug=True)