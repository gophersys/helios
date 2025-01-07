# Standard includes
import inspect
import json
import logging
import traceback
import queue
import threading
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError, as_completed, wait
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

# 3rd party includes
import grpc
from protos.cluster_operator.cluster_operator_pb2 import (
    ClusterStatus,
    HealthCheckRequest,
    HealthCheckResponse,
    RegisterTestRequest,
    RegisterTestResponse,
)
from protos.cluster_operator.cluster_operator_pb2_grpc import ClusterOperatorStub

# Protocol includes
from protos.cluster_test.cluster_test_pb2 import (
    ExecuteRequest,
    ExecuteResponse,
    StepInfo,
    StopRequest,
    StopResponse,
    TestInfo,
    TestStepResult,
)
from protos.cluster_test.cluster_test_pb2_grpc import (
    ClusterTestServicer,
    add_ClusterTestServicer_to_server,
)

# Private includes
from .core import TestCase


# ---------------------------------------------------------------------------------
#                                                                Test gRPC Provider
# -------------------------------------------------------------------------------*/
class ClusterTestServicerProvider(ClusterTestServicer):
    def __init__(
        self, test: Any
    ):  # We set the test type to Any, as it's defined in this same file, but below this class
        self.test: TestCase = test

    # -----------------------------------------------------------------------------
    #                                                                   HealthCheck
    #  --------------------------------------------------------------------------*/
    def HealthCheck(self, request: HealthCheckRequest, context):
        return HealthCheckResponse()

    # -----------------------------------------------------------------------------
    #                                                                       Execute
    #  --------------------------------------------------------------------------*/
    def Execute(self, request: ExecuteRequest, context):
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

        # Variables to track test state at this
        test_failed: bool = True
        results_count: int = 0
        while True:
            response = results_queue.get()

            if response is None:  # Completion signal received
                if results_count == len(self.test.steps):
                    test_failed = False
                break

            results_count = results_count + 1
            yield response

        # Check if we got a stop response before we clear up the flag in deinit
        test_stopped: bool = False
        if self.test.stop_requested:
            test_stopped = True

        # Clean up
        error = self.test.deinit()
        if error:
            error = f"Failed to deinitialize test: {error}"
            logging.error(error)
            context.abort(grpc.StatusCode.ABORTED, error)

        if test_failed and not test_stopped:
            error = f"Test did not complete all steps in any node, check results for more info"
            logging.error(error)
            context.abort(grpc.StatusCode.ABORTED, error)

        # If all went okay, we simply yield
        yield

    # -----------------------------------------------------------------------------
    #                                                                          Stop
    #  --------------------------------------------------------------------------*/
    def Stop(self, request: StopRequest, context):
        logging.warning("Test stop requested")
        self.test.stop()
        return StopResponse()
