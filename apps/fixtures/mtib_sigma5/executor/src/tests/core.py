# Standard includes
import uuid
import threading
import logging
from typing import Tuple, List, Callable, Optional
from concurrent.futures import as_completed

# Protocol includes
from protos.cluster_runner.cluster_runner_pb2 import (
    RunnerInfo
)
from protos.cluster_runner.cluster_runner_pb2_grpc import ClusterRunnerStub

from protos.cluster_test.cluster_test_pb2 import (
    TestInfo, StepInfo, TestStepResult
)

# -------------------------------------------------------------------------------------------------
#                                                                                     Runner Object
# -----------------------------------------------------------------------------------------------*/
class TestRunner:
    def __init__(self, info:RunnerInfo, stub:ClusterRunnerStub):
        self.info:RunnerInfo = info
        self.stub:ClusterRunnerStub = stub

test_step_1:StepInfo = StepInfo(
    sequence=1,
    name="Electrical Test",

)

# -------------------------------------------------------------------------------------------------
#                                                                                       Step Object
# -----------------------------------------------------------------------------------------------*/
TestHandlerType = Callable[[TestRunner], TestStepResult]
class TestStep:
    def __init__(self,
                info:StepInfo,
                handler:TestHandlerType):
        
        self.info:StepInfo = info
        self.handler:TestHandlerType = handler

    def exec(self, runners: List[TestRunner]) -> Tuple[bool, str, Optional[List[TestStepResult]]]:
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

# Bool is set to false if an error occurred and the string is set, otherwise True means test is done
# Complete
# error
# sequence
# results
TestCallbackType = Callable[[bool, str, int, Optional[List[TestStepResult]]], None]
class Test:
    def __init__(self,
                 info:TestInfo,
                 steps:List[TestStep]):
        
        self.info:TestInfo = info
        self.steps:List[TestStep] = steps

        # Populate the info object with the steps info
        for step in self.steps:
            self.info.steps.append(step.info)

    def exec(self, runners:List[TestRunner], callback:TestCallbackType):
        active_runners:List[TestRunner] = runners

        # For each step in the test
        for index, step in enumerate(self.steps):
            
            success:bool = False
            error:str = ""
            results:List[TestStepResult] = []

            # Execute in all active runners in parallel
            success, error, results = step.exec(active_runners)

            # If there was an error executing, then we let the user know, and return
            if not success:
                if error:
                    callback(True, f"error executing step: {error}", step.info.sequence, None) # Complete, Error, No result
                elif not results:
                    callback(True, f"No results were returned by step.exec()", step.info.sequence, None) 
                else:
                    callback(True, f"Unknown error occurred executing step", step.info.sequence, None) 
                return
            else:
                # Process the step results
                for result in results:
                    if not result.execOk:
                        # Find and remove the runners in which we didn't succeed
                        for runner in active_runners:
                            if runner.info.id == result.runnerId:
                                active_runners.remove(runner)

                logging.info("exec for test executed correctly")

                # Populate the common fields
                # Check if it's the last step by comparing the current index with the length of the steps list
                is_last_step = (index == len(self.steps) - 1)
                callback(is_last_step, "", step.info.sequence, results)