# Standard includes
import grpc
import logging
import time
import threading
from typing import List, Optional
from concurrent.futures import Future,ThreadPoolExecutor
from queue import Queue
import uuid
import os

# App includes
from config import conf
from src.services.operator import ClusterOperator

# Protocol includes
from protos.cluster_test.cluster_test_pb2 import (
    TestStepResult, ExecuteResponse, ExecuteRequest, StopRequest, StopResponse
)

from protos.cluster_operator.cluster_operator_pb2 import (
    ClusterStatus, HealthCheckRequest, HealthCheckResponse,
    NodeInfo, GetClusterInfoRequest, GetClusterInfoResponse,
    RegisterTestRequest, RegisterTestResponse,
    ListTestsRequest, ListTestsResponse,
    GetDeploymentInfoRequest, GetDeploymentInfoResponse,
    ExecuteTestResponse, StopTestResponse
)
from protos.cluster_operator.cluster_operator_pb2_grpc import ClusterOperatorServicer

class ClusterOperatorServicerProvider(ClusterOperatorServicer):
    def __init__(self, operator:ClusterOperator):
        self.operator:ClusterOperator = operator

    def HealthCheck(self, request:HealthCheckRequest, context):
        status, error = self.operator.get_status()
        return HealthCheckResponse(status=status, error=error)
    
    def GetClusterInfo(self, request:GetClusterInfoRequest, context):
        # Call app to get info
        response:GetClusterInfoResponse = GetClusterInfoResponse(
            nodes_info=self.operator.get_nodes_info()
        )
        
        return response
    
    def GetDeploymentInfo(self, request:GetDeploymentInfoRequest, context):
        # Call app to get info
        response:GetDeploymentInfoResponse = GetDeploymentInfoResponse(
            deployment_info=self.operator.get_deployment_info()
        )
        
        return response
    
    def RegisterTest(self, request:RegisterTestRequest, context):
        response:RegisterTestResponse = RegisterTestResponse(
            success=True
        )
        
        # Call the object method
        error = self.operator.register_test(request.port, request.info)
        if error:
            logging.error(error)
            response.success = False
            response.error = error
            
        return response
    
    def ListTests(self, request:ListTestsRequest, context):
        response:ListTestsResponse = ListTestsResponse(
            tests = self.operator.list_tests()
        )
        
        return response
    
    def ExecuteTest(self, request, context):
        # Create and send a request to the test service
        request_to_test_service = ExecuteRequest(
            config=request.config,
            nodes=request.nodes
        )
        
        test = self.operator.get_test_entry(request.uuid)
        
        # Communicate with the test service
        try:
            for response in test.stub.Execute(request_to_test_service):
                test_response = ExecuteTestResponse(
                    results=response.results
                )
                yield test_response
        except grpc.RpcError as e:
            context.abort(grpc.StatusCode.ABORTED, f"{e.details()}")
        
    def StopTest(self, request, context):
        # Find the test
        test = self.operator.get_test_entry(request.uuid)
        
        # Communicate with the test service
        try:
            response:StopResponse = test.stub.Stop(StopRequest())
            return StopTestResponse(
                error=response.error
            )
        except grpc.RpcError as e:
            context.abort(grpc.StatusCode.ABORTED, f"An error ocurred trying to stop test: {e.details()}")

