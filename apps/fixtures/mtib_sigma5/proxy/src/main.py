# Standard includes
import logging

# Library includes
from flask import Flask

# App includes
from config import conf

# Routes
from v1.health.healthcheck import healthcheck_bp
from v1.cluster.register import cluster_register_bp

# -------------------------------------------------------------------------------------------------
#                                                                                       HTTP Server
# -----------------------------------------------------------------------------------------------*/
app = Flask(__name__)

# Route Blue Prints
app.register_blueprint(healthcheck_bp)
app.register_blueprint(cluster_register_bp)

# -------------------------------------------------------------------------------------------------
#                                                                                              Main
# -----------------------------------------------------------------------------------------------*/
if __name__ == '__main__':
    print(conf)
    app.run(port=conf.SERVER_PORT,debug=True)
    
