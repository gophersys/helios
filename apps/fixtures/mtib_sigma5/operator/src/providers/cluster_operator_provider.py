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
from protos.cluster_operator.cluster_operator_pb2 import (
    ClusterStatus, HealthCheckRequest, HealthCheckResponse,
    NodeInfo, GetClusterInfoRequest, GetClusterInfoResponse,
    RegisterTestRequest, RegisterTestResponse,
    ListTestsRequest, ListTestsResponse,
    GetDeploymentInfoRequest, GetDeploymentInfoResponse
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
    
    # # -------------------------------------------------------------------------------------------------
    # #                                                                                  ExecuteTest
    # # -----------------------------------------------------------------------------------------------*/

    # def ExecuteTest(self, request, context):
    #     # Create a unique test identifier for this test instance
    #     test_id = str(uuid.uuid4())

    #     # We use a queue to communicate the execute callback and the response stream of this RPC
    #     results_queue = Queue()

    #     # This gets called every time a new step completes in the execution cycle
    #     def callback(complete: bool, error: str, sequence:int, results: Optional[List[TestStepResult]] = None):
    #         if error:
    #             results_queue.put(('error', error))
    #         elif not results:
    #             results_queue.put(('error', "Empty results array"))
    #         else:
    #             results_queue.put(('results', results))
            
    #         if complete:
    #             results_queue.put(('complete', None))

    #     # Execute the test in a separate thread to avoid blocking gRPC thread
    #     executor = ThreadPoolExecutor(max_workers=1)
    #     executor.submit(self.cluster.execute_test, request.testId, request.runnerIds, callback)

    #     while True:
    #         # Block until a message is available in the queue
    #         message_type, message = results_queue.get()

    #         if message_type == 'error':
    #             logging.error(f"Test execution error: {message}")
    #             context.abort(grpc.StatusCode.INTERNAL, str(message))
    #             break

    #         elif message_type == 'results':
    #             yield ExecuteTestResponse(instance=test_id,
    #                                       sequence=1, # How do we add the sequence cleanly in here
    #                                       results=message)

    #         elif message_type == 'complete':
    #             logging.info("Last result was received, returning on RPC")
    #             break

    #     # Shutdown the executor
    #     executor.shutdown(wait=True)
