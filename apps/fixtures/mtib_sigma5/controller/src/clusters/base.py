from abc import ABC, abstractmethod
from typing import Tuple, Any, Tuple, Callable, List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging

# Protocol includes
from protos.mtib_runner.mtib_runner_pb2 import (
    RunnerInfo
)
from protos.mtib_runner.mtib_runner_pb2_grpc import MtibRunnerStub
from protos.mtib_controller.mtib_controller_pb2 import (
    TestInfo, StepInfo, TestStepResult
)

# -------------------------------------------------------------------------------------------------
#                                                                                     Runner Object
# -----------------------------------------------------------------------------------------------*/
class ClusterRunner:
    def __init__(self, info:RunnerInfo, stub:MtibRunnerStub):
        self.info:RunnerInfo = info
        self.stub:MtibRunnerStub = stub

# -------------------------------------------------------------------------------------------------
#                                                                                       Step Object
# -----------------------------------------------------------------------------------------------*/
TestHandlerType = Callable[[ClusterRunner], TestStepResult]
class ClusterTestStep:
    def __init__(self,
                info:StepInfo,
                handler:TestHandlerType):
        
        self.info:StepInfo = info
        self.handler:TestHandlerType = handler

    def exec(self, runners: List[ClusterRunner]) -> Tuple[bool, str, Optional[List[TestStepResult]]]:
        results: List[TestStepResult] = []

        with ThreadPoolExecutor(max_workers=len(runners)) as executor:
            future_to_runner = {executor.submit(self.handler, runner): runner for runner in runners}
            
            for future in as_completed(future_to_runner):
                try:
                    result: TestStepResult = future.result()
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

class ClusterTest:
    def __init__(self,
                 info:TestInfo,
                 steps:List[ClusterTestStep]):
        
        self.info:TestInfo = info
        self.steps:List[ClusterTestStep] = steps

        # Populate the info object with the steps info
        for step in self.steps:
            self.info.steps.append(step.info)

    def exec(self, runners:List[ClusterRunner], callback:TestCallbackType):
        active_runners:List[ClusterRunner] = runners

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
# -------------------------------------------------------------------------------------------------
#                                                                               Base cluster object
# -----------------------------------------------------------------------------------------------*/
class BaseTestCluster(ABC):
    @abstractmethod
    def setup(self) -> Tuple[bool, str]:
        """
        Setup or initialize the test cluster.
        Returns a boolean indicating success.
        """
        pass

    @abstractmethod
    def get_cluster_info(self) -> Any:
        """
        Fetches metadata about the test cluster.
        Returns a dictionary containing metadata such as runners, supported hardware, etc.
        """
        pass

    @abstractmethod
    def get_tests(self) -> Any:
        """
        Fetches metadata about the test cluster.
        Returns a dictionary containing metadata such as runners, supported hardware, etc.
        """
        pass

    def execute_test(self, test_id:str, runner_ids:List[int], callback:Any) -> Any:
        pass