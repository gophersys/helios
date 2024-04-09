# Standard includes
import grpc
import logging
import time
import threading
from typing import List, Optional
from concurrent.futures import Future,ThreadPoolExecutor
from queue import Queue
import uuid

# App includes
from config import conf
from src.app.controller import ControllerServer
from src.clusters.base import BaseTestCluster

# Protocol includes
from protos.mtib_controller.mtib_controller_pb2 import (
    HealthCheckRequest, HealthCheckResponse,
    ClusterStatus, GetClusterInfoRequest, GetClusterInfoResponse,
    ResetRequest, ResetResponse,
    ListTestsRequest, ListTestsResponse,
    TestStepResult,
    TestInfo, StepInfo, ExecuteTestRequest, ExecuteTestResponse
)
from protos.mtib_controller.mtib_controller_pb2_grpc import MtibControllerServicer

class MtibControllerServicerProvider(MtibControllerServicer):
    # -------------------------------------------------------------------------------------------------
    #                                                                                 Pass Test Cluster
    # -----------------------------------------------------------------------------------------------*/
    def __init__(self, cluster:BaseTestCluster):
        self.cluster:BaseTestCluster = cluster
    
    # -------------------------------------------------------------------------------------------------
    #                                                                                 Pass Test Cluster
    # -----------------------------------------------------------------------------------------------*/
    def set_test_cluster(self, cluster:BaseTestCluster):
        self.cluster = cluster

    # -------------------------------------------------------------------------------------------------
    #                                                                                       HealthCheck
    # -----------------------------------------------------------------------------------------------*/
    def HealthCheck(self, request:HealthCheckRequest, context):
        logging.debug("HealthCheck RPC Called")
        if ControllerServer().error != "":
            return HealthCheckResponse(status=ClusterStatus.Errored, error=ControllerServer().error)
        
        return HealthCheckResponse(status=ClusterStatus.Ready)
    
    # -------------------------------------------------------------------------------------------------
    #                                                                                    GetClusterInfo
    # -----------------------------------------------------------------------------------------------*/
    def GetClusterInfo(self, request:GetClusterInfoRequest, context):
        return GetClusterInfoResponse(
            info = self.cluster.get_cluster_info()
        )
    
    # -------------------------------------------------------------------------------------------------
    #                                                                                             Reset
    # -----------------------------------------------------------------------------------------------*/
    def Reset(self, request:ResetRequest, context):
        response:ResetResponse = ResetResponse()
        return response
    
    # -------------------------------------------------------------------------------------------------
    #                                                                                         ListTests
    # -----------------------------------------------------------------------------------------------*/
    def ListTests(self, request:ListTestsRequest, context):
        """Gets all the test available in the cluster"""
        return ListTestsResponse(
            tests = self.cluster.get_tests()
        )
    
    # -------------------------------------------------------------------------------------------------
    #                                                                                  ExecuteTest
    # -----------------------------------------------------------------------------------------------*/

    def ExecuteTest(self, request, context):
        test_id = str(uuid.uuid4())
        results_queue = Queue()

        def callback(complete: bool, error: str, sequence:int, results: Optional[List[TestStepResult]] = None):
            if error:
                results_queue.put(('error', error))
            elif not results:
                results_queue.put(('error', "Empty results array"))
            else:
                results_queue.put(('results', results))
            
            if complete:
                results_queue.put(('complete', None))

        # Execute the test in a separate thread to avoid blocking gRPC thread
        executor = ThreadPoolExecutor(max_workers=1)
        executor.submit(self.cluster.execute_test, request.testId, request.runnerIds, callback)

        while True:
            # Block until a message is available in the queue
            message_type, message = results_queue.get()

            if message_type == 'error':
                logging.error(f"Test execution error: {message}")
                context.abort(grpc.StatusCode.INTERNAL, str(message))
                break

            elif message_type == 'results':
                yield ExecuteTestResponse(instance=test_id,
                                          sequence=1, # How do we add the sequence cleanly in here
                                          results=message)

            elif message_type == 'complete':
                logging.info("Last result was received, returning on RPC")
                break

        # Shutdown the executor
        executor.shutdown(wait=True)
