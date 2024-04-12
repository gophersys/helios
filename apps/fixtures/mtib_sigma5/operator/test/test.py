# Standard libraryes
import hashlib
import os
import sys
import time
import logging
import subprocess
import threading

# 3rd party libraries
import grpc
import typer
from typing import Optional, Tuple, Literal
from rich import print as rprint
from rich.progress import Progress

# Protocol includes
from protos.cluster_controller.cluster_controller_pb2_grpc import ClusterControllerStub
from protos.cluster_controller.cluster_controller_pb2 import (
    HealthCheckRequest, HealthCheckResponse
)

SERVER_ADDRESSES = 'localhost:50051'

# -------------------------------------------------------------------------------------------------
#                                                                                              Main
# -----------------------------------------------------------------------------------------------*/
if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)

    # Instantiate a new stub withour TLS 
    channel = grpc.insecure_channel(SERVER_ADDRESSES)
    server = ClusterControllerStub(channel)

    while True:
        response = server.HealthCheck(HealthCheckRequest())

        if not response.ok:
            logging.error("Controller server responded with OK set to false")
            sys.exit(1)

        logging.info("Health check OK.")
        time.sleep(1)