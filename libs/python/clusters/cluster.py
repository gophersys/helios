# Standard includes
import time
import os
import yaml
import subprocess
import logging
from typing import Tuple, List, Callable, Optional

# 3rd party includes
from kubernetes import client, config,  utils
import grpc

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
class TestClusterRunner:
    def __init__(self, info:RunnerInfo, stub:MtibRunnerStub):
        self.info:RunnerInfo = info
        self.stub:MtibRunnerStub = stub

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
#                                                                                Cluster Deployment
# -----------------------------------------------------------------------------------------------*/
class TestClusterDeployment:
    def __init__(self, 
                 k8s_deployment_path:str,
                 ):
        self.name:str = name
        self.runners_info:List[RunnerInfo] = runners_info
        self.tests:List[ClusterTest] = tests

# -------------------------------------------------------------------------------------------------
#                                                                                      Cluster Info
# -----------------------------------------------------------------------------------------------*/
class TestClusterConfig:
    def __init__(self, 
                 name:str,
                 runners_info:List[RunnerInfo],
                 tests:List[ClusterTest]):
        self.name:str = name
        self.runners_info:List[RunnerInfo] = runners_info
        self.tests:List[ClusterTest] = tests

# -------------------------------------------------------------------------------------------------
#                                                                                           Cluster
# -----------------------------------------------------------------------------------------------*/

class TestCluster:
    # Runner config
    RUNNNER_SERVER_PORT=12345               # Where the runner service is being served at

    # Timeouts
    HOST_STARTUP_TIMEOUT_S=60               # Linux kernel up and running
    K8S_AWAIT_NODES_TIMEOUT_S=120           # Docker & k8s
    K8S_DELETE_DEPLOYMENT_TIMEOUT_S=120      # Delete deployment
    K8S_APPLY_DEPLOYMENT_TIMEOUT_S=240      # Apply deployment, a new image could take a while!

    def __init__(self, config:TestClusterConfig):
        """Instantiates a new test cluster instance with the desired configuration."""
        
        self.config:TestClusterConfig = config
        self.runners:List[TestClusterRunner] = []

        self.k8s_config_set:bool = False

    def setup(self, kubeconfig_path:str) -> Tuple[bool, str]:
        """Tries to initialize the cluster by following the same steps a human operator
           would follow when trying to recover and or setup the cluster"""
        
        logging.info(f"Starting setup for cluster {self.config.name}.")

        # First check that the k8s deployment passed is valid
        try:
            config.load_kube_config(self.kubeconfig_path)
        except config.ConfigException as e:
            return False,f"Could not configure test cluster {self.config.name} kubernetes configuration: {e}"

        # Ping all the hosts first, make sure the kernel is at least booted
        success, err = self.__await_for_hosts_ping()
        if not success:
            return False, f"One or more runners could not be reached: {err}. Is the cluster powered on and all hosts connected?"

        logging.info("All hosts are reachable. Proceeding with Kubernetes nodes check...")

        # # Await for Kubernetes to be fully setup on all the runners
        # success, err = self.__await_for_k8s_nodes()
        # if not success:
        #     return False, f"Kubernetes nodes failed to initialize: {err}. Are all the servers "
        
        # logging.info("All nodes are ready. Proceeding to delete all deployments...")
        
        # # Wipe everything ont the cluster, and start fresh every time, with the latest deployment
        # success, err = self.__delete_k8s_deployments(K8S_DELETE_DEPLOYMENT_TIMEOUT_S)
        # if not success:
        #     return False, f"Failed to delete kubernetes deployment: {err}"
        
        # logging.info("Deployments deleted. Proceeding to apply latest deployment...")

        # # Apply the latest deployment to the cluster
        # success, err = self.__apply_k8s_deployment(K8S_APPLY_DEPLOYMENT_TIMEOUT_S)
        # if not success:
        #     return False, f"Failed to apply kubernetes deployment to cluster: {err}"

        # # Await for all the pods to be ready
        # success, err = self.__wait_for_deployment_pods_ready(K8S_APPLY_DEPLOYMENT_TIMEOUT_S)
        # if not success:
        #     return False, f"Failed to apply kubernetes deployment to cluster: {err}"

        # logging.info("Deployments is running and ready. Proceeding to connect to runners...")

        # # Allow for some time for the servers to be up
        # time.sleep(20)

        # # Connect to all the runners service over gRPC
        # success, err = self.__connect_to_runners()
        # if not success:
        #     return False, f"Failed to apply kubernetes deployment to cluster: {err}"

        # logging.info("Sigma 5 test cluster was setup correctly")
        return True, ""

    def __await_for_hosts_ping(self) -> Tuple[bool, str]:
        """Attempts to ping all the hosts in the runner's info list in a loop until all are reachable or a timeout occurs."""

        logging.debug("Attempting to reach all hosts in the runners list.")
        
        start_time = time.time()
        timeout = self.HOST_STARTUP_TIMEOUT_S

        unreachable_runners = self.config.runners_info.copy()  # Iterate a copy of the list to modify the original list safely
        
        # Ping all the hosts until available or timeout
        while time.time() - start_time < timeout and unreachable_runners:
            for runner in unreachable_runners[:]:  
                target = runner.hostname
                try:
                    logging.debug(f"Pinging host {target}.")
                    response = subprocess.run(["ping", "-c", "1", "-W", str(0.5), target], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    
                    if response.returncode == 0:
                        logging.debug(f"Successfully pinged {runner.hostname}.")
                        unreachable_runners.remove(runner)  # Host is reachable, remove it from the list
                    else:
                        logging.debug(f"Host {target} not yet reachable. Will retry.")
                
                except Exception as e:
                    logging.warning(f"Error occurred pinging host {target}: {str(e)}, kernel may not be ready yet?")
                    # Even in case of error, we'll retry until timeout, so no action needed here

            time.sleep(0.2)  # Sleep for a bit to prevent hammering the network with constant pings

        if not unreachable_runners:
            # We found all our hosts!
            return True, ""
        else:
            # Timeout reached but some hosts are still unreachable
            unreachable_hosts = ', '.join([runner.hostname for runner in unreachable_runners])
            return False, f"Timeout reached. Could not verify hosts: {unreachable_hosts}"

    # def __await_for_k8s_nodes(self) -> Tuple[bool, str]:
    #     """Awaits for the Kubernetes nodes in the cluster to all be in the Ready state."""

    #     v1 = client.CoreV1Api()
    #     config.load_kube_config(self.kubeconfig_path)
    #     start_time = time.time()
        
    #     while time.time() - start_time < timeout:
    #         nodes = v1.list_node().items
    #         all_ready = all(node.status.conditions[-1].type == 'Ready' for node in nodes)
            
    #         if all_ready:
    #             logging.info(f"All nodes in cluster are ready, time taken: {time.time() - start_time}")
    #             return True, ""
            
    #         time.sleep(5)  # Wait for a bit before checking again
        
    #     return False, f"Timeout {timeout}s reached, not all nodes are ready."
    
    # def __delete_k8s_deployments(self, timeout:int) -> Tuple[bool, str]:
    #     """Deletes all Kubernetes deployments in the default namespace and waits for their pods to be terminated."""
    #     logging.info("Deleting all Kubernetes deployments in the default namespace.")
    #     config.load_kube_config(self.kubeconfig_path)
    #     apps_v1 = client.AppsV1Api()
    #     core_v1 = client.CoreV1Api()

    #     try:
    #         # Delete all deployments
    #         apps_v1.delete_collection_namespaced_deployment(namespace='default')
    #         start_time = time.time()

    #         # Loop until all pods are terminated or timeout
    #         while time.time() - start_time < timeout:
    #             pods = core_v1.list_namespaced_pod(namespace='default').items
    #             # Filter pods to find those associated with deployments
    #             # This assumes pods have a label 'app' that matches the deployment name, adjust as needed
    #             deployment_pods = [pod for pod in pods if pod.metadata.labels.get('app')]
                
    #             if not deployment_pods:
    #                 return True, ""
                
    #             logging.debug(f"Waiting for {len(deployment_pods)} pods to be deleted...")
    #             time.sleep(1)
            
    #         return False, "Timeout reached before all pods were deleted."

    #     except Exception as e:
    #         return False, f"Failed to delete deployments: {str(e)}"

    # def __apply_k8s_deployment(self, timeout:int) -> Tuple[bool, str]:
    #     """Applies a specific Kubernetes deployment to the cluster and waits for the pods to be ready."""
    #     logging.info(f"Applying Kubernetes deployment from: {self.deployment_path}")
    #     config.load_kube_config(self.kubeconfig_path)

    #     try:
    #         with open(self.deployment_path, 'r') as file:
    #             deployment_yaml = yaml.safe_load(file)
            
    #         k8s_client = client.ApiClient()
    #         utils.create_from_yaml(k8s_client, yaml_objects=[deployment_yaml], namespace="default")
            
    #         self.deployment_name = deployment_yaml.get("metadata", {}).get("name", "")
    #         if not self.deployment_name:
    #             return False, "Deployment name could not be extracted from the YAML file."

    #         logging.info("Deployment applied successfully. Waiting for pods to become ready.")
            
    #         return True, ""
            
    #     except Exception as e:
    #         return False, f"Failed to apply deployment from {self.deployment_path}: {str(e)}"

    # def __wait_for_deployment_pods_ready(self, timeout:int) -> Tuple[bool, str]:
    #     """Waits for all pods in a deployment to be in the 'Ready' state and reports any errors."""
    #     config.load_kube_config(self.kubeconfig_path)
    #     apps_v1 = client.AppsV1Api()
    #     core_v1 = client.CoreV1Api()
    #     start_time = time.time()
        
    #     while time.time() - start_time < timeout:
    #         try:
    #             deployment = apps_v1.read_namespaced_deployment(name=self.deployment_name, namespace=self.deployment_namespace)
    #             if deployment.status.ready_replicas == deployment.spec.replicas:
    #                 logging.info(f"All pods for deployment {self.deployment_name} are ready.")
    #                 return True, ""
    #         except client.exceptions.ApiException as e:
    #             return False, f"Error fetching deployment {self.deployment_name}: {str(e)}"

    #         pod_list = core_v1.list_namespaced_pod(namespace=self.deployment_namespace, label_selector=f"app={self.deployment_name}")
    #         for pod in pod_list.items:
    #             if pod.status.phase == "Pending":
    #                 field_selector = f"involvedObject.name={pod.metadata.name},involvedObject.namespace={self.deployment_namespace}"
    #                 events = core_v1.list_namespaced_event(namespace=self.deployment_namespace, field_selector=field_selector)
    #                 for event in events.items:
    #                     logging.debug(f"Event for {pod.metadata.name}: {event.message}")
    #                     if "Failed" in event.reason:
    #                         error_details = f"{event.reason}: {event.message}"
    #                         return False, error_details

    #         time.sleep(1)  # Sleep before the next check to avoid overwhelming the API server

    #     return False, "Timeout reached. Not all pods are ready."

    # def __connect_to_runners(self) -> Tuple[bool, str]:
    #     # For each user defined runner info
    #     for runner_info in runners_info:
    #         # Connect a new channel and creat a stub to the runner 
    #         try:            
    #             # Create the connection string
    #             runner_url = f"{runner_info.hostname}:{runner_info.serverPort}"

    #             # Create a gRPC channel
    #             channel = grpc.insecure_channel(runner_url)

    #             # Create a stub using the insecure channel
    #             stub = MtibRunnerStub(channel)

    #             # Get the missing runner metadata
    #             try:
    #                 response:GetRunnerInfoResponse = stub.GetRunnerInfo(GetClusterInfoRequest())
                    
    #                 # Populate the dynamic fields
    #                 for file in response.info.supportedFirmware:
    #                     runner_info.supportedFirmware.append(file)

    #                 # Append a new runner to the cluster list
    #                 new_runner:ClusterRunner = ClusterRunner(
    #                     info=runner_info,
    #                     stub=stub
    #                 )
    #                 self.runners.append(new_runner)

    #             except grpc.RpcError as e:
    #                 return False, f"Unable to register cluster at {runner_url}: {e}"

    #             logging.info(f"Successfully registered runner at {runner_url}!")
    #         except grpc.RpcError as e:
    #             return False, f"Failed to connect to runner at {runner_url}. Error: {e}"

    #     return True, ""