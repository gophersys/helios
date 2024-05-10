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
    TestStepResult, ExecuteResponse, ExecuteRequest
)

from protos.cluster_operator.cluster_operator_pb2 import (
    ClusterStatus, HealthCheckRequest, HealthCheckResponse,
    NodeInfo, GetClusterInfoRequest, GetClusterInfoResponse,
    RegisterTestRequest, RegisterTestResponse,
    ListTestsRequest, ListTestsResponse,
    GetDeploymentInfoRequest, GetDeploymentInfoResponse,
    ExecuteTestResponse, 
)
from protos.cluster_operator.cluster_operator_pb2_grpc import ClusterOperatorServicer

class ClusterOperatorServicerProvider(ClusterOperatorServicer):
    # -------------------------------------------------------------------------------------------------
    #                                                                                 Pass Test Cluster
    # -----------------------------------------------------------------------------------------------*/
    def __init__(self, operator:ClusterOperator):
        self.operator:ClusterOperator = operator

    # -------------------------------------------------------------------------------------------------
    #                                                                                       HealthCheck
    # -----------------------------------------------------------------------------------------------*/
    def HealthCheck(self, request:HealthCheckRequest, context):
        status, error = self.operator.get_status()
        return HealthCheckResponse(status=status, error=error)
    
    # -------------------------------------------------------------------------------------------------
    #                                                                                    GetClusterInfo
    # -----------------------------------------------------------------------------------------------*/
    def GetClusterInfo(self, request:GetClusterInfoRequest, context):
        # Call app to get info
        response:GetClusterInfoResponse = GetClusterInfoResponse(
            nodes_info=self.operator.get_nodes_info()
        )
        
        return response
    
    # -------------------------------------------------------------------------------------------------
    #                                                                                 GetDeploymentInfo
    # -----------------------------------------------------------------------------------------------*/
    def GetDeploymentInfo(self, request:GetDeploymentInfoRequest, context):
        # Call app to get info
        response:GetDeploymentInfoResponse = GetDeploymentInfoResponse(
            deployment_info=self.operator.get_deployment_info()
        )
        
        return response
    
    # -------------------------------------------------------------------------------------------------
    #                                                                                     Register Test
    # -----------------------------------------------------------------------------------------------*/
    def RegisterTest(self, request:RegisterTestRequest, context):
        logging.debug("RegisterTest handler called")
        
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
    
    # -------------------------------------------------------------------------------------------------
    #                                                                                         ListTests
    # -----------------------------------------------------------------------------------------------*/
    def ListTests(self, request:ListTestsRequest, context):
        logging.debug("ListTests handler called")
        
        response:ListTestsResponse = ListTestsResponse(
            tests = self.operator.list_tests()
        )
        
        return response
    
    # -------------------------------------------------------------------------------------------------
    #                                                                                  ExecuteTest
    # -----------------------------------------------------------------------------------------------*/

    def ExecuteTest(self, request, context):
        logging.debug("ExecuteTest handler called")
        logging.warning(request)
        
        # Create and send a request to the test service
        request_to_test_service = ExecuteRequest(
            config=request.config,
            nodes=request.nodes
        )
        
        test = self.operator.get_test_entry(request.uuid)
        
        # Communicate with the test service
        try:
            for response in test.stub.Execute(request_to_test_service):
                logging.info(f"Received response from test service: {response}")
                test_response = ExecuteTestResponse(
                    results=response.results
                )
                yield test_response
        except grpc.RpcError as e:
            logging.error(f"Error in communication with the test service: {str(e)}")
            context.abort(grpc.StatusCode.ABORTED, "Test execution failed due to an RPC error.")
        
        # # Call the test in a new thread, and send the responses back to the main RPC
        # def results_cb(results):
        #     logging.error(f"Callback: {results}")
        #     if results is None:
        #         yield
                
        #     response = ExecuteTestResponse(
        #         results=results
        #     )
            
        #     logging.warning(f"Received response: {response}")
        #     yield response
        
        # # Call the operator 
        # error = self.operator.execute_test(request.uuid, request.config, request.nodes, results_cb)
        # if error:
        #     logging.error(f"Could not start test execution: {error}")
        #     context.abort(grpc.StatusCode.ABORTED, f"Test execution failed: {error}")
        
        # logging.info(f"Test {request.uuid} executed succesfully")
        # yield
