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

from corekinect.test.step import TestStep

from corekinect.utils.log import Logger
from corekinect.mtib_runner.v1.client import MtibRunnerV1Client
from corekinect.test.config import ValidationTestConfig, TestConfig

# # 3rd party includes
# import grpc
# from protos.cluster_operator.cluster_operator_pb2 import (
#     ClusterStatus,
#     HealthCheckRequest,
#     HealthCheckResponse,
#     RegisterTestRequest,
#     RegisterTestResponse,
# )
# from protos.cluster_operator.cluster_operator_pb2_grpc import ClusterOperatorStub

# # Protocol includes
# from protos.cluster_test.cluster_test_pb2 import (
#     ExecuteRequest,
#     ExecuteResponse,
#     StepInfo,
#     StopRequest,
#     StopResponse,
#     TestInfo,
#     TestStepResult,
# )
# from protos.cluster_test.cluster_test_pb2_grpc import (
#     ClusterTestServicer,
#     add_ClusterTestServicer_to_server,
# )

# from ..step import TestStep
# from .net import ClusterTestServicerProvider

# ---------------------------------------------------------------------------------
#                                                              Test Class Callbacks
# -------------------------------------------------------------------------------*/

"""
Test initialization function. Called before every test run:.

Args:
    (Optional[Any]): The unmarshalled test configuration, if applicable.
    (List[str]): The list of nodes this test will be executed on.
    (Optional[Any]): The user data

Returns:
    (str): An error, if any ocurred during initialization
"""
TestInitFuncType = Callable[[Optional[Any], List[str], Optional[Any]], str]

"""
Test deinitialization function. Called after every test run:.

Args:
    (Optional[Any]): The unmarshalled test configuration, if applicable.
    (List[str]): The list of nodes this test was be executed on.
    (Optional[Any]): The user data

Returns:
    (str): An error, if any ocurred during deinitialization
"""
TestDeinitFuncType = Callable[[Optional[Any], List[str], Optional[Any]], str]

"""
Text execution callback. Called after a test step completes.

Args:
    (bool): done, indicates the last call to this function.
    (int): The sequence of the test, used for percentage calculation.
    (List[TestStepResult]): A list of results for the step

Returns:
    None.
"""
# ExecCallbackFuncType = Callable[[bool, int, List[TestStepResult]], None]


# ---------------------------------------------------------------------------------
#                                                                  Test Class State
# -------------------------------------------------------------------------------*/
class TestStatus(Enum):
    """
    Enumeration representing the status of a test.

    Attributes:
        IDLE (int): The test is idle and has not been initialized.
        INITIALIZED (int): The test has been initialized and is ready to run.
        RUNNING (int): The test is currently running.
        ERRORED (int): The test encountered an error during execution.
    """

    IDLE = 0
    INITIALIZED = 1
    RUNNING = 2
    ERRORED = 3


# ---------------------------------------------------------------------------------
#                                                              Validation Test Case
# -------------------------------------------------------------------------------*/


class ValidationTest:
    def __init__(
        self,
        config: ValidationTestConfig,
        mtib_runner_client_config: MtibRunnerV1Client.Config,
        steps_info: Dict[TestStep, TestConfig],
    ):
        self.config: ValidationTestConfig = config
        self.mtib_runner_client_config: MtibRunnerV1Client.Config = mtib_runner_client_config
        self.steps_info: Dict[TestStep, TestConfig] = steps_info

        # Objects used by the test
        self.logger: Logger = None
        self.runner_client: MtibRunnerV1Client = None

    def run(self) -> Optional[str]:
        # Instantiate a logger
        self.logger = Logger(
            config=Logger.Config(
                logger_name="test_case",
                test_case_logger=True,
            )
        )

        self.logger.info(self.config)

        # Initialize the shared runner instance
        self.runner_client = MtibRunnerV1Client(
            config=self.mtib_runner_client_config,
            logger=self.logger,
        )

        err = self.runner_client.connect()
        if err is not None:
            return f"Could not connect to runner at {self.mtib_runner_client_config.net.addr}:{self.mtib_runner_client_config.net.port}"

        step: TestStep
        step_config: TestConfig
        for step, step_config in self.steps_info:
            step.handler(
                runner_client=self.runner_client,
                test_config=self.config,
                step_config=step_config,
            )


# ---------------------------------------------------------------------------------
#                                                                        Test Class
# -------------------------------------------------------------------------------*/
# class TestCase:
#     # -----------------------------------------------------------------------------
#     #                                                                   Instantiate
#     #  --------------------------------------------------------------------------*/
#     def __init__(
#         self,
#         info: TestInfo = None,
#         config_type: Any = None,
#         init_func: TestInitFuncType = None,
#         deinit_func: TestInitFuncType = None,
#         usr_data: Optional[Any] = None,
#         usr_data_type: Optional[Any] = None,
#         steps: List[TestStep] = [],
#     ):
#         """
#         Initializes a Test instance with the provided parameters.

#         Args:
#             info (TestInfo): Metadata about this test.
#             config_type (Any): The type used for test configuration.
#             init_func (TestInitFuncType): The function to initialize the test.
#             deinit_func (TestInitFuncType): The function to deinitialize the test.
#             steps (List[TestStep]): The steps to execute in the test.

#         Raises:
#             ValueError or TypeError.
#         """
#         # Metadata about this test
#         if info is None:
#             raise ValueError("info field is missing in test definition")

#         self.info: TestInfo = info

#         # Test configuration (if applicable)
#         self.config_type: Any = config_type

#         # Assign our steps for the test
#         if len(steps) == 0:
#             raise ValueError("Test has 0 steps")

#         self.steps: List[TestStep] = steps

#         # Assign sequence numbers to the steps
#         for index, step in enumerate(self.steps):
#             step.info.sequence = index + 1  # Start sequence at 1

#         # Get the user data type if applicable
#         self.usr_data: Optional[Any] = usr_data
#         self.usr_data_type: Optional[Any] = usr_data_type

#         # Validate the handler types
#         for step in self.steps:
#             self.info.steps.append(step.info)
#             if self.config_type is not None:
#                 step.validate_handler_signature(self.config_type, self.usr_data_type)

#         # Validate the config_type if provided
#         if self.config_type is not None:
#             self._validate_config_type()

#         # Assign user-defined functions if provided
#         self.init_func = init_func
#         self.deinit_func = deinit_func

#         # Validate function signatures if functions are provided
#         if self.init_func is not None:
#             self._validate_function_signature(self.init_func, "init_func")
#         if self.deinit_func is not None:
#             self._validate_function_signature(self.deinit_func, "deinit_func")

#         self.nodes: List[str] = []

#         # Variable to manage state
#         self.status: TestStatus = TestStatus.IDLE
#         self.lock = threading.Lock()
#         self.stop_requested = False

#         # Validate test info
#         self._validate_test_info()

#     # -----------------------------------------------------------------------------
#     #                                                                          Test
#     #  --------------------------------------------------------------------------*/
#     def run(self, nodes: List[str]) -> str:
#         # Initialize the test
#         error = self.init(None, nodes)
#         if error:
#             return f"Failed to initialize test: {error}"

#         # Execute the main "case" logic as a series of steps that can run
#         # concurrently or serially to each other.
#         #
#         # At the end if everyone is "happy" and the test logic executed without
#         # any errors. we get a group of results, which are metadata about the test
#         # execution logic, including any assets and PASS or FAIl criteria for the
#         # execution.
#         error, results_queue = self.exec()
#         if error:
#             return f"Failed to execute test: {error}"

#         # Get results until test is done
#         while True:
#             response = results_queue.get()

#             if response is None:  # Completion signal received
#                 break

#         # Clean up
#         error = self.deinit()
#         if error:
#             return f"Failed to deinitialize test: {error}"

#         # If all went okay, return no error
#         return ""

#     # -----------------------------------------------------------------------------
#     #                                                                         Setup
#     #  --------------------------------------------------------------------------*/
#     def setup(self, uuid: int, port: int, operator_url: str) -> str:
#         # Verify inputs
#         if uuid == "":
#             return f"Test UUID cannot be empty"
#         if port < 1000:
#             return f"Port {port} is not a valid port number"
#         if operator_url == "":
#             return f"Operator URL cannot be empty"

#         # Set test uuid
#         self.info.uuid = uuid

#         error = self._start_test_server(port)
#         if error:
#             return f"Could not start test server, {error}"

#         error = self._register_with_operator(port, operator_url)
#         if error:
#             return f"Could not register test with operator {error}"

#         logging.info("Test server is running and registered with the operator.")
#         return ""

#     def _start_test_server(self, port: int) -> str:
#         try:
#             self.server = grpc.server(ThreadPoolExecutor(max_workers=10))
#         except Exception as e:
#             return f"Failed to create gRPC server: {e}"

#         try:
#             provider = ClusterTestServicerProvider(test=self)
#             add_ClusterTestServicer_to_server(provider, self.server)
#         except Exception as e:
#             return f"Failed to register the ClusterTest service: {e}"

#         try:
#             self.server.add_insecure_port(f"[::]:{port}")
#             self.server.start()
#         except Exception as e:
#             return f"Failed to start the gRPC server on port {port}: {e}"

#         logging.info(f"Test {self.info.name} server started, listening on port {port}.")
#         return ""

#     def _register_with_operator(self, port: int, operator_url: str) -> str:
#         try:
#             channel = grpc.insecure_channel(operator_url)
#             stub = ClusterOperatorStub(channel)

#             logging.info("Awaiting for operator readiness...")
#             ready = False
#             while not ready:
#                 try:
#                     response: HealthCheckResponse = stub.HealthCheck(HealthCheckRequest())
#                     if response.status != ClusterStatus.STARTING:
#                         ready = True
#                 except grpc.RpcError as e:
#                     logging.warning(f"Unable to get operator info at {operator_url}: {e}")
#                 time.sleep(1)

#             logging.info(f'Registering test "{self.info.name}" with operator at {operator_url}...')
#             request = RegisterTestRequest(port=port, info=self.info)
#             response = stub.RegisterTest(request)
#             if not response.success:
#                 return f"Operator was not able to register test: {response.error}"

#             logging.info(f'Successfully registered test "{self.info.name}"!')
#             return ""

#         except grpc.RpcError as e:
#             return f"Failed to connect to operator at {operator_url} over gRPC. Error: {e}"

#     # -----------------------------------------------------------------------------
#     #                                                                          Stop
#     #  --------------------------------------------------------------------------*/
#     def teardown(self):
#         if self.server:
#             self.server.stop(0)
#             logging.info("Test server stopped.")

#     # -----------------------------------------------------------------------------
#     #                                                                          Init
#     #  --------------------------------------------------------------------------*/
#     def init(self, config: str, nodes: List[str]) -> str:
#         """
#         Initializes the test with the provided configuration and nodes.

#         Args:
#             config (str): The test configuration string.
#             nodes (List[str]): List of node hostnames to run the test on.

#         Returns:
#             str: An empty string if initialization is successful, or an error message if it fails.
#         """
#         with self.lock:
#             if self.status is not TestStatus.IDLE:
#                 return f"Test is already running. Cannot reinitialize. Status: {self.status}"

#             # Check that the nodes list passed makes sense
#             if len(nodes) == 0:
#                 return "List of nodes passed has 0 items, test needs at least 1 node to execute on"
#             self.nodes = nodes

#             logging.debug(f"Starting test case {self.info.name} in nodes {nodes}")

#             # Attempt to unmarshal the configuration if applicable
#             if self.config_type is not None:
#                 if not config or config.strip() == "{}":
#                     logging.debug("Using default configuration for test")
#                     self.config_obj = self.config_type()
#                 else:
#                     try:
#                         self.config_obj = self.config_type.unmarshall(config)
#                         logging.debug(f"Using user configuration for test: {config}")
#                     except Exception as e:
#                         return f"Failed to parse config: {str(e)}"

#             # Call the initialize function for the test
#             if self.init_func:
#                 try:
#                     logging.debug(f"Calling test initialization function...")
#                     error = self.init_func(self.config_obj, nodes, self.usr_data)
#                     if error:
#                         return f"An error occurred during test initialization: {error}"
#                 except Exception as e:
#                     return f"An exception occurred during test initialization: {str(e)}"

#             logging.debug(f"Test initialized successfully")
#             self.status = TestStatus.INITIALIZED
#             return ""

#     # -----------------------------------------------------------------------------
#     #                                                                          Exec
#     #  --------------------------------------------------------------------------*/
#     def exec(self) -> Tuple[str, Optional[queue.Queue]]:
#         """
#         Executes the test by starting a new thread to run the test steps.

#         Returns:
#             Tuple[str, Optional[queue.Queue]]: A tuple containing an error message (if any) and the results queue.
#         """
#         with self.lock:
#             # Ensure the test is in the INITIALIZED state before execution
#             if self.status is not TestStatus.INITIALIZED:
#                 return f"Test is not initialized yet. Cannot execute. Status: {self.status}", None

#             logging.debug(f"Executing test {self.info.name}...")

#             # Create a queue to communicate results back to the RPC handler
#             self.results_queue = queue.Queue()

#             # Spin up a new thread to run the test
#             thread = threading.Thread(target=self._execute_steps, daemon=True)
#             thread.start()

#             return "", self.results_queue

#     def _execute_steps(self):
#         """
#         Executes the test steps in sequence, processing results and handling stop requests.

#         This method runs in a separate thread.
#         """
#         active_nodes = self.nodes[:]
#         step_sequence = 0

#         # Measure the start time
#         start_time = time.time()

#         for step in self.steps:
#             step_sequence += 1
#             if not active_nodes:
#                 logging.error("Ending test, no active nodes left without errors")
#                 break

#             logging.debug(
#                 f"Executing test step: {step.info.name} ({step_sequence}/{len(self.steps)}) on nodes {active_nodes}"
#             )
#             step_results = step.exec(self.config_obj, active_nodes, self.usr_data)

#             # Determine if the step should retry on failure
#             for retry in range(step.num_retries_on_fail):
#                 failed_nodes = [result.node for result in step_results if not result.success]
#                 if not failed_nodes:
#                     break

#                 logging.warning(
#                     f"Retrying step {step_sequence} on failed nodes: {failed_nodes} (retry {retry + 1}/{step.num_retries_on_fail})"
#                 )
#                 step_results = step.exec(self.config_obj, failed_nodes, self.usr_data)

#             # Process the results and filter out nodes that failed
#             for result in step_results:
#                 if result.error:
#                     logging.error(
#                         f"Removing node {result.node} from active list, an error was detected in step {step_sequence}: {result.error}"
#                     )
#                     active_nodes.remove(result.node)
#                 elif result.success == False:
#                     logging.warning(
#                         f"A step failure (NO PASS) was detected in step {step_sequence} on node {result.node}. Reason: {result.reason}"
#                     )
#                     if step.info.noPassIsFatal:
#                         logging.error(
#                             f"No pass criteria marked as fatal, removing node {result.node} from active list for subsequent steps"
#                         )
#                         active_nodes.remove(result.node)

#             # Generate and enqueue the response
#             response = ExecuteResponse(sequence=step_sequence, stopped=self._is_stop_requested(), results=step_results)
#             self.results_queue.put(response)

#             # Check if stop was requested
#             if self._is_stop_requested():
#                 logging.warning(f"Test was stopped at step {step_sequence} of {len(self.steps)}")
#                 break

#         duration = time.time() - start_time
#         logging.warning(
#             f'Test "{self.info.name}" finished executing {step_sequence}/{len(self.steps)} steps in {duration:.2f} seconds'
#         )

#         # Signal completion to RPC handler
#         self.results_queue.put(None)

#     def _is_stop_requested(self) -> bool:
#         """
#         Checks if a stop request has been made.

#         Returns:
#             bool: True if a stop request has been made, False otherwise.
#         """
#         with self.lock:
#             return self.stop_requested

#     def stop(self):
#         """
#         Requests to stop the test execution.

#         Returns:
#             str: An empty string.
#         """
#         with self.lock:
#             self.stop_requested = True

#     # -----------------------------------------------------------------------------
#     #                                                                        Deinit
#     #  --------------------------------------------------------------------------*/
#     def deinit(self) -> str:
#         """
#         Deinitialize the test, reset the state to IDLE and ready for the test to be re-ran.

#         Returns:
#             str: Message indicating the result of the deinitialization.
#         """
#         with self.lock:

#             # Call the deinitialization function if provided
#             if self.deinit_func is not None:
#                 try:
#                     logging.debug(f"Calling test deinitialization function...")
#                     error = self.deinit_func(self.config_obj, self.nodes, self.usr_data)
#                     if error:
#                         return f"An error occurred during test deinitialization: {error}"
#                 except Exception as e:
#                     return f"An exception occurred during test deinitialization: {str(e)}"

#             # Reset the configuration object and nodes
#             self.config_obj = None
#             self.nodes = []

#             # Finally set the state to IDLE and reset stop_requested
#             self.status = TestStatus.IDLE
#             self.stop_requested = False

#             logging.debug(f"Test deinitialized succesfully")
#             return ""

#     # -----------------------------------------------------------------------------
#     #                                                                      Validate
#     #  --------------------------------------------------------------------------*/
#     def _validate_test_info(self):
#         """
#         Validates that the default configuration in the test info matches the marshalled default configuration
#         from the config type, if provided.

#         Raises:
#             ValueError: If the default configuration in the test info does not match the marshalled default configuration.
#         """
#         # Check if config_type is provided
#         if self.config_type is not None:
#             # Marshal the default configuration from config_type
#             default_config_obj = self.config_type()
#             default_config_str = default_config_obj.marshall()

#             # Check if info.defaultConfig matches the marshalled default configuration
#             if self.info.defaultConfig != default_config_str:
#                 raise ValueError("info.defaultConfig does not match the default configuration of config_type")

#         # Check that the user didn't accidentally set the test id at declaration time
#         if self.info.uuid != "":
#             raise ValueError(
#                 "info.uuid must be set at run time, from an environment variable, and not at test definition time"
#             )

#     def _validate_config_type(self):
#         """
#         Validates the configuration type class. Ensures that all parameters of its constructor have default values,
#         and that it has the required methods 'unmarshall' and 'marshall'.

#         Raises:
#             ValueError: If any parameter in the constructor does not have a default value.
#             ValueError: If the config_type does not have the required 'unmarshall' or 'marshall' methods.
#         """
#         # Validate that there's a default value for each configuration parameter
#         init_params = inspect.signature(self.config_type.__init__).parameters
#         for param in init_params.values():
#             if param.name == "self":
#                 continue
#             if param.default == inspect.Parameter.empty:
#                 raise ValueError(
#                     f"Parameter '{param.name}' in '{self.config_type.__name__}' does not have a default value"
#                 )

#         # Check for the existence of 'unmarshall' and 'marshall' methods
#         required_methods = ["unmarshall", "marshall"]
#         for method in required_methods:
#             if not hasattr(self.config_type, method) or not callable(getattr(self.config_type, method)):
#                 raise ValueError(f"The config_type must have a {method} method.")

#     def _validate_function_signature(self, func, func_name):
#         """
#         Validates the signature of a given function to ensure it matches the expected signature based on config_type.

#         Args:
#             func (callable): The function to validate.
#             func_name (str): The name of the function (used for error messages).

#         Raises:
#             TypeError: If the function is not callable.
#             TypeError: If the function's signature does not match the expected signature.
#         """
#         # Create a flexible expected signature based on config_type
#         expected_param = self.config_type if self.config_type is not None else Optional[Any]
#         expected_signature = inspect.Signature(
#             parameters=[
#                 inspect.Parameter("config", inspect.Parameter.POSITIONAL_OR_KEYWORD, annotation=expected_param),
#                 inspect.Parameter("nodes", inspect.Parameter.POSITIONAL_OR_KEYWORD, annotation=List[str]),
#                 inspect.Parameter("usr_data", inspect.Parameter.POSITIONAL_OR_KEYWORD, annotation=self.usr_data_type),
#             ],
#             return_annotation=str,
#         )

#         if not callable(func):
#             raise TypeError(f"{func_name} must be callable")

#         actual_signature = inspect.signature(func)
#         if actual_signature != expected_signature:
#             raise TypeError(
#                 f"{func_name} has an incorrect signature. Expected {expected_signature}, got {actual_signature}"
#             )

#         return func
