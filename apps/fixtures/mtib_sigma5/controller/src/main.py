# Standard includes
from concurrent import futures
from typing import Tuple, Optional
import logging

# Library includes
import grpc
from flask import Flask

# App includes
from config import conf

# Routes
from v1.healthcheck import healthcheck_bp
from v1.tests import tests_bp
from v1.run import run_bp

# Tests
import tests.electrical

# Protocol includes
from protos.mtib_cs_pi.mtib_cs_pi_pb2_grpc import MtibCsPiStub

# -------------------------------------------------------------------------------------------------
#                                                                                       HTTP Server
# -----------------------------------------------------------------------------------------------*/
app = Flask(__name__)

app.register_blueprint(healthcheck_bp)
app.register_blueprint(tests_bp)
app.register_blueprint(run_bp)

# -------------------------------------------------------------------------------------------------
#                                                                                              Main
# -----------------------------------------------------------------------------------------------*/
if __name__ == '__main__':
    print(conf)
    app.run(port=conf.SERVER_PORT,debug=True)
    
