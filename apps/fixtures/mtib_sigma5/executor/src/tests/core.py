# Standard includes
import uuid
import threading
import logging
from enum import Enum
import inspect
import time
import queue
from typing import Tuple, List, Callable, Optional, Any
from concurrent.futures import as_completed

# Protocol includes
from protos.cluster_test.cluster_test_pb2 import (
    TestInfo, StepInfo, TestStepResult
)

# -------------------------------------------------------------------------------------------------
#                                                                                       Step Object
# -----------------------------------------------------------------------------------------------*/
"""
A test step handler will be passed 2 arguements:
    (str): The test configuration string
    (str): The node hostname requested
"""
TestHandlerType = Callable[[str, str], TestStepResult]

class TestStep:
    def __init__(self,
                info:StepInfo,
                handler:TestHandlerType):
        
        self.info:StepInfo = info
        self.handler:TestHandlerType = handler

    def exec(self, runners: List[str]) -> Tuple[bool, str, Optional[List[TestStepResult]]]:
        results: List[TestStepResult] = []

        with threading.ThreadPoolExecutor(max_workers=len(runners)) as executor:
            future_to_runner = {executor.submit(self.handler, runner): runner for runner in runners}
            
            for future in as_completed(future_to_runner):
                try:
                    result:TestStepResult = future.result()
                    results.append(result)
                except Exception as e:
                    return False, f"Error executing handler for step: {e}", None
                
        return True, "", results
    
# -------------------------------------------------------------------------------------------------
#                                                                                       Test Object
# -----------------------------------------------------------------------------------------------*/

"""
Test initialization function. Called before every test run:.

Args:
    (Optional[Any]): The unmarshalled test configuration, if applicable.
    (List[str]): The list of nodes this test will be executed on.

Returns:
    (str): An error, if any ocurred during initialization
"""
TestInitFuncType = Callable[[Optional[Any], List[str]], str]

"""
Test deinitialization function. Called after every test run:.

Args:
    (Optional[Any]): The unmarshalled test configuration, if applicable.
    (List[str]): The list of nodes this test was be executed on.

Returns:
    (str): An error, if any ocurred during deinitialization
"""
TestDeinitFuncType = Callable[[Optional[Any], List[str]], str]

"""
Text execution callback. Called after a test step completes.

Args:
    (bool): done, indicates the last call to this function.
    (int): The sequence of the test, used for percentage calculation.
    (List[TestStepResult]): A list of results for the step

Returns:
    None.
"""
ExecCallbackFuncType = Callable[[bool, int, List[TestStepResult]], None]

class TestStatus(Enum):
    IDLE = 0
    INITIALIZED = 1
    RUNNING = 2
    ERRORED = 3
    
class Test:
    def __init__(self,
                 info:TestInfo = None,
                 config_type:Any = None, 
                 init_func:TestInitFuncType = None,
                 deinit_func:TestInitFuncType = None,
                 steps:List[TestStep] = []):
        
        # Metadata about this test
        if info is None:
            raise ValueError("info field is missing in test definition")

        self.info:TestInfo = info
        
        # Test configuration (if applicable)
        self.config_type:Any = config_type
        
        # Assign our steps for the test
        if len(steps) == 0:
            raise ValueError("Test has 0 steps")
        
        self.steps:List[TestStep] = steps

        # Populate the info object with the steps info
        for step in self.steps:
            self.info.steps.append(step.info)
            
        # Validate the config_type if provided
        if self.config_type is not None:
            self._validate_config_type()
    
        # Assign user defined functions if provided
        self.init_func = init_func
        self.deinit_func = deinit_func
        
        # Validate function signatures if functions are provided
        if self.init_func is not None:
            self._validate_function_signature(self.init_func, "init_func")
        if self.deinit_func is not None:
            self._validate_function_signature(self.deinit_func, "deinit_func")
        
        self.nodes:List[str] = []
        
        # Variable to manage state
        self.status:TestStatus = TestStatus.IDLE
        self.lock = threading.Lock()
        self.stop_requested = False
        
    def init(self, config:str, nodes:List[str]) -> str:
        with self.lock:
            if self.status is not TestStatus.IDLE: 
                return f"Test is already running. Cannot reinitialize. Status: {self.status}"

            # Attempt to unmarshall the configuration if applicable
            if self.config_type is not None:
                if config is None:
                    return "Test requires a configuration object, but none were passed"
                try:
                    self.config_obj = self.config_type.unmarshall(config)
                except Exception as e:
                    return f"Failed to parse config: {str(e)}"
        
            if len(nodes) == 0:
                return "List of nodes passed has 0 items, test needs at least 1 node to execute on"
            
            if self.init_func:
                try:
                    error = self.init_func(self.config_obj, nodes)
                    if error:
                        return f"An error occurred during test initialization: {error}"
                except Exception as e:
                    return f"An exception occurred during test initialization: {str(e)}"
            
            self.status = TestStatus.INITIALIZED
            self.nodes = nodes
            return ""
    
    def exec(self) -> Tuple[str, Optional[queue.Queue]]:
        with self.lock:
            
            self.results_queue = queue.Queue()
            
            # TODO: Check that the results callback is correct
            if self.status is not TestStatus.INITIALIZED: 
                    return f"Test is not initialized yet. Cannot execute. Status: {self.status}"
            
            # No errors, proceed to execution in a thread
            thread = threading.Thread(target=self._execute_steps)
            thread.start()
            return ("", self.results_queue)
    
    def _execute_steps(self):
        # Simulate the execution of several test steps
        test_steps = [
            {"error": "", "success": True, "detailedResult": "Initialization complete."},
            {"error": "", "success": True, "detailedResult": "Loading modules."},
            {"error": "Error loading module", "success": False, "detailedResult": "Module failed to load."},
            {"error": "", "success": True, "detailedResult": "Cleanup and finalizing."},
            {"error": "", "success": True, "detailedResult": "Test completed successfully."}
        ]

        for step in test_steps:
            if self.stop_requested == True:
                self.results_queue.put(None)
                return
                
            test_step_result = TestStepResult(
                error=step["error"],
                success=step["success"],
                detailedResult=step["detailedResult"],
            )
            
            test_step_results = [
                test_step_result,test_step_result,test_step_result,test_step_result,test_step_result,test_step_result
            ]
            
            self.results_queue.put(test_step_results)
            time.sleep(1)  # Simulate delay between steps

        self.results_queue.put(None)  # Signal completion

            # active_runners:List[str] = nodes

            # # For each step in the test
            # for index, step in enumerate(self.steps):
                
            #     success:bool = False
            #     error:str = ""
            #     results:List[TestStepResult] = []   

            #     # Execute in all active runners in parallel
            #     success, error, results = step.exec(active_runners)

            #     # If there was an error executing, then we let the user know, and return
            #     if not success:
            #         if error:
            #             callback(True, f"error executing step: {error}", step.info.sequence, None) # Complete, Error, No result
            #         elif not results:
            #             callback(True, f"No results were returned by step.exec()", step.info.sequence, None) 
            #         else:
            #             callback(True, f"Unknown error occurred executing step", step.info.sequence, None) 
            #         return
            #     else:
            #         logging.info("exec for test executed correctly")

            #         # Populate the common fields
            #         # Check if it's the last step by comparing the current index with the length of the steps list
            #         is_last_step = (index == len(self.steps) - 1)
            #         callback(is_last_step, "", step.info.sequence, results)
    
    def stop(self) -> str:
        self.stop_requested = True
        return ""
         
    def deinit(self) -> str:
        # Call the deinitialization function
        if self.deinit_func is not None:
            try:
                error = self.deinit_func(self.config_obj, self.nodes)
                if error:
                   return f"An error occurred during test deinitialization: {error}" 
            except Exception as e:
                return f"An exception occurred during test deinitialization: {str(e)}"
        
        self.config_obj = None
        self.nodes = []
        
        # Finally set the state
        self.status = TestStatus.IDLE
    
    def _validate_config_type(self):
        # Check for the existence of marshall and unmarshall methods
        required_methods = ['unmarshall']
        for method in required_methods:
            if not hasattr(self.config_type, method) or not callable(getattr(self.config_type, method)):
                raise ValueError(f"The config_type must have a {method} method.")
                
    def _validate_function_signature(self, func, func_name):
        # Create a flexible expected signature based on config_type
        expected_param = self.config_type if self.config_type is not None else Optional[Any]
        expected_signature = inspect.Signature(
            parameters=[
                inspect.Parameter('config', inspect.Parameter.POSITIONAL_OR_KEYWORD, annotation=expected_param),
                inspect.Parameter('nodes', inspect.Parameter.POSITIONAL_OR_KEYWORD, annotation=List[str])
            ],
            return_annotation=str
        )
        
        if not callable(func):
            raise TypeError(f"{func_name} must be callable")

        actual_signature = inspect.signature(func)
        if actual_signature != expected_signature:
            raise TypeError(f"{func_name} has an incorrect signature. Expected {expected_signature}, got {actual_signature}")

        return func