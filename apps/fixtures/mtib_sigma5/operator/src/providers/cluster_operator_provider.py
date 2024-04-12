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
    HealthCheckRequest, HealthCheckResponse,
    OperatorStatus, OperatorInfo, GetOperatorInfoRequest, GetOperatorInfoResponse
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
        # Create a response
        response:HealthCheckResponse = HealthCheckResponse()
        response.healthy = False # Assume worst case scenario by default

        # Get the status from the operator service
        error = self.operator.get_error()
        if error:
            response.error = error 
        else:
            response.healthy = True
        
        return response
    
    # # -------------------------------------------------------------------------------------------------
    # #                                                                                    GetClusterInfo
    # # -----------------------------------------------------------------------------------------------*/
    # def GetClusterInfo(self, request:GetClusterInfoRequest, context):
    #     return GetClusterInfoResponse(
    #         info = self.cluster.get_cluster_info()
    #     )
    
    # # -------------------------------------------------------------------------------------------------
    # #                                                                         Update Cluster Deployment
    # # -----------------------------------------------------------------------------------------------*/
    # def UpdateClusterDeployment(self, request:UpdateDeploymentRequest, context):
    #     deployment_file = request.deployment_file
    #     filename = request.filename

    #     # Save the deployment file to the filesystem
    #     filepath = os.path.join('/var/lib', filename)
    #     with open(filepath, 'wb') as f:
    #         f.write(deployment_file)

    #     # Updating cluster deployment
    #     logging.info("Deployment updated succesfully to cluster")

    #     # self.cluster.setup()
        
    #     return UpdateDeploymentResponse(success=True, message="Deployment updated successfully.")
    
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
