# Standard includes
import time
import logging

# App includes
from config import conf
import grpc
from src.tests.core import Test

# Protocol includes
from google.protobuf.timestamp_pb2 import Timestamp
from protos.cluster_test.cluster_test_pb2 import (
    HealthCheckRequest, HealthCheckResponse,
    ExecuteRequest, TestStepResult, ExecuteResponse
)
from protos.cluster_operator.cluster_operator_pb2_grpc import ClusterOperatorServicer

class ClusterTestServicerProvider(ClusterOperatorServicer):
    # -------------------------------------------------------------------------------------------------
    #                                                                                 Pass Test Cluster
    # -----------------------------------------------------------------------------------------------*/
    def __init__(self, test:Test):
        self.test:Test = test

    # -------------------------------------------------------------------------------------------------
    #                                                                                       HealthCheck
    # -----------------------------------------------------------------------------------------------*/
    def HealthCheck(self, request:HealthCheckRequest, context):        
        return HealthCheckResponse()
    
    # -------------------------------------------------------------------------------------------------
    #                                                                                    GetClusterInfo
    # -----------------------------------------------------------------------------------------------*/
    def Execute(self, request:ExecuteRequest, context):
        logging.warning(request)
        
        # Simulate the execution of several test steps
        test_steps = [
            {"execError": "", "success": True, "detailedResult": "Initialization complete.", "progressPercentage": 20, "timestamp": str(time.time())},
            {"execError": "", "success": True, "detailedResult": "Loading modules.", "progressPercentage": 40, "timestamp": str(time.time())},
            {"execError": "Error loading module", "success": False, "detailedResult": "Module failed to load.", "progressPercentage": 60, "timestamp": str(time.time())},
            {"execError": "", "success": True, "detailedResult": "Cleanup and finalizing.", "progressPercentage": 80, "timestamp": str(time.time())},
            {"execError": "", "success": True, "detailedResult": "Test completed successfully.", "progressPercentage": 100, "timestamp": str(time.time())}
        ]
        
        try:
            for step in test_steps:
                if context.is_active():  # Check if the context is still active
                    test_step_result = TestStepResult(
                        execError=step["execError"],
                        success=step["success"],
                        detailedResult=step["detailedResult"],
                        progressPercentage=step["progressPercentage"],
                        timestamp=Timestamp().FromSeconds(int(time.time()))
                    )

                    response = ExecuteResponse(results=[test_step_result])
                    logging.error(f"Yielding: {response}")
                    yield response
                    time.sleep(1)  # Simulate delay between steps
                else:
                    logging.error("Stream was cancelled or closed by client")
                    break

        except Exception as e:
            logging.error(f"An error occurred during test execution: {str(e)}")
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details('Internal server error occurred during test execution.')
            yield ExecuteResponse(results=[])  # Optionally send an empty final message to signal error

        logging.warning("Test was executed successfully")


        
        
