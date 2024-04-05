# Standard includes
import time
import os
import yaml
import subprocess
import logging
from typing import Tuple, List

# 3rd party includes
from kubernetes import client, config,  utils
import grpc

# Protocol includes
from protos.mtib_controller.mtib_controller_pb2 import (
    HealthCheckRequest, HealthCheckResponse
)
from protos.mtib_controller.mtib_controller_pb2_grpc import MtibControllerStub 

# Private includes
from .base import *

# -------------------------------------------------------------------------------------------------
#                                                                                     Configuration
# -----------------------------------------------------------------------------------------------*/
# Runner config
RUNNNER_SERVER_PORT=12345

# Timeouts
HOST_STARTUP_TIMEOUT_S=100
K8S_STARTUP_TIMEOUT_S=500
K8S_DELETE_DEPLOYMENT_TIMEOUT_S=100
K8S_APPLY_DEPLOYMENT_TIMEOUT_S=1000

# -------------------------------------------------------------------------------------------------
#                                                                                     Configuration
# -----------------------------------------------------------------------------------------------*/
# Define supported hardware
supported_hardware = HardwareInfo(
    model = "sigma5",
    version = "1"
)

# Define runners
runners = [
    # Individual Board
    RunnerInfo( id=0,
                name="Control Plane",
                hostname="control-plane",
                serverPort=RUNNNER_SERVER_PORT,
                isInPanel=False,
                panelId=0
            ),

    # Panel 
    RunnerInfo( id=1,
                name="Panel Slot 1",
                hostname="slot-1",
                serverPort=RUNNNER_SERVER_PORT,
                isInPanel=True,
                panelId=1
            ),
    RunnerInfo( id=2,
                name="Panel Slot 2",
                hostname="slot-2",
                serverPort=RUNNNER_SERVER_PORT,
                isInPanel=True,
                panelId=2
            ),
    RunnerInfo( id=3,
                name="Panel Slot 3",
                hostname="slot-3",
                serverPort=RUNNNER_SERVER_PORT,
                isInPanel=True,
                panelId=3
            ),
    RunnerInfo( id=4,
                name="Panel Slot 4",
                hostname="slot-4",
                serverPort=RUNNNER_SERVER_PORT,
                isInPanel=True,
                panelId=4
            ),
    RunnerInfo( id=5,
                name="Panel Slot 5",
                hostname="slot-5",
                serverPort=RUNNNER_SERVER_PORT,
                isInPanel=True,
                panelId=5
            ),
]

# -------------------------------------------------------------------------------------------------
#                                                                                      Test Cluster
# -----------------------------------------------------------------------------------------------*/
class Sigma5TestClusterRunnerItem:
    def __init__(self, info:RunnerInfo, stub:MtibControllerStub):
        self.info:RunnerInfo = info
        self.stub:MtibControllerStub = stub

class Sigma5TestCluster(BaseTestCluster):
    runnerItems:List[Sigma5TestClusterRunnerItem] = []

    def __init__(self, kubeconfig_path: str, deployment_path: str):
        self.kubeconfig_path:str = kubeconfig_path
        self.deployment_path:str = deployment_path

    # --------------------------------------------------------------------------------------------
    #                                                                                        Setup
    # ------------------------------------------------------------------------------------------*/
    def setup(self) -> Tuple[bool, str]:
        logging.info("Starting setup of Sigma5TestCluster.")
        
        # Attempt to connect to all the hosts in the cluster
        success, err = self.__await_for_hosts(runners, HOST_STARTUP_TIMEOUT_S)
        if not success:
            return False, f"Could not connect to cluster hosts: {err}. Is the cluster powered on and all hosts connected?"

        logging.info("All hosts are reachable. Proceeding with Kubernetes nodes check.")

        # Set the k8s logger to only INFO so we don't spam the server logs
        logging.getLogger('kubernetes').setLevel(logging.INFO)

        # Await for Kubernetes to be fully setup on all the nodes
        success, err = self.__await_for_k8s_nodes(self.kubeconfig_path, K8S_STARTUP_TIMEOUT_S)
        if not success:
            return False, f"Kubernetes nodes failed to initialize: {err}"
        
        logging.info("All nodes are ready. Proceeding deployments.")
        
        # Delete any deployments present in the host
        success, err = self.__delete_k8s_deployments(self.kubeconfig_path, K8S_STARTUP_TIMEOUT_S)
        if not success:
            return False, f"Failed to delete kubernetes deployment: {err}"
        
        # Apply the latest deployment to the cluster
        success, err = self.__apply_k8s_deployment(self.kubeconfig_path, self.deployment_path)
        if not success:
            return False, f"Failed to apply kubernetes deployment to cluster: {err}"

        # Connect to all the runners over gRPC and get their info
        success, err = self.__connect_to_runners()
        if not success:
            return False, f"Failed to apply kubernetes deployment to cluster: {err}"

        logging.info("Sigma 5 test cluster was setup correctly")
        return True, ""
    
    def __await_for_hosts(self, runners: List[RunnerInfo], timeout: int) -> Tuple[bool, str]:
        """Attempts to ping all the hosts in the runner list in a loop until all are reachable or a timeout occurs."""
        logging.info("Attempting to reach all hosts in the runners list.")
        
        start_time = time.time()
        unreachable_runners = runners.copy()  # Initialize with all runners
        
        while time.time() - start_time < timeout and unreachable_runners:
            for runner in unreachable_runners[:]:  # Iterate a copy of the list to modify the original list safely
                target = runner.hostname
                try:
                    logging.info(f"Pinging host {target}.")
                    response = subprocess.run(["ping", "-c", "1", "-W", str(1), target], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    
                    if response.returncode == 0:
                        logging.info(f"Successfully pinged {runner.hostname}.")
                        unreachable_runners.remove(runner)  # Host is reachable, remove it from the list
                    else:
                        logging.debug(f"Host {target} not yet reachable. Will retry.")
                
                except Exception as e:
                    logging.error(f"Error pinging host {target}: {str(e)}")
                    # Even in case of error, we'll retry until timeout, so no action needed here

            # Optionally sleep for a bit to prevent hammering the network with constant pings
            time.sleep(1)

        if not unreachable_runners:
            return True, ""
        else:
            # Timeout reached but some hosts are still unreachable
            unreachable_hosts = ', '.join([runner.hostname for runner in unreachable_runners])
            return False, f"Timeout reached. Could not verify hosts: {unreachable_hosts}"

    def __await_for_k8s_nodes(self, kubeconfig_path: str, timeout: int) -> Tuple[bool, str]:
        """Awaits for the Kubernetes nodes in the cluster to all be in the ready state."""
        logging.info("Checking readiness of Kubernetes nodes.")
        config.load_kube_config(kubeconfig_path)
        v1 = client.CoreV1Api()

        start_time = time.time()
        
        while time.time() - start_time < timeout:
            nodes = v1.list_node().items
            all_ready = all(node.status.conditions[-1].type == 'Ready' for node in nodes)
            
            if all_ready:
                logging.info(f"All nodes in cluster are ready, time taken: {time.time() - start_time}")
                return True, ""
            
            time.sleep(5)  # Wait for a bit before checking again
        
        return False, f"Timeout {timeout}s reached, not all nodes are ready."
    
    def __delete_k8s_deployments(self, kubeconfig_path: str, timeout: int) -> Tuple[bool, str]:
        """Deletes all Kubernetes deployments in the default namespace and waits for their pods to be terminated."""
        logging.info("Deleting all Kubernetes deployments in the default namespace.")
        config.load_kube_config(kubeconfig_path)
        apps_v1 = client.AppsV1Api()
        core_v1 = client.CoreV1Api()

        try:
            # Delete all deployments
            apps_v1.delete_collection_namespaced_deployment(namespace='default')
            start_time = time.time()

            # Loop until all pods are terminated or timeout
            while time.time() - start_time < timeout:
                pods = core_v1.list_namespaced_pod(namespace='default').items
                # Filter pods to find those associated with deployments
                # This assumes pods have a label 'app' that matches the deployment name, adjust as needed
                deployment_pods = [pod for pod in pods if pod.metadata.labels.get('app')]
                
                if not deployment_pods:
                    return True, ""
                
                logging.debug(f"Waiting for {len(deployment_pods)} pods to be deleted...")
                time.sleep(1)
            
            return False, "Timeout reached before all pods were deleted."

        except Exception as e:
            return False, f"Failed to delete deployments: {str(e)}"

    def __apply_k8s_deployment(self, kubeconfig_path: str, deployment_path: str, timeout: int = 300) -> Tuple[bool, str]:
        """Applies a specific Kubernetes deployment to the cluster and waits for the pods to be ready."""
        logging.info(f"Applying Kubernetes deployment from: {deployment_path}")
        config.load_kube_config(kubeconfig_path)

        try:
            with open(deployment_path, 'r') as file:
                deployment_yaml = yaml.safe_load(file)
            
            k8s_client = client.ApiClient()
            utils.create_from_yaml(k8s_client, yaml_objects=[deployment_yaml], namespace="default")
            
            deployment_name = deployment_yaml.get("metadata", {}).get("name", "")
            if not deployment_name:
                return False, "Deployment name could not be extracted from the YAML file."

            logging.info("Deployment applied successfully. Waiting for pods to become ready.")
            
            return self.__wait_for_deployment_pods_ready(deployment_name, "default", kubeconfig_path, timeout)
            
        except Exception as e:
            return False, f"Failed to apply deployment from {deployment_path}: {str(e)}"

    def __wait_for_deployment_pods_ready(self, deployment_name: str, namespace: str, kubeconfig_path: str, timeout: int) -> Tuple[bool, str]:
        """Waits for all pods in a deployment to be in the 'Ready' state and reports any errors."""
        config.load_kube_config(kubeconfig_path)
        apps_v1 = client.AppsV1Api()
        core_v1 = client.CoreV1Api()
        start_time = time.time()

        while time.time() - start_time < timeout:
            try:
                deployment = apps_v1.read_namespaced_deployment(name=deployment_name, namespace=namespace)
                if deployment.status.ready_replicas == deployment.spec.replicas:
                    logging.info(f"All pods for deployment {deployment_name} are ready.")
                    return True, "All pods are ready."
            except client.exceptions.ApiException as e:
                logging.error(f"Error fetching deployment {deployment_name}: {e}")
                return False, f"Error fetching deployment {deployment_name}: {str(e)}"

            pod_list = core_v1.list_namespaced_pod(namespace=namespace, label_selector=f"app={deployment_name}")
            for pod in pod_list.items:
                if pod.status.phase == "Pending":
                    field_selector = f"involvedObject.name={pod.metadata.name},involvedObject.namespace={namespace}"
                    events = core_v1.list_namespaced_event(namespace=namespace, field_selector=field_selector)
                    for event in events.items:
                        logging.debug(f"Event for {pod.metadata.name}: {event.message}")
                        if "Failed" in event.reason:
                            error_details = f"{event.reason}: {event.message}"
                            logging.error(error_details)
                            return False, error_details

            time.sleep(1)  # Sleep before the next check to avoid overwhelming the API server

        return False, "Timeout reached. Not all pods are ready."

    def __connect_to_runners(self) -> Tuple[bool, str]:
        for runner in runners:
            # Connect a new channel and creat a stub to the runner 
            try:            
                # Create the connection string
                runner_url = f"{runner.hostname}:{runner.serverPort}"

                # Create a gRPC channel
                channel = grpc.insecure_channel(runner_url)

                # Create a stub using the insecure channel
                stub = MtibControllerStub(channel)

                # Get cluster metadata
                try:
                    #TODO: Populate the IP and the file info in the runner

                    # We are ready to add this runner to our list succesfully
                    new_runner_item:Sigma5TestClusterRunnerItem = Sigma5TestClusterRunnerItem(
                        info=runner,
                        stub=stub
                    )

                    self.runnerItems.append(new_runner_item)

                except grpc.RpcError as e:
                    return False, f"Unable to register cluster at {runner_url}: {e}"

                logging.info(f"Successfully registered runner at {runner_url}!")
            except grpc.RpcError as e:
                return False, f"Failed to connect to cluster at {runner_url}. Error: {e}"

        return True, ""
    
    # --------------------------------------------------------------------------------------------
    #                                                                             Get Cluster Data
    # ------------------------------------------------------------------------------------------*/
    def get_cluster_metadata(self) -> ClusterInfo:
        info:ClusterInfo = ClusterInfo(
            runners = runners,
            supportedHardware = supported_hardware
        )

        return info
