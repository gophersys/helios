# Standard includes
import inspect
import logging
import json
import traceback
from dataclasses import asdict, dataclass
from concurrent.futures import ThreadPoolExecutor, TimeoutError, wait
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional, Union, get_type_hints, Type
from abc import ABC, abstractmethod
from dataclasses import is_dataclass

# # Protocol includes
# from protos.cluster_test.cluster_test_pb2 import (
#     StepInfo,
#     TestStepResult,
# )

# Runner client
from corekinect.mtib_runner.v1.client import MtibRunnerV1Client

# Private library includes
from ..config import (
    TestConfig,
    CompatibleValidationTestConfig,
    ValidationTestConfig,
    CompatibleManufacturingTestConfig,
    ManufacturingTestConfig,
)

from .types import TestStepInfo, TestStepConfig, TestStepData


# ---------------------------------------------------------------------------------
#                                                      Default Configuration Fields
# -------------------------------------------------------------------------------*/
DEFAULT_TEST_STEP_TIMEOUT_MS = 10000  # 10s


# ---------------------------------------------------------------------------------
#                                                                   Test Step Class
# -------------------------------------------------------------------------------*/


# ---------------------------------------------------------------------------------
#                                                                   Test Step Class
# -------------------------------------------------------------------------------*/
class TestStep(ABC):
    # -----------------------------------------------------------------------------
    #                                                                          Init
    # ---------------------------------------------------------------------------*/
    def __init__(self):
        config: self.Config = self.Config

        # Verify that the child class has the needed subclasses
        err = self._verify_child_class_structs()
        if err is not None:
            raise ValueError(f"Test step subclass definition is incorrect: {err}")

        # Ensure that the child class implements handler with correct type hints
        self._verify_handler_signature()

    def _verify_child_class_structs(self) -> Optional[str]:
        """
        Verifies that the child class has defined the needed configurationa and
        data structures needed by the framework
        """
        # Check the config class exists
        if not hasattr(self, "Config"):
            raise NotImplementedError("Child classes must define a 'Config' class")

        # Check that it's a subclass of TestConfig
        if not issubclass(self.Config, TestStepConfig):
            return f"'Config' class must be a subclass of TestConfig, got {type(self.Config)}."

        # Check if the Config class is a dataclass
        if not is_dataclass(self.Config):
            return "'Config' class must be decorated with @dataclass."

        # Check that compatible_config is defined
        if not hasattr(self, "compatible_config"):
            return "Child classes must define a 'compatible_config' attribute."

        # Check that compatible_config is an instance of the allowed types
        if not isinstance(
            self.compatible_config,
            (
                CompatibleValidationTestConfig,
                CompatibleManufacturingTestConfig,
            ),
        ):
            return (
                f"'compatible_config' must be an instance of either CompatibleValidationTestConfig "
                f"or CompatibleManufacturingTestConfig, got {type(self.compatible_config).__name__}."
            )

        # Check that info is defined
        if not hasattr(self, "info"):
            return "Child classes must define a 'info' attribute."

        # Check compatible_config against allowed types
        if not isinstance(self.info, TestStepInfo):
            return f"'info' must be TestStepInfo, got {self.info}."

        return None

    def _verify_handler_signature(self):
        # Get the child class's handler method
        handler_method = getattr(self, "handler", None)
        if handler_method is None:
            raise NotImplementedError("Child classes must implement 'handler' method")

        # Get the signature of the handler method
        handler_signature = inspect.signature(handler_method)
        handler_type_hints = get_type_hints(handler_method)

        # Check test_config type to ensure it is either ValidationTestConfig or ManufacturingTestConfig
        test_config_type = handler_type_hints.get("test_config")
        allowed_types = (ValidationTestConfig, ManufacturingTestConfig)

        if test_config_type not in allowed_types:
            raise TypeError(
                f"test_config must be either ValidationTestConfig or ManufacturingTestConfig, "
                f"but got '{test_config_type.__name__}'."
            )

    # -----------------------------------------------------------------------------
    #                                                                           Run
    # ---------------------------------------------------------------------------*/
    def run():
        pass

    # -----------------------------------------------------------------------------
    #                                                             Developer Handler
    # ---------------------------------------------------------------------------*/
    @abstractmethod
    def handler(
        self,
        runner_client: MtibRunnerV1Client,
        test_config: Union[ValidationTestConfig, ManufacturingTestConfig],
        step_config: "self.Config",
    ):
        pass


# ---------------------------------------------------------------------------------
#                                                                   Test Step Class
# -------------------------------------------------------------------------------*/
# class TestStep(ABC):
#     # The user must define the metadata
#     info: TestStepInfo = None
#     config: TestStepConfig = None

#     # g_config: ValidationTestInfo()

#     def __init_subclass__(cls, **kwargs):
#         """Ensures that subclasses define the `metadata`."""
#         super().__init_subclass__(**kwargs)

#         # Check if metadata is set and is an instance of StepInfo
#         if cls.info is None or not isinstance(cls.info, TestStepInfo):
#             raise TypeError(f"Class {cls.__name__} must define `info` as an instance of `TestStepInfo`")

#         # Check if `Config` is defined and is a subclass of TestStepConfig
#         if not hasattr(cls, "Config") or not issubclass(cls.Config, TestStepConfig):
#             raise TypeError(f"Class {cls.__name__} must define a class `Config` that inherits from `TestStepConfig`")

#     def __init__(self):
#         pass

#     # def handler(self, g_config:Any, config:Any, progress_callback:Any, dependencies:TestDependency)

#     def validate_handler_signature(self, config_type, usr_data_type):
#         expected_signature = inspect.Signature(
#             parameters=[
#                 inspect.Parameter("config", inspect.Parameter.POSITIONAL_OR_KEYWORD, annotation=config_type),
#                 inspect.Parameter("node", inspect.Parameter.POSITIONAL_OR_KEYWORD, annotation=str),
#                 inspect.Parameter("usr_data", inspect.Parameter.POSITIONAL_OR_KEYWORD, annotation=usr_data_type),
#             ],
#             return_annotation=TestStepResult,
#         )

#         if not callable(self.handler):
#             raise TypeError("Handler must be callable")

#         actual_signature = inspect.signature(self.handler)
#         if actual_signature != expected_signature:
#             raise TypeError(
#                 f"Step handler function '{self.handler.__name__}' has an incorrect signature. "
#                 f"Expected {expected_signature}, got {actual_signature}"
#             )

#     def exec(self, config: Any, nodes: List[str], usr_data: Optional[Any]) -> List[TestStepResult]:
#         results: List[TestStepResult] = []
#         timeout_sec = self.timeout_ms / 1000  # Convert timeout to seconds
#         start_time = datetime.now().isoformat()  # Record the start time of the step

#         with ThreadPoolExecutor(max_workers=len(nodes)) as executor:
#             # Create a mapping of futures to their respective nodes
#             future_to_node: Dict[object, str] = {
#                 executor.submit(self._safe_handler_call, config, node, usr_data): node for node in nodes
#             }

#             # Get the time when the function should stop
#             end_time = datetime.now() + timedelta(seconds=timeout_sec)

#             while future_to_node:
#                 # Calculate the remaining time for the timeout
#                 remaining_time = (end_time - datetime.now()).total_seconds()
#                 if remaining_time <= 0:
#                     break

#                 # Wait for the futures with the remaining time
#                 done, not_done = wait(future_to_node.keys(), timeout=remaining_time)

#                 for future in done:
#                     node = future_to_node[future]
#                     try:
#                         result = future.result()  # We already waited, so just get the result
#                         logging.debug(
#                             f"{self.info.name} (step {self.info.sequence}) handler finished executing on node {node}"
#                         )
#                         results.append(result)
#                     except TimeoutError:
#                         logging.error(f"Timeout occurred for node: {node}")
#                         results.append(
#                             TestStepResult(
#                                 error=f"Execution timed out. Expected step {self.info.sequence} to last {self.timeout_ms}ms",
#                                 success=False,
#                                 node=node,
#                                 timeout=True,
#                                 sequence=self.info.sequence,
#                                 startTime=start_time,
#                                 endTime=datetime.now().isoformat(),
#                                 noPassIsFatal=self.info.noPassIsFatal,
#                             )
#                         )
#                     except FailTest:
#                         logging.error(f"Timeout occurred for node: {node}")
#                         results.append(
#                             TestStepResult(
#                                 error=f"Execution timed out. Expected step {self.info.sequence} to last {self.timeout_ms}ms",
#                                 success=False,
#                                 node=node,
#                                 timeout=True,
#                                 sequence=self.info.sequence,
#                                 startTime=start_time,
#                                 endTime=datetime.now().isoformat(),
#                                 noPassIsFatal=self.info.noPassIsFatal,
#                             )
#                         )
#                     except Exception as e:
#                         logging.error(f"Exception occurred for node: {node}, Error: {str(e)}")
#                         results.append(
#                             TestStepResult(
#                                 error=f"An exception occurred running handler: {str(e)}",
#                                 success=False,
#                                 node=node,
#                                 timeout=False,
#                                 sequence=self.info.sequence,
#                                 startTime=start_time,
#                                 endTime=datetime.now().isoformat(),
#                                 noPassIsFatal=self.info.noPassIsFatal,
#                             )
#                         )

#                     # Remove the completed future from the mapping
#                     del future_to_node[future]

#             # Handle remaining futures that did not complete in time
#             for future, node in future_to_node.items():
#                 results.append(
#                     TestStepResult(
#                         error=f"Execution timed out. Expected step to last {self.timeout_ms}ms",
#                         success=False,
#                         node=node,
#                         timeout=True,
#                         sequence=self.info.sequence,
#                         startTime=start_time,
#                         endTime=datetime.now().isoformat(),
#                         noPassIsFatal=self.info.noPassIsFatal,
#                     )
#                 )

#         return results

#     def _safe_handler_call(self, config: str, node: str, usr_data: Optional[Any]) -> TestStepResult:
#         """
#         Safely call the handler and ensure the result is of type TestStepResult.

#         Args:
#             config (str): Configuration string for the handler.
#             node (str): Node hostname for which the handler is called.

#         Returns:
#             TestStepResult: Result of the handler execution.
#         """
#         start_time = datetime.now().isoformat()  # Record the start time of the handler call
#         try:
#             result = self.handler(config, node, usr_data)  # Call the handler
#             if not isinstance(result, TestStepResult):
#                 # If the handler does not return a TestStepResult, raise a ValueError
#                 raise ValueError("Handler returned invalid type")

#             # Populate the application specific fields
#             result.node = node
#             result.timeout = False
#             result.sequence = self.info.sequence
#             result.startTime = start_time
#             result.endTime = datetime.now().isoformat()
#             result.noPassIsFatal = self.info.noPassIsFatal

#             return result
#         except Exception as e:
#             # Handle exceptions during the handler call and return an error result
#             return TestStepResult(
#                 error=f"An exception occurred in the user's step {self.info.sequence} handler for node {node}: Exception: {str(e)}\n{traceback.format_exc()}",
#                 success=False,
#                 node=node,
#                 timeout=False,
#                 sequence=self.info.sequence,
#                 startTime=start_time,
#                 endTime=datetime.now().isoformat(),
#                 noPassIsFatal=self.info.noPassIsFatal,
#             )
