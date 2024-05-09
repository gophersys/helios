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
    TestStepResult, ExecuteResponse
)

from protos.cluster_operator.cluster_operator_pb2 import (
    ClusterStatus, HealthCheckRequest, HealthCheckResponse,
    NodeInfo, GetClusterInfoRequest, GetClusterInfoResponse,
    RegisterTestRequest, RegisterTestResponse,
    ListTestsRequest, ListTestsResponse,
    GetDeploymentInfoRequest, GetDeploymentInfoResponse,
    ExecuteTestResponse
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
    
    # # -------------------------------------------------------------------------------------------------
    # #                                                                                             Reset
    # # -----------------------------------------------------------------------------------------------*/
    # def Reset(self, request:ResetRequest, context):
    #     response:ResetResponse = ResetResponse()
    #     return response
    
    # # -------------------------------------------------------------------------------------------------
    # #                                                                                         ListTests
    # # -----------------------------------------------------------------------------------------------*/
    # def ListTests(self, request:ListTestsRequest, context):
    #     """Gets all the test available in the cluster"""
    #     return ListTestsResponse(
    #         tests = self.cluster.get_tests()
    #     )
    
    # -------------------------------------------------------------------------------------------------
    #                                                                                  ExecuteTest
    # -----------------------------------------------------------------------------------------------*/
    def ExecuteTest(self, request, context):
        logging.warning(request)
        
        # Simulate the execution of several test steps
        test_steps = [
            {"execError": "", "success": True, "detailedResult": "Initialization complete.", "progressPercentage": 20, "timestamp": str(time.time())},
            {"execError": "", "success": True, "detailedResult": "Loading modules.", "progressPercentage": 40, "timestamp": str(time.time())},
            {"execError": "Error loading module", "success": False, "detailedResult": "Module failed to load.", "progressPercentage": 60, "timestamp": str(time.time())},
            {"execError": "", "success": True, "detailedResult": "Cleanup and finalizing.", "progressPercentage": 80, "timestamp": str(time.time())},
            {"execError": "", "success": True, "detailedResult": "Test completed successfully.", "progressPercentage": 100, "timestamp": str(time.time())}
        ]
        
        for step in test_steps:
            # Create a TestStepResult message
            test_step_result = TestStepResult(
                execError=step["execError"],
                success=step["success"],
                detailedResult=step["detailedResult"],
                progressPercentage=step["progressPercentage"],
                timestamp=step["timestamp"]
            )

            # Wrap the result in an ExecuteResponse and then in an ExecuteTestResponse
            response = ExecuteTestResponse(
                results=[ExecuteResponse(results=[test_step_result])]
            )
            yield response
            time.sleep(1)  # Simulate time delay between steps        
