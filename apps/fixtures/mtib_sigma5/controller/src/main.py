# Standard includes
from concurrent import futures
from typing import Tuple, Optional
import grpc
import logging
import threading
import time
import requests
import socket
import sys

# App includes
from config import conf
from src.providers.mtib_controller_provider import MtibControllerServicerProvider
from python.clusters.cluster import TestCluster, TestClusterConfig
from python.clusters.mtib_sigma5 import sigma5_test_cluster_config
from src.app.controller import ControllerServer

# Protocol includes
from protos.mtib_controller.mtib_controller_pb2 import *
from protos.mtib_controller.mtib_controller_pb2_grpc import add_MtibControllerServicer_to_server

# -------------------------------------------------------------------------------------------------
#                                                                                     Cluster Setup
# -----------------------------------------------------------------------------------------------*/
def new_cluster(config:TestClusterConfig) -> Tuple[bool, str, Optional[TestCluster]]:
    try:
        cluster:TestCluster = TestCluster(config)
    except Exception as e:
        return False, f"Fatal error trying to instantiate cluster: {e}", None

    return True, "", cluster

# -------------------------------------------------------------------------------------------------
#                                                                                       gRPC Server
# -----------------------------------------------------------------------------------------------*/
def setup_grpc_server(cluster:TestCluster) -> Tuple[bool, Optional[grpc.Server]]:
    # Create gRPC server
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    
    # Register the MTIB service
    provider = MtibControllerServicerProvider(cluster=cluster)
    add_MtibControllerServicer_to_server(provider, server)
        
    # Serve
    server.add_insecure_port(f'[::]:{conf.GRPC_SERVER_PORT}') 
    server.start()
    
    logging.info(f"Server started, listening on port {conf.GRPC_SERVER_PORT}.") 

    return True, server

# -------------------------------------------------------------------------------------------------
#                                                                                        Keep Alive
# -----------------------------------------------------------------------------------------------*/
def cluster_registration():
    """ Runs a periodic registration query to the proxy server """

    # Create the URL the proxy should use to connect to this server (us)
    hostname = socket.gethostname()  
    grpc_port = conf.GRPC_SERVER_PORT 
    url = f"{hostname}:{grpc_port}"

    # Populate the request payload with the hostname of the device and the port we're serving gRPC on
    registration_payload = {
        "url": url,
    }

    # Allow some time for the network and server to be setup
    time.sleep(5) 

    # Send the request to connect periodically 
    while True:
        try:
            registration_endpoint = f"{conf.PROXY_SERVER_URL}/v1/cluster/register"  
            response = requests.post(registration_endpoint, json=registration_payload, timeout=100)
            if response.status_code == 200:
                logging.debug(f"Successfully registered cluster with proxy at {conf.PROXY_SERVER_URL}")
            elif response.status_code == 503:
                logging.error(f"Proxy server was unable to find our URL {url}")
            else:
                logging.error(f"Error response from proxy, status code: {response.status_code}, response: {response.content}")
        except Exception as e:
            logging.warning(f"Exception occurred during cluster registration: {str(e)}")

        time.sleep(5) 

# -------------------------------------------------------------------------------------------------
#                                                                                              Main
# -----------------------------------------------------------------------------------------------*/
if __name__ == '__main__':
    logging.debug(f"App configuration: \n{conf}")

    # Instantiate a new cluster
    success, error, cluster = new_cluster(sigma5_test_cluster_config)
    if not success:
        logging.error(f"Could not create cluster instance: {error}")
        sys.exit(1)

    # Setup gRPC server
    success, server = setup_grpc_server(cluster)
    if not success:
        raise ValueError("Error setting up GRPC server")

    # Setup the cluster
    success, error = cluster.setup()
    if not success:
        logging.error(f"Unable to setup cluster: {error}")
        ControllerServer().set_internal_error(error)

    # Create a new thread to start registration
    registration_thread = threading.Thread(target=cluster_registration, daemon=True)
    registration_thread.start()

    # Await for kill signal
    try:
        server.wait_for_termination()
    except KeyboardInterrupt:
        logging.warning("Kill signal detected, stopping server...")
        server.stop(0)
        logging.info("Server stopped.")
        sys.exit(1)