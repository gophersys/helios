# Standard includes
import time
import os
import yaml
import subprocess
import logging
import requests
from typing import Tuple, List, Callable, Optional
from urllib.parse import urlparse
from concurrent.futures import as_completed
import threading

# 3rd party includes
import docker
from kubernetes import client, config,  utils
import grpc

# Protocol includes
from protos.cluster_runner.cluster_runner_pb2 import (
   RunnerInfo, GetRunnerInfoRequest, GetRunnerInfoResponse,

)
from protos.cluster_runner.cluster_runner_pb2_grpc import ClusterRunnerStub
from protos.cluster_controller.cluster_controller_pb2 import (
    TestInfo, StepInfo, TestStepResult,
    ClusterInfo, GetClusterInfoRequest, GetClusterInfoResponse
)

# -------------------------------------------------------------------------------------------------
#                                                                                     Runner Object
# -----------------------------------------------------------------------------------------------*/
class TestClusterRunner:
    def __init__(self, info:RunnerInfo, stub:ClusterRunnerStub):
        self.info:RunnerInfo = info
        self.stub:ClusterRunnerStub = stub

# -------------------------------------------------------------------------------------------------
#                                                                                       Step Object
# -----------------------------------------------------------------------------------------------*/
TestHandlerType = Callable[[TestClusterRunner], TestStepResult]
class ClusterTestStep:
    def __init__(self,
                info:StepInfo,
                handler:TestHandlerType):
        
        self.info:StepInfo = info
        self.handler:TestHandlerType = handler

    def exec(self, runners: List[TestClusterRunner]) -> Tuple[bool, str, Optional[List[TestStepResult]]]:
        results: List[TestStepResult] = []

        with ThreadPoolExecutor(max_workers=len(runners)) as executor:
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

class ClusterTest:
    def __init__(self,
                 info:TestInfo,
                 steps:List[ClusterTestStep]):
        
        self.info:TestInfo = info
        self.steps:List[ClusterTestStep] = steps

        # Populate the info object with the steps info
        for step in self.steps:
            self.info.steps.append(step.info)


    def exec(self, runners:List[TestClusterRunner], callback:TestCallbackType):
        active_runners:List[TestClusterRunner] = runners

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
#                                                                                      Cluster Info
# -----------------------------------------------------------------------------------------------*/
class TestClusterConfig:
    def __init__(self, 
                 name:str,
                 runners_info:List[RunnerInfo],
                 tests:List[ClusterTest],
                 uuid:str = "",
                 proxy_url:str = "",
                 registry_url:str = ""):
        self.name:str = name
        self.uuid:str = uuid
        self.registry_url:str = registry_url
        self.proxy_url:str = proxy_url
        self.runners_info:List[RunnerInfo] = runners_info
        self.tests:List[ClusterTest] = tests

# -------------------------------------------------------------------------------------------------
#                                                                                           Cluster
# -----------------------------------------------------------------------------------------------*/

class TestCluster:
    def __connect_to_runners(self) -> Tuple[bool, str]:
        # For each user defined runner info
        for runner_info in self.config.runners_info:
            # Connect a new channel and creat a stub to the runner 
            try:            
                # Create the connection string
                runner_url = f"{runner_info.hostname}:{runner_info.serverPort}"

                # Create a gRPC channel
                channel = grpc.insecure_channel(runner_url)

                # Create a stub using the insecure channel
                stub = ClusterRunnerStub(channel)

                # Get the missing runner metadata
                try:
                    response:GetRunnerInfoResponse = stub.GetRunnerInfo(GetClusterInfoRequest())
                    
                    # Populate the dynamic fields
                    for file in response.info.supportedFirmware:
                        runner_info.supportedFirmware.append(file)

                    # Append a new runner to the cluster list
                    new_runner:TestClusterRunner = TestClusterRunner(
                        info=runner_info,
                        stub=stub
                    )
                    self.runners.append(new_runner)

                except grpc.RpcError as e:
                    return False, f"Unable to register cluster at {runner_url}: {e}"

                logging.info(f"Successfully registered runner at {runner_url}!")
            except grpc.RpcError as e:
                return False, f"Failed to connect to runner at {runner_url}. Error: {e}"

        return True, ""