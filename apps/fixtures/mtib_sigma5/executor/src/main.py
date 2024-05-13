# Standard includes
from concurrent import futures
from typing import Tuple, Optional
import grpc
import logging
import socket
import time
import sys

# App includes
from config import conf
from src.providers.cluster_test_provider import ClusterTestServicerProvider
from src.tests.core import Test
from tests.electrical.test import electrical_test

# Protocol includes
from protos.cluster_test.cluster_test_pb2 import (
    TestInfo
)
from protos.cluster_test.cluster_test_pb2_grpc import add_ClusterTestServicer_to_server
from protos.cluster_operator.cluster_operator_pb2 import (
    ClusterStatus, HealthCheckRequest, HealthCheckResponse,
    RegisterTestRequest, RegisterTestResponse
)
from protos.cluster_operator.cluster_operator_pb2_grpc import ClusterOperatorStub

# -------------------------------------------------------------------------------------------------
#                                                                                     Test Register
# -----------------------------------------------------------------------------------------------*/
def register_test_with_operator(test_info:TestInfo) -> str:
    operator_url:str = f"localhost:{conf.OPERATOR_SERVER_PORT}"

    # Instantiate an operator stub and give it our info
    try:            
        # Create a gRPC channel
        channel = grpc.insecure_channel(operator_url)

        # Create a stub using the insecure channel
        stub = ClusterOperatorStub(channel)

        logging.info("Awaiting for operator readiness...")
        
        # Await infinately for the operator to be in the READY state
        ready:bool = False
        while not ready:
            try:
                # Get the operator info
                response:HealthCheckResponse = stub.HealthCheck(HealthCheckRequest())
                if response.status != ClusterStatus.STARTING:
                    ready = True
                else:
                    time.sleep(1) # Operator is not yet ready give it some time

            except grpc.RpcError as e:
                return f"Unable to get operator at {operator_url} info over gRPC method GetOperatorInfo(): {e}"
    
        logging.info("Operator is ready for test to be registerd!")
    
        # Now that the operator is ready, we can register our test with it so that it can be served
        # to the proxy 
        logging.info(f"Registering test \"{test_info.name}\" with operator at {operator_url}...")
        
        try:
            # Populate the registration request
            request:RegisterTestRequest = RegisterTestRequest(
                port = conf.TEST_SERVER_PORT,    # Where the operator is going to call us 
                info = test_info                 # The metadata of the test we're serving
            )

            # Call the operator RPC to register
            response:RegisterTestResponse = stub.RegisterTest(request)
            if not response.success:
                return f"Operator was not able to register test: {response.error} "

        except grpc.RpcError as e:
            return f"Unable to register test with operator at {operator_url} over gRPC method RegisterTest(): {e}"

        logging.info(f"Successfully registered test with operator!")
        return ""

    except grpc.RpcError as e:
        return f"Failed to connect to operator at {operator_url} over gRPC. Error: {e}"

# -------------------------------------------------------------------------------------------------
#                                                                                      Server Start
# -----------------------------------------------------------------------------------------------*/
def start_server(test:Test) -> Tuple[str, Optional[grpc.Server]]:
    # Create gRPC server
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    
    # Register the MTIB service
    provider = ClusterTestServicerProvider(test)
    add_ClusterTestServicer_to_server(provider, server)
        
    # Serve
    server.add_insecure_port(f'[::]:{conf.TEST_SERVER_PORT}') 
    server.start()
    
    logging.info(f"Test server started, listening on port {conf.TEST_SERVER_PORT}.") 

    return "", server

# -------------------------------------------------------------------------------------------------
#                                                                                              Main
# -----------------------------------------------------------------------------------------------*/
if __name__ == '__main__':
    logging.debug(f"Test app environment configuration: \n{conf}")

    # Setup gRPC server (we serve as a test)
    error, server = start_server(electrical_test)
    if error:
        logging.error(f"Could not start gRPC server: {error}")
        sys.exit(1)
        
    # Register with the operator
    error = register_test_with_operator(electrical_test.info)
    if error:
        logging.fatal(error)
        sys.exit(1)

    # Await for kill signal
    try:
        server.wait_for_termination()
    except KeyboardInterrupt:
        logging.warning("Kill signal detected, stopping server...")
        server.stop(0)
        logging.info("Operator server stopped.")
        sys.exit(1)