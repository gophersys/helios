# Standard includes
from concurrent import futures
from typing import Tuple, Optional
import grpc
import logging
import socket
import sys

# App includes
from config import conf
from src.providers.cluster_operator_provider import ClusterOperatorServicerProvider
from src.services.operator import ClusterOperator, ClusterOperatorConfig

# Protocol includes
from protos.cluster_operator.cluster_operator_pb2 import *
from protos.cluster_operator.cluster_operator_pb2_grpc import add_ClusterOperatorServicer_to_server

# -------------------------------------------------------------------------------------------------
#                                                                                      Server Start
# -----------------------------------------------------------------------------------------------*/
def start_server(operator:ClusterOperator) -> Tuple[str, Optional[grpc.Server]]:
    # Create gRPC server
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    
    # Register the MTIB service
    provider = ClusterOperatorServicerProvider(operator)
    add_ClusterOperatorServicer_to_server(provider, server)
        
    # Serve
    server.add_insecure_port(f'[::]:{conf.GRPC_SERVER_PORT}') 
    server.start()
    
    logging.info(f"Operator server started, listening on port {conf.GRPC_SERVER_PORT}.") 

    return "", server

# -------------------------------------------------------------------------------------------------
#                                                                                              Main
# -----------------------------------------------------------------------------------------------*/
if __name__ == '__main__':
    logging.debug(f"Operator app environment configuration: \n{conf}")

    # Instantiate an operator service instance
    config:ClusterOperatorConfig = ClusterOperatorConfig(
        uuid=conf.CLUSTER_UUID,
        proxy_url=conf.PROXY_SERVER_URL,
        registry_port=conf.LOCAL_REGISTRY_PORT,
        grpc_server_url=f"{socket.gethostname()}:{conf.GRPC_SERVER_PORT}",
        runners_hostnames=[
            "control-plane",
            "slot-1",
            "slot-2",
            "slot-3",
            "slot-4",
            "slot-5"
        ],
        kubeconfig_path=conf.KUBECONFIG_PATH
    )

    operator:ClusterOperator = ClusterOperator(config)

    error = operator.init()
    if error:
        logging.error(f"Could not create operator: {error}")

    # Setup gRPC server (we serve as an operator)
    error, server = start_server(operator)
    if error:
        logging.error(f"Could not start gRPC server: {error}")

    # Await for kill signal
    try:
        server.wait_for_termination()
    except KeyboardInterrupt:
        logging.warning("Kill signal detected, stopping server...")
        server.stop(0)
        logging.info("Operator server stopped.")
        sys.exit(1)