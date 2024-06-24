# Standard includes
import logging
import socket
import sys
from concurrent import futures
from typing import Optional, Tuple

import grpc
# App includes
from config import conf
# Protocol includes
from protos.cluster_operator.cluster_operator_pb2 import *
from protos.cluster_operator.cluster_operator_pb2_grpc import \
    add_ClusterOperatorServicer_to_server
from src.providers.cluster_operator_provider import \
    ClusterOperatorServicerProvider
from src.services.operator import ClusterOperator, ClusterOperatorConfig


# -------------------------------------------------------------------------------------------------
#                                                                                      Server Start
# -----------------------------------------------------------------------------------------------*/
def start_server(operator: ClusterOperator) -> Tuple[str, Optional[grpc.Server]]:
    # Create gRPC server
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))

    # Register the MTIB service
    provider = ClusterOperatorServicerProvider(operator)
    add_ClusterOperatorServicer_to_server(provider, server)

    # Serve
    server.add_insecure_port(f"[::]:{conf.GRPC_SERVER_PORT}")
    server.start()

    logging.info(f"Operator server started, listening on port {conf.GRPC_SERVER_PORT}.")

    return "", server


# -------------------------------------------------------------------------------------------------
#                                                                                              Main
# -----------------------------------------------------------------------------------------------*/
if __name__ == "__main__":
    logging.debug(f"Operator app environment configuration: \n{conf}")

    # Create the operator configuration
    config: ClusterOperatorConfig = ClusterOperatorConfig(
        uuid=conf.CLUSTER_UUID,
        proxy_url=conf.PROXY_SERVER_URL,
        registry_host="control-plane",
        registry_port=conf.LOCAL_REGISTRY_PORT,
        grpc_server_url=f"10.4.43.3:{conf.GRPC_SERVER_PORT}",
        nodes_hostnames=conf.NODES_HOSTNAMES,
        kubeconfig_path=conf.KUBECONFIG_PATH,
        deployments_path="/var/lib/deployments",
    )

    # Instantiate an operator object instance to be used by this server
    operator: ClusterOperator = ClusterOperator()
    error = operator.init(config)
    if error:
        logging.error(f"Could not start operator: {error}")
        sys.exit(1)

    # Setup gRPC server (we serve as an operator)
    error, server = start_server(operator)
    if error:
        logging.error(f"Could not start gRPC server: {error}")
        sys.exit(1)

    # Await for kill signal
    try:
        server.wait_for_termination()
        operator.stop()
    except KeyboardInterrupt:
        logging.warning("Kill signal detected, stopping server...")
        server.stop(None)
        operator.stop()
        logging.info("Operator server stopped.")
        sys.exit(1)
