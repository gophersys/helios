# Standard includes
import time
import logging
from typing import List

# App includes
from config import conf
import grpc
from src.tests.core import Test

# Protocol includes
from google.protobuf.timestamp_pb2 import Timestamp
from protos.cluster_test.cluster_test_pb2 import (
    HealthCheckRequest, HealthCheckResponse,
    ExecuteRequest, TestStepResult, ExecuteResponse,
    StopRequest, StopResponse
)
from protos.cluster_operator.cluster_operator_pb2_grpc import ClusterOperatorServicer

class ClusterTestServicerProvider(ClusterOperatorServicer):
    def __init__(self, test:Test):
        self.test:Test = test

    # -----------------------------------------------------------------------------
    #                                                                   HealthCheck
    #  --------------------------------------------------------------------------*/
    def HealthCheck(self, request:HealthCheckRequest, context):        
        return HealthCheckResponse()
    
    # -----------------------------------------------------------------------------
    #                                                                       Execute
    #  --------------------------------------------------------------------------*/
    def Execute(self, request:ExecuteRequest, context):
        # Always initialize first
        error = self.test.init(request.config, request.nodes)
        if error: 
            error = f"Failed to initialize test: {error}"
            logging.error(error)
            context.abort(grpc.StatusCode.ABORTED, error)
        
        # Call execute, which will block async until this test is done, it's stopped, or it errors our
        error, results_queue = self.test.exec()
        if error:
            error = f"Failed to execute test: {error}"
            context.abort(grpc.StatusCode.ABORTED, error)

        while True:
            result = results_queue.get()
            if result is None:
                break  # Completion signal received
            response = ExecuteResponse(results=[result])
            yield response
            
        # Clean up
        error = self.test.deinit()
        if error: 
            error = f"Failed to deinitialize test: {error}"
            logging.error(error)
            context.abort(grpc.StatusCode.ABORTED, error)
        
        yield

    # -----------------------------------------------------------------------------
    #                                                                          Stop
    #  --------------------------------------------------------------------------*/
    def Stop(self, request:StopRequest, context):
        response:StopResponse = StopResponse(
            error = self.test.stop()
        )
        
        return response
        
        
        
