# Standard includes
import logging
import os
import threading
import time
import uuid
from concurrent.futures import Future, ThreadPoolExecutor
from queue import Queue
from typing import List, Optional

import grpc

# App includes
from config import conf
from protocols.cluster_operator.cluster_operator_pb2 import (
    ClusterStatus,
    ExecuteTestResponse,
    GetClusterInfoRequest,
    GetClusterInfoResponse,
    GetDeploymentInfoRequest,
    GetDeploymentInfoResponse,
    HealthCheckRequest,
    HealthCheckResponse,
    ListTestsRequest,
    ListTestsResponse,
    NodeInfo,
    RegisterTestRequest,
    RegisterTestResponse,
    StopTestResponse,
)
from protocols.cluster_operator.cluster_operator_pb2_grpc import ClusterOperatorServicer

# Protocol includes
from protocols.cluster_test.cluster_test_pb2 import (
    ExecuteRequest,
    ExecuteResponse,
    StopRequest,
    StopResponse,
    TestStepResult,
)
from src.services.operator import ClusterOperator


class ClusterOperatorServicerProvider(ClusterOperatorServicer):
    def __init__(self, operator: ClusterOperator):
        self.operator: ClusterOperator = operator

    def HealthCheck(self, request: HealthCheckRequest, context):
        status, error = self.operator.get_status()
        return HealthCheckResponse(status=status, error=error)

    def GetClusterInfo(self, request: GetClusterInfoRequest, context):
        # Call app to get info
        response: GetClusterInfoResponse = GetClusterInfoResponse(nodes_info=self.operator.get_nodes_info())

        return response

    def GetDeploymentInfo(self, request: GetDeploymentInfoRequest, context):
        # Call app to get info
        response: GetDeploymentInfoResponse = GetDeploymentInfoResponse(
            deployment_info=self.operator.get_deployment_info()
        )

        return response

    def RegisterTest(self, request: RegisterTestRequest, context):
        response: RegisterTestResponse = RegisterTestResponse(success=True)

        # Call the object method
        error = self.operator.register_test(request.port, request.info)
        if error:
            logging.error(error)
            response.success = False
            response.error = error

        return response

    def ListTests(self, request: ListTestsRequest, context):
        response: ListTestsResponse = ListTestsResponse(tests=self.operator.list_tests())

        return response

    def ExecuteTest(self, request, context):
        # Create and send a request to the test service
        request_to_test_service = ExecuteRequest(config=request.config, nodes=request.nodes)

        test = self.operator.get_test_entry(request.uuid)

        self.operator.status = ClusterStatus.RUNNING

        logging.info(f"Operator started running test {request.uuid}")

        # Communicate with the test service
        try:
            for response in test.stub.Execute(request_to_test_service):
                test_response = ExecuteTestResponse(
                    stopped=response.stopped, sequence=response.sequence, results=response.results
                )
                yield test_response
        except grpc.RpcError as e:
            self.operator.status = ClusterStatus.IDLE
            context.abort(grpc.StatusCode.ABORTED, f"{e.details()}")

        logging.info(f"Operator stopped running test {request.uuid}")
        self.operator.status = ClusterStatus.IDLE

    def StopTest(self, request, context):
        # Check if we're running first
        if self.operator.status != ClusterStatus.RUNNING:
            context.abort(grpc.StatusCode.ABORTED, f"No tests are currently running")

        logging.info(f"Received test stop request for test {request.uuid}")

        test = self.operator.get_test_entry(request.uuid)

        # Communicate with the test service
        try:
            test.stub.Stop(StopRequest())
            return StopTestResponse()
        except grpc.RpcError as e:
            context.abort(grpc.StatusCode.ABORTED, f"An error ocurred trying to stop test: {e.details()}")
