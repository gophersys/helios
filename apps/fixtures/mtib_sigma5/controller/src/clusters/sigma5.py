# Standard includes
import time
import os
import yaml
import subprocess
import logging
from typing import Tuple, List

# 3rd party includes
from kubernetes import client, config,  utils

# Private includes
from .base import *

# Configuration
HOST_STARTUP_TIMEOUT_S=100
K8S_STARTUP_TIMEOUT_S=500
K8S_DELETE_DEPLOYMENT_TIMEOUT_S=100
K8S_APPLY_DEPLOYMENT_TIMEOUT_S=1000

# Define runners
runners = [
    RunnerInfo( id=1,
                name="Control Plane",
                hostname="control-plane",
                serverPort=12345,
                ipAddr="",
                isInPanel=False,
                panelId=0
            ),
]

class Sigma5TestCluster(BaseTestCluster):
    def __init__(self, kubeconfig_path: str, deployment_path: str):
        self.kubeconfig_path:str = kubeconfig_path
        self.deployment_path:str = deployment_path

    def setup(self) -> Tuple[bool, str]:
        logging.info("Starting setup of Sigma5TestCluster.")
        
        # Attempt to connect to all the hosts in the cluster
        success, err = self.__await_for_hosts(runners, HOST_STARTUP_TIMEOUT_S)
        if not success:
            return False, f"Could not connect to cluster hosts: {err}. Is the cluster powered on and all hosts connected?"

        logging.info("All hosts are reachable. Proceeding with Kubernetes nodes check.")

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
        
        # Apply the latest deployment to the cluster
        success, err = self.__wait_for_deployment_ready(self.kubeconfig_path, self.deployment_path, K8S_APPLY_DEPLOYMENT_TIMEOUT_S)
        if not success:
            return False, f"Failure in kubernetes deployment to cluster: {err}"

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
        """Deletes all Kubernetes deployments in the default namespace."""
        logging.info("Deleting all Kubernetes deployments in the default namespace.")
        config.load_kube_config(kubeconfig_path)
        apps_v1 = client.AppsV1Api()

        try:
            # Delete all deployments
            apps_v1.delete_collection_namespaced_deployment(namespace='default')
            start_time = time.time()

            while time.time() - start_time < timeout:
                deployments = apps_v1.list_namespaced_deployment(namespace='default')
                if not deployments.items:
                    logging.info("All deployments successfully deleted.")
                    return True, ""
                
                logging.debug("Waiting for deployments to be deleted...")
                time.sleep(1)
            
            return False, "Timeout reached before all deployments were deleted."
        except Exception as e:
            return False, f"Failed to delete deployments: {str(e)}"

    def __apply_k8s_deployment(self, kubeconfig_path: str, deployment_path: str) -> Tuple[bool, str]:
        """Applies a specific Kubernetes deployment to the cluster."""
        logging.info("Applying a specific Kubernetes deployment.")
        config.load_kube_config(kubeconfig_path)

        try:
            # Open and read the YAML file content
            with open(deployment_path, 'r') as file:
                deployment_yaml = yaml.safe_load(file)
            
            k8s_client = client.ApiClient()
            # Now using `yaml_objects` with a list wrapping the loaded YAML
            utils.create_from_yaml(k8s_client, yaml_objects=[deployment_yaml], namespace="default")

            logging.info("Deployment applied successfully.")
            return True, ""
        except Exception as e:
            logging.error(f"Failed to apply deployment: {str(e)}")
            return False, f"Failed to apply deployment: {str(e)}"
        
    def __wait_for_deployment_ready(self, kubeconfig_path: str, deployment_path: str, timeout: int) -> Tuple[bool, str]:
        """Waits for all pods in a deployment to be in the 'Ready' state."""
        logging.info("Loading Kubernetes configuration.")
        config.load_kube_config(kubeconfig_path)
        
        # Load the deployment name from the YAML file
        with open(deployment_path, 'r') as file:
            deployment_yaml = yaml.safe_load(file)
        deployment_name = deployment_yaml.get("metadata", {}).get("name", "")
        if not deployment_name:
            return False, "Deployment name could not be extracted from the YAML file."

        logging.info(f"Waiting for deployment {deployment_name} to be ready.")
        apps_v1 = client.AppsV1Api()
        core_v1 = client.CoreV1Api()
        start_time = time.time()
        namespace = "default"  # Assuming the default namespace, adjust as necessary

        while time.time() - start_time < timeout:
            try:
                deployment = apps_v1.read_namespaced_deployment(name=deployment_name, namespace=namespace)
                if deployment.status.ready_replicas == deployment.status.replicas:
                    logging.info("Deployment ready.")
                    return True, ""
            except client.exceptions.ApiException as e:
                if e.status != 404:
                    return False, f"Error fetching deployment: {str(e)}"

            # Check for not ready pods and gather verbose error info
            pod_list = core_v1.list_namespaced_pod(namespace=namespace, label_selector=f"app={deployment_name}")
            for pod in pod_list.items:
                if pod.status.phase != "Running" or not all(container.ready for container in pod.status.container_statuses):
                    node_name = pod.spec.node_name
                    pod_name = pod.metadata.name
                    return False, f"Pod {pod_name} on node {node_name} is not ready. Phase: {pod.status.phase}."

            time.sleep(1)  # Sleep before next check

        return False, "Timeout waiting for deployment to be ready."

    def get_cluster_metadata(self) -> dict:
        return []
    