import logging
import grpc
import uuid
import time
import socket
import threading
from typing import Tuple, Any, List, Optional
import re
import subprocess
import yaml
import os
from urllib.parse import urlparse
from enum import Enum
import requests
import sys

# 3rd Party includes
import docker
import kubernetes

# Protocol includes
from protos.cluster_test.cluster_test_pb2 import (
    TestInfo, HealthCheckRequest, HealthCheckResponse
)
from protos.cluster_test.cluster_test_pb2_grpc import ClusterTestStub

from protos.cluster_operator.cluster_operator_pb2 import (
    OperatorStatus
)

# -------------------------------------------------------------------------------------------------
#                                                                                       Deployments
# -----------------------------------------------------------------------------------------------*/
class ClusterDeploymentStatus(Enum):
    NO_DEPLOYMENT = 1
    DEPLOYMENT_ACTIVE = 2

class ClusterDeploymentInfo:
    def __init__(self,
                name:str = "",
                path:str = "",
                status:ClusterDeploymentStatus = ClusterDeploymentStatus.NO_DEPLOYMENT):
        self.name:str = name
        self.path:str = path
        self.status:ClusterDeploymentStatus = status

# -------------------------------------------------------------------------------------------------
#                                                                                            Config
# -----------------------------------------------------------------------------------------------*/
class ClusterOperatorConfig:
    def __init__(self,
                 uuid:str,
                 proxy_url:str,
                 registry_port:int,
                 grpc_server_url:str,
                 nodes_hostnames:List[str],
                 kubeconfig_path:str):
        self.uuid:str = uuid
        self.proxy_url:str = proxy_url
        self.registry_port:int = registry_port
        self.grpc_server_url:str = grpc_server_url
        self.nodes_hostnames:List[str] = nodes_hostnames
        self.kubeconfig_path:str = kubeconfig_path

# -------------------------------------------------------------------------------------------------
#                                                                                        Test Entry
# -----------------------------------------------------------------------------------------------*/
class ClusterOperatorTestEntry:
    def __init__(self,
                 info:TestInfo,
                 port:int,
                 channel:grpc.Channel,
                 stub:ClusterTestStub):
        self.info:TestInfo = info
        self.port:int = port
        self.channel:grpc.Channel = channel
        self.stub:ClusterTestStub = stub
    
# -------------------------------------------------------------------------------------------------
#                                                                                          Operator
# -----------------------------------------------------------------------------------------------*/
class ClusterOperatorStatus(Enum):
    STARTING = 1
    CLUSTER_READY = 2
    
class ClusterOperator:
    # Timeoutes
    HOST_STARTUP_TIMEOUT_S=120              # Linux kernel up and running
    K8S_AWAIT_NODES_TIMEOUT_S=120           # Docker & k8s
    K8S_DELETE_DEPLOYMENT_TIMEOUT_S=120     # Delete deployment
    K8S_APPLY_DEPLOYMENT_TIMEOUT_S=240      # Apply deployment, a new image could take a while!
    PROXY_REGISTRATION_RETRY_TIMEOUT_S=5    # How often to retry registering ourselves with the cluster
    
    def __init__(self, config:ClusterOperatorConfig):
        # Set the internal configuration
        self.config:ClusterOperatorConfig = config
        
        # Set the global object error
        self.error:str = ""
        
        # Set the initial global object state
        self.status:OperatorStatus = OperatorStatus.STARTING
        
        # Docker info
        logger = logging.getLogger('docker')
        logger.setLevel(logging.INFO)
        self.docker_client = docker.from_env()

        # Kubernetes info
        logger = logging.getLogger('kubernetes')
        logger.setLevel(logging.INFO)
        self.kubernets_client = kubernetes.client
        self.deployment_namespace = "default"  
        self.deployment_info:ClusterDeploymentInfo = ClusterDeploymentInfo()

        # Tests 
        self.tests:List[ClusterOperatorTestEntry] = []
        
        self.stop_event = threading.Event()
        
        # Start the object thread
        self._thread = threading.Thread(target=self._main_thread, daemon=True)
        self._thread.start()
        
        self._health_thread = threading.Thread(target=self._tests_health_check_thread, daemon=False)
        self._health_thread.start()
        
        self._proxy_thread = threading.Thread(target=self._proxy_health_check_thread, daemon=False)
        self._proxy_thread.start()
    
    def stop(self):
        self.stop_event.set()
        self._thread.join(timeout=1)
        self._health_thread.join(timeout=1)
        self._proxy_thread.join(timeout=1)
    
    def get_status(self) -> Tuple[Any, str]:
        return self.status, self.error
    
    def register_test(self, port:int, info:TestInfo) -> str:
        # Make sure that a test isn't trying to register on a same port
        for test in self.tests:
            if test.port == port:
                return f"Operator already has test \"{test.info.name}\" registered at port {port}"
            
        # Build the test URL
        test_url = f"localhost:{port}"
        
        # Attempt to connect to the test over gRPC
        try:
            # Create a gRPC channel
            channel = grpc.insecure_channel(test_url)

            # Create a stub using the insecure channel
            stub = ClusterTestStub(channel)
            
            # Do a quick health check
            try:
                stub.HealthCheck(HealthCheckRequest())
            except grpc.RpcError as e:
                return f"Health check failed for test at {test_url}: {e}"
            
            test_entry:ClusterOperatorTestEntry = ClusterOperatorTestEntry(
                info=info,
                port=port,
                channel=channel,
                stub=stub
            )
            
            self.tests.append(test_entry)
            logging.info(f"Registered test \"{info.name}\" at {test_url}")
            return ""
            
        except grpc.RpcError as e:
            return f"Failed to connect to operator at {test_url} over gRPC. Error: {e}"
        
    def list_tests(self) -> List[TestInfo]:
        tests_info:List[TestInfo] = []
        for test in self.tests:
            tests_info.append(test.info)
            
        return tests_info
        
    def _main_thread(self):
        # Create registry if not already present
        error = self._setup_local_registry()
        if error:
            return f"Could not setup local container registry: {error}"
        
        # Await for all the nodes in this cluster to be ready
        error = self._await_for_cluster_readiness()
        if error:
            return f"Cluster was not ready before timeout: {error}"

        # We are now ready for tests to be registered, as well as ready for connection 
        # to the proxy
        self.status = OperatorStatus.READY
        
        # Now we just attempt to register until the end of times or until we're actually registerde
        self._register_with_proxy()
        
        # Main loop
        while not self.stop_event.is_set():
            if self.status == OperatorStatus.READY:
                # Proxy was disconnected, try to register
                self._register_with_proxy()
                
            time.sleep(1)

    def _proxy_health_check_thread(self):
        while not self.stop_event.is_set():
            if self.status == OperatorStatus.CONNECTED:
                try:
                    # Do an HTTP request to the proxy for registration
                    endpoint = f"{self.config.proxy_url}/v1/healthcheck"

                    response = requests.get(endpoint, timeout=1)
                    if response.status_code != 200:
                        self.status = OperatorStatus.READY
                        logging.error(f"Proxy healthcheck failed. Is the proxy down? Status code for GET {endpoint}: {response.status_code}")

                except Exception as e:
                    self.status = OperatorStatus.READY
                    logging.warning(f"Network error: could not GET healthcheck in proxy server {str(e)}")

            time.sleep(1)
            
    def _tests_health_check_thread(self):
        """Periodically check the health of each cluster."""
        while not self.stop_event.is_set():
            tests = self.tests
            for test in tests:
                try:
                    # Perform a periodic health check to ensure we're still connected and alive
                    test.stub.HealthCheck(HealthCheckRequest())
                    
                except grpc.RpcError as e:
                    logging.error(f"Failed to perform health check on test at {test.port}. Unregistering from operator")
                    test.channel.close()
                    self.tests.remove(test)
                    
                time.sleep(1)

            time.sleep(1)
            
    def _await_for_cluster_readiness(self) -> str:
        # First check that the k8s deployment passed is valid
        try:
            kubernetes.config.load_kube_config(self.config.kubeconfig_path)
        except kubernetes.config.ConfigException as e:
            return f"Could not configure test cluster {self.config.name} kubernetes configuration: {e}"

        # Basic network test, make sure the kernel is at least running
        error = self.__await_for_hosts_ping()
        if error:
            return f"Could not ping all hosts in cluster: {error}"
        
        logging.info("All hosts were found in the network, proceeding to check kubernetes cluster readiness...")
        
        # Readiness check for all the nodes in the cluster
        error = self.__await_for_k8s_nodes()
        if error:
            return f"Nodes readiness probe did not pass: {error}"
        
        logging.info("Kubernetes cluster is ready, deleting all deployments...")
        
        # Wipe the cluster of any deployments
        error = self.__delete_k8s_deployments()
        if error:
            return f"Could not clear cluster of running deployments: {error}"
        
        logging.info("All deployments have been removed, cluster is ready for operation!")

        return ""
    
    def __await_for_hosts_ping(self) -> str:
        logging.info("Attempting to ping all hosts in the runners list...")

        start_time = time.time()
        timeout = self.HOST_STARTUP_TIMEOUT_S
        unreachable_nodes = self.config.nodes_hostnames.copy()

        # Function to ping a single host
        def ping_host(hostname):
            try:
                response = subprocess.run(["ping", "-c", "1", "-W", "1", hostname], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                if response.returncode == 0:
                    logging.debug(f"Successfully pinged {hostname}.")
                    if hostname in unreachable_nodes:
                        unreachable_nodes.remove(hostname)
                else:
                    logging.debug(f"Host {hostname} not yet reachable.")
            except Exception as e:
                logging.warning(f"Error occurred pinging host {hostname}: {str(e)}")

        # Thread list
        threads = []

        # Keep pinging until all hosts are reachable or timeout occurs
        while time.time() - start_time < timeout and unreachable_nodes:
            for hostname in unreachable_nodes[:]:
                thread = threading.Thread(target=ping_host, args=(hostname,))
                threads.append(thread)
                thread.start()

            # Wait for all threads to complete
            for thread in threads:
                thread.join(timeout=(timeout - (time.time() - start_time)))

            time.sleep(0.2)  # Sleep to prevent too many rapid pings

        if not unreachable_nodes:
            return ""
        else:
            unreachable_hosts = ', '.join(unreachable_nodes)
            return f"Timeout reached. Could not verify hosts: {unreachable_hosts}"
        
    def __await_for_k8s_nodes(self) -> str:
        """Awaits for the Kubernetes nodes in the cluster to all be in the Ready state."""

        timeout:int = self.K8S_AWAIT_NODES_TIMEOUT_S
        
        v1 = self.kubernets_client.CoreV1Api()
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            nodes = v1.list_node().items
            all_ready = all(node.status.conditions[-1].type == 'Ready' for node in nodes)
            
            if all_ready:
                logging.info(f"All nodes in cluster are ready, time taken: {time.time() - start_time}")
                return ""
            
            time.sleep(5)  # Wait for a bit before checking again
        
        return f"Timeout {timeout}s reached, not all nodes are ready."

    def __delete_k8s_deployments(self) -> str:
        """Deletes all Kubernetes deployments in the default namespace and waits for their pods to be terminated."""
        logging.info("Deleting all Kubernetes deployments in the default namespace.")

        timeout:int = self.K8S_DELETE_DEPLOYMENT_TIMEOUT_S

        apps_v1 = self.kubernets_client.AppsV1Api()
        core_v1 = self.kubernets_client.CoreV1Api()

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
                    return ""
                
                logging.debug(f"Waiting for {len(deployment_pods)} pods to be deleted...")
                time.sleep(1)
            
            return "Timeout reached before all pods were deleted."
        except Exception as e:
            return f"Failed to delete deployments: {str(e)}"
        
    def _setup_local_registry(self) -> str:
        logging.debug(f"Setting up local registry at port {self.config.registry_port}...")
        client = docker.from_env()

        try:
            # Check if a registry is running on that port
            all_containers = client.containers.list(all=True)
            registry_running = False
            for container in all_containers:
                container_ports = container.attrs['HostConfig']['PortBindings'] or {}
                for port, bindings in container_ports.items():
                    if port.split('/')[0] == str(self.config.registry_port) and bindings:
                        registry_running = True
                        break

            if not registry_running:
                logging.info("No local registry found. Creating one...")
                client.containers.run("registry:2", ports={f'{self.config.registry_port}/tcp': self.config.registry_port}, detach=True)
            else:
                logging.info("Local registry already running.")

        except docker.errors.APIError as e:
            error_message = f"Failed to check or create local registry: {str(e)}"
            logging.error(error_message)
            return error_message

        logging.info(f"Local registry at port {self.config.registry_port} setup OK")
        return ""

    def _register_with_proxy(self):
        retry_counter:int = 0
        while True:
            try:
                # Do an HTTP request to the proxy for registration
                endpoint = f"{self.config.proxy_url}/v1/clusters/{self.config.uuid}/register"
                payload = {
                    "url": self.config.grpc_server_url # Us
                }

                response = requests.post(endpoint, json=payload, timeout=100)
                if response.status_code == 200:
                    logging.info(f"Successfully registered cluster with proxy at {endpoint}!")
                    self.status = OperatorStatus.CONNECTED
                
                    return
                elif response.status_code == 503:
                    logging.error(f"Network error: proxy server was unable to find our URL {self.config.grpc_server_url} in the network")
                else:
                    logging.error(f"Error response from proxy, status code: {response.status_code}, response: {response.content}")

            except Exception as e:
                retry_counter += 1
                if retry_counter % 10 == 0:  # Log every 10th retry attempt
                    logging.warning(f"Exception occurred during cluster registration after {retry_counter} attempts: {str(e)}")
                    
            # Give some time to the proxy to not flood the network
            time.sleep(1)
    
    def _cluster_deployments_thread(self):
        """
        Runs a periodic check for new deployments on the proxy for this cluster, and if there are any detected
        and they differ from the current deployment, it will delete the current deployment, and apply the new one.
        """
        logging.info("Started cluster deployment monitor thread")
        while True:
            # First we ensure we are connected to the proxy
            if self.status != OperatorStatus.CONNECTED:
                time.sleep(5)  
                continue  # Skip trying to register if not connected to proxy
                    
            error = self.__fetch_current_deployment()
            if error:
                self.status = OperatorStatus.ERRORED
                self.error = error
            
            time.sleep(5)  # Periodic delay between checks
    
    def __fetch_current_deployment(self) -> str:
        # Fetch basic cluster information to get the current deployment name
        url = f"{self.config.proxy_url}/v1/cluster/{self.config.uuid}"
        response = requests.get(url)
        if response.status_code != 200:
            return f"Could not fetch the cluster information from proxy at {self.config.proxy_url}, status code: {response.status_code}, response: {json_response}"
        
        # Check and parse the response
        try:
            json_response = response.json()
        except requests.exceptions.JSONDecodeError:
            return f"Error: Invalid response from server: {response.status_code}"

        # Extract the current deployment file name from the path
        current_deployment_path = json_response.get('current_deployment')
        if not current_deployment_path:
            return f"Invalid server response for {url}: field 'current_deployment' was not present"

        current_deployment_name = os.path.basename(current_deployment_path)
        if not current_deployment_name:
            return f"No valid deployment file name found in the current_deployment path."

        # First time we fetch the deployment we assign it to the objects deployment name
        if self.deployment_info.name == "":
            self.deployment_info.name = current_deployment_name
        else:
            if self.deployment_info.name == current_deployment_name:
                # No new deployments were detected for this cluster
                return ""
            else:
                logging.debug(f"New deployment detected: {current_deployment_name}, updating over: {self.deployment_info.name}")
                self.deployment_info.name = current_deployment_name
            
        # We have an update, delete all deployments and install the latest deployment
        error = self.__delete_k8s_deployments()
        if error:
            return f"Could not delete deployments in cluster before updating to new deployment: {error}"

        # Fetch the latest Kubernetes deployment from the proxy
        logging.info(f"Fetching deployment: {current_deployment_name} from proxy")
        url = f"{self.config.proxy_url}/v1/cluster/{self.config.uuid}/deployment/{current_deployment_name}"
        response = requests.get(url)
        if response.status_code != 200:
            return f"Could not fetch the cluster deployment from proxy at {self.config.proxy_url}, status code: {response.status_code}, response: {response.json()}"

        # Extract the deployment file content from the response
        try:
            deployment_info = response.json()
            deployment_file_contents = deployment_info['deployment_file_contents']
            deployment_file_path = f"/var/lib/deployments/{current_deployment_name}"

            # Save the deployment file contents to the filesystem
            os.makedirs(os.path.dirname(deployment_file_path), exist_ok=True)
            with open(deployment_file_path, 'w') as f:
                f.write(deployment_file_contents)
            
            self.deployment_path = deployment_file_path

            logging.info(f"Successfully saved deployment file: {deployment_file_path}")

            # Download all the images from the deployment
            logging.info(f"Fetching images in deployment {current_deployment_name} from registries")
            error = self.__download_and_update_deployment_images()
            if error:
                return f"Could not fetch all the deployment images: {error}"

            # Install the new deployment
            error = self.__apply_k8s_deployment()
            if error:
                return f"Could not apply new deployment to cluster: {error}"

            # Await for all the pods to be ready
            error = self.__wait_for_deployment_pods_ready()
            if error:
                return f"Failed to apply kubernetes deployment to cluster: {error}"
            
            # Update the state 

            logging.info("Deployments is running and ready")
            return ""
    
        except KeyError:
            return f"Deployment file contents not found in the response for {url}"
        except requests.exceptions.JSONDecodeError:
            return f"Error: Invalid deployment response from server: {response.status_code}"

    def __download_and_update_deployment_images(self) -> str:
        """
        Searches through a Kubernetes deployment for any images present, downloads them from
        that registry to the registry of the cluster, and once all images have been successfully
        downloaded, it will rename them so that the runners inside the network can download them
        without internet access. It also updates the image names in the deployment file.
        """

        # Read the deployment file content
        deployment_path = self.deployment_path
        try:
            with open(deployment_path, 'r') as file:
                deployment_content = file.read()
        except FileNotFoundError:
            return f"Deployment file '{deployment_path}' not found"

        # Parse the deployment as YAML
        try:
            deployment_yaml = yaml.safe_load(deployment_content)
        except yaml.YAMLError as e:
            return f"Error parsing deployment file: {e}"

        # Find and process all container images in the deployment
        try:
            containers = deployment_yaml['spec']['template']['spec']['containers']
        except KeyError as e:
            return f"Error extracting containers from deployment: {e}"

        image_updates = {}
        for container in containers:
            original_image = container['image']
            image_name = os.path.basename(urlparse(original_image).path)
            new_image_name = f"control-plane:{self.config.registry_port}/{image_name}" #TODO: Change to local registry
            image_updates[original_image] = new_image_name

            logging.info(f"Fetching image {original_image}...")

            # Pull and tag new images
            try:
                local_image = self.docker_client.images.pull(original_image)
                local_image.tag(new_image_name)
                self.docker_client.images.push(new_image_name)
                logging.info(f"Image {original_image} downloaded and tagged as {new_image_name}")
            except docker.errors.APIError as e:
                return f"Failed to download or tag image {original_image}: {e}"
            except docker.errors.NotFound:
                return f"Image {original_image} not found in the registry"

        # Update the image names in the deployment manifest
        for container in containers:
            original_image = container['image']
            container['image'] = image_updates[original_image]

        # Save the updated deployment back to the filesystem
        try:
            with open(deployment_path, 'w') as file:
                yaml.safe_dump(deployment_yaml, file)
            logging.info(f"Updated deployment file saved successfully: {deployment_path}")
        except IOError as e:
            return f"Failed to save updated deployment file: {e}"

        return ""
        
    def __apply_k8s_deployment(self) -> str:
        """Applies a specific Kubernetes deployment to the cluster and waits for the pods to be ready."""
        logging.info(f"Applying Kubernetes deployment from: {self.deployment_path}")

        try:
            with open(self.deployment_path, 'r') as file:
                deployment_yaml = yaml.safe_load(file)
            
            k8s_client = kubernetes.client.ApiClient()
            kubernetes.utils.create_from_yaml(k8s_client, yaml_objects=[deployment_yaml], namespace="default")
            
            self.deployment_name = deployment_yaml.get("metadata", {}).get("name", "")
            if not self.deployment_name:
                return "Deployment name could not be extracted from the YAML file."
            
            return ""
            
        except Exception as e:
            return f"Failed to apply deployment from {self.deployment_path}: {str(e)}"
           
    def __wait_for_deployment_pods_ready(self) -> str:
        """Waits for all pods in a deployment to be in the 'Ready' state and reports any errors."""

        timeout:int = self.K8S_APPLY_DEPLOYMENT_TIMEOUT_S

        apps_v1 = kubernetes.client.AppsV1Api()
        core_v1 = kubernetes.client.CoreV1Api()
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            try:
                deployment = apps_v1.read_namespaced_deployment(name=self.deployment_name, namespace=self.deployment_namespace)
                if deployment.status.ready_replicas == deployment.spec.replicas:
                    logging.info(f"All pods for deployment {self.deployment_name} are ready.")
                    return ""
            except kubernetes.client.exceptions.ApiException as e:
                return f"Error fetching deployment {self.deployment_name}: {str(e)}"

            pod_list = core_v1.list_namespaced_pod(namespace=self.deployment_namespace, label_selector=f"app={self.deployment_name}")
            for pod in pod_list.items:
                if pod.status.phase == "Pending":
                    field_selector = f"involvedObject.name={pod.metadata.name},involvedObject.namespace={self.deployment_namespace}"
                    events = core_v1.list_namespaced_event(namespace=self.deployment_namespace, field_selector=field_selector)
                    for event in events.items:
                        logging.debug(f"Event for {pod.metadata.name}: {event.message}")
                        if "Failed" in event.reason:
                            error_details = f"{event.reason}: {event.message}"
                            return error_details

            time.sleep(1)  # Sleep before the next check to avoid overwhelming the API server

        return "Timeout reached. Not all pods are ready."
            