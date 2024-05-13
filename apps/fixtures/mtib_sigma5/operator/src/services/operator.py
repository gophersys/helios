import logging
import grpc
import uuid
import time
import socket
import threading
from typing import Tuple, Any, List, Optional, Callable
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
    TestInfo, HealthCheckRequest, HealthCheckResponse,
    ExecuteRequest,TestStepResult
)
from protos.cluster_test.cluster_test_pb2_grpc import ClusterTestStub

from protos.cluster_operator.cluster_operator_pb2 import (
    ClusterStatus, NodeInfo, PodInfo, DeploymentInfo
)

# -------------------------------------------------------------------------------------------------
#                                                                                       Deployments
# -----------------------------------------------------------------------------------------------*/
class ClusterDeploymentStatus(Enum):
    NO_DEPLOYMENT = 1
    DEPLOYMENT_ACTIVE = 2

class ClusterDeploymentInfo:
    def __init__(self,
                uuid:str = "",
                path:str = "",
                status:ClusterDeploymentStatus = ClusterDeploymentStatus.NO_DEPLOYMENT):
        self.uuid:str = uuid
        self.path:str = path
        self.status:ClusterDeploymentStatus = status

# ----------------------------------------------------------------------------------
#                                                                         Test Entry
# --------------------------------------------------------------------------------*/
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

TestResultsCallbackType = Callable[[Optional[List[TestStepResult]]],None]

# ----------------------------------------------------------------------------------
#                                                                      Configuration
# --------------------------------------------------------------------------------*/
class ClusterOperatorConfig:
    def __init__(self,
                 uuid:str,
                 proxy_url:str,
                 registry_host:str,
                 registry_port:int,
                 grpc_server_url:str,
                 nodes_hostnames:List[str],
                 kubeconfig_path:str,
                 deployments_path:str):
        self.uuid:str = uuid
        self.proxy_url:str = proxy_url
        self.registry_host:int = registry_host
        self.registry_port:int = registry_port
        self.grpc_server_url:str = grpc_server_url
        self.nodes_hostnames:List[str] = nodes_hostnames
        self.kubeconfig_path:str = kubeconfig_path
        self.deployments_path:str = deployments_path
        
# ----------------------------------------------------------------------------------
#                                                                         Main Class
# --------------------------------------------------------------------------------*/
class ClusterOperator:
    # Timeouts
    HOST_STARTUP_TIMEOUT_S=120              # Linux kernel up and running
    K8S_AWAIT_NODES_TIMEOUT_S=120           # Docker & k8s
    K8S_DELETE_DEPLOYMENT_TIMEOUT_S=120     # Delete deployment
    K8S_APPLY_DEPLOYMENT_TIMEOUT_S=240      # Apply deployment, a new image could take a while!
    PROXY_REGISTRATION_RETRY_TIMEOUT_S=5    # How often to retry registering ourselves with the cluster
    
    # -----------------------------------------------------------------------------
    #                                                                          Init
    #  --------------------------------------------------------------------------*/
    def __init__(self, ):
        self.initialized = False
        self.config:ClusterOperatorConfig = None
        self.error:str = ""
        self.status:ClusterStatus = None
        
        # Flag to manage our connection to the proxy
        self.proxy_connected:bool = False
        
        # Docker info
        logger = logging.getLogger('docker')
        logger.setLevel(logging.INFO)
        self.docker_client:docker.DockerClient = None

        # Kubernetes info
        logger = logging.getLogger('kubernetes')
        logger.setLevel(logging.INFO)
        self.kubernetes_client:kubernetes.client 
        self.deployment_namespace = "default"  
        self.deployment_info:ClusterDeploymentInfo = ClusterDeploymentInfo()

        # Tests 
        self.tests:List[ClusterOperatorTestEntry] = []
    
    def init(self, config:ClusterOperatorConfig) -> str:
        if self.initialized:
            return "Do not initialize class again."
        
        self.config = config
        self.status = ClusterStatus.STARTING
        
        self.docker_client:docker.DockerClient = docker.from_env()
        self.kubernetes_client:kubernetes.client = kubernetes.client
        
        # Ensure the deployments directory exists
        if not os.path.exists(self.config.deployments_path):
            os.makedirs(self.config.deployments_path)
            
        # We return immediately on initialize so that if any errors occur during setup
        # the proxy is able to see it
        self._main_thread_handle = threading.Thread(target=self._main_thread, daemon=True)
        self._main_thread_handle.start()
        
        # We attempt to register so that proxy has immediate visibility of us
        self._proxy_thread_handle = threading.Thread(target=self._proxy_management_thread, daemon=True)
        self._proxy_thread_handle.start()
        
        # Simple health check to keep tracks of what tests are active
        self._tests_thread_handle = threading.Thread(target=self._tests_management_thread, daemon=True)
        self._tests_thread_handle.start()
        
        return ""
    
    # -----------------------------------------------------------------------------
    #                                                                       Restart
    #  --------------------------------------------------------------------------*/
    def restart(self) -> str:
        pass
    
    # -----------------------------------------------------------------------------
    #                                                                          Stop
    #  --------------------------------------------------------------------------*/
    def stop(self):
        self._main_thread_handle.join(timeout=1)
        self._proxy_thread_handle.join(timeout=1)
        self._tests_thread_handle.join(timeout=1)
    
    def get_status(self) -> Tuple[Any, str]:
        return self.status, self.error
    
    def get_nodes_info(self) -> list:
        """Fetches node information from the Kubernetes cluster and returns a list of NodeInfo."""
        
        # Initialize the Kubernetes client
        api = self.kubernetes_client.CoreV1Api()

        # List all nodes in the cluster
        node_list = api.list_node()
        nodes_info = []

        # Iterate over each node to extract relevant information
        for node in node_list.items:
            # Extract and parse memory and storage details
            memory_capacity_bytes = self._parse_node_mem_capacity(node.status.capacity['memory'])
            storage_capacity_bytes = self._parse_node_mem_capacity(node.status.capacity['ephemeral-storage'])
            memory_used_bytes = memory_capacity_bytes - self._parse_node_mem_capacity(node.status.allocatable['memory'])
            storage_used_bytes = storage_capacity_bytes - self._parse_node_mem_capacity(node.status.allocatable['ephemeral-storage'])

            node_info = {
                "name": node.metadata.name,
                "host": next((addr.address for addr in node.status.addresses if addr.type == "Hostname"), None),
                "os_image": node.status.node_info.os_image,
                "kernel_version": node.status.node_info.kernel_version,
                "cpu_cores": int(node.status.capacity["cpu"].replace('m', '')),  # CPU capacity is assumed to be in millicores
                "memory_used_bytes": memory_used_bytes,
                "memory_capacity_bytes": memory_capacity_bytes,
                "storage_used_bytes": storage_used_bytes,
                "storage_capacity_bytes": storage_capacity_bytes,
            }
            nodes_info.append(node_info)

        return nodes_info
    
    def get_deployment_info(self) -> List[DeploymentInfo]:
        """Fetches deployment information from the Kubernetes cluster."""
        
        apps_v1 = self.kubernetes_client.AppsV1Api()
        core_v1 = self.kubernetes_client.CoreV1Api()
        
        try:
            deployments = apps_v1.list_namespaced_deployment(namespace="default")
            deployment_infos = []

            for deployment in deployments.items:
                pods_info = self.__get_pods_info(deployment.metadata.name, deployment.metadata.namespace)
                deployment_info = DeploymentInfo(
                    name=deployment.metadata.name,
                    uuid=deployment.metadata.uid,
                    pods_info=pods_info
                )
                deployment_infos.append(deployment_info)

            return deployment_infos
        except kubernetes.client.rest.ApiException as e:
            logging.error(f"An error occurred while fetching deployments: {e}")
            return []

    def __get_pods_info(self, deployment_name: str, namespace: str) -> List[PodInfo]:
        """Helper method to fetch pod information for a given deployment."""
        core_v1_api = kubernetes.client.CoreV1Api()
        
        try:
            # Get deployment to fetch its unique selector
            apps_v1_api = kubernetes.client.AppsV1Api()
            deployment = apps_v1_api.read_namespaced_deployment(deployment_name, namespace)
            match_labels = deployment.spec.selector.match_labels
            label_selector = ','.join(f"{k}={v}" for k, v in match_labels.items())
            
            # Now use the specific selector tied to the deployment's own specification
            pods = core_v1_api.list_namespaced_pod(namespace, label_selector=label_selector)
            pods_info = []

            for pod in pods.items:
                container_statuses = pod.status.container_statuses or []
                pod_info = PodInfo(
                    name=pod.metadata.name,
                    image=[container.image for container in pod.spec.containers][0] if pod.spec.containers else None,
                    node=pod.spec.node_name,
                    status=pod.status.phase,
                    restarts=sum(cs.restart_count for cs in container_statuses),
                    ready=all(cs.ready for cs in container_statuses)
                )
                pods_info.append(pod_info)

        except kubernetes.client.exceptions.ApiException as e:
            logging.error(f"API error retrieving pods for deployment {deployment_name}: {e}")
            return []
        except Exception as e:
            logging.error(f"Unexpected error in retrieving pods: {e}")
            return []

        return pods_info
    
    def _parse_node_mem_capacity(self, value):
        """Parse capacity string with units to bytes."""
        if value.endswith('Ki'):
            return int(value.replace('Ki', '')) * 1024
        elif value.endswith('Mi'):
            return int(value.replace('Mi', '')) * 1024**2
        elif value.endswith('Gi'):
            return int(value.replace('Gi', '')) * 1024**3
        elif value.endswith('Ti'):
            return int(value.replace('Ti', '')) * 1024**4
        elif value.endswith('Pi'):
            return int(value.replace('Pi', '')) * 1024**5
        else:
            return int(value)  # Assume the value is in bytes if no unit suffix is present

    # -----------------------------------------------------------------------------
    #                                                                         Tests
    #  --------------------------------------------------------------------------*/
    def register_test(self, port:int, info:TestInfo) -> str:
        # Make sure that a test isn't trying to register on a same port
        for test in self.tests:
            if test.port == port:
                return f"Operator already has test \"{test.info.name}\" registered at port {port}"
            
        # Build the test URL
        test_url = f"localhost:{port}"  #TODO: Change back to localhost once the operator is running inside the same machine
        
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
    
    def get_test_entry(self, test_uuid:str) -> ClusterOperatorTestEntry:
        # Find the test in our list
        for t in self.tests:
            if t.info.uuid == test_uuid:
                return t
            
    def execute_test(self, test_uuid:str, test_config:str, test_nodes:List[str], results_cb:TestResultsCallbackType) -> str:
        # Ensure we aren't running a test
        if self.status is ClusterStatus.RUNNING:
            return f"Cannot execute a new test while cluster is in the RUNNING state"
        
        self.status = ClusterStatus.RUNNING
        
        # Find the test in our list
        test:ClusterOperatorTestEntry = None
        for t in self.tests:
            if t.info.uuid == test_uuid:
                test = t
                break
        
        if test is None:
            return f"Test {test_uuid} is not registered with operator"
        
        # Call the test in a new thread, and send the responses back to the main RPC
        request = ExecuteRequest(
            config=test_config,
            nodes=test_nodes
        )
        
        finished_event = threading.Event()
            
        def handle_test_execution():
            try:
                for response in test.stub.Execute(request):
                    logging.warning(f"Thread response: {response}")
                    results_cb(response.results)

            except grpc.RpcError as e:
                logging.error(f"Error calling Execute on test {test_uuid}: {str(e)}")
                self.status = ClusterStatus.ERROR  # Set status to ERROR on RPC error
                results_cb(None)  # Signal the callback that an error occurred
            
            finally:
                self.status = ClusterStatus.IDLE
                results_cb(None)  # Signal the end of the test to the callback
                finished_event.set()  # Signal that the test is complete
                
        test_thread = threading.Thread(target=handle_test_execution)
        test_thread.start()
        
        finished_event.wait()
        
        return ""
    
    def list_tests(self) -> List[TestInfo]:
        tests_info:List[TestInfo] = []
        for test in self.tests:
            tests_info.append(test.info)
            
        return tests_info
    
    # -----------------------------------------------------------------------------
    #                                                                         Setup
    #  --------------------------------------------------------------------------*/
    def _setup(self) -> str:
         # Check that the k8s deployment passed is valid
        try:
            kubernetes.config.load_kube_config(self.config.kubeconfig_path)
        except kubernetes.config.ConfigException as e:
            return f"Could not load kubernetes configuration: {e}"
        
        # Create a local registry for deployment images
        error = self.__setup_local_container_registry()
        if error:
            return f"Could not setup local container registry: {error}"
        
        # Await for all the nodes in this cluster to be ready
        error = self.__await_for_cluster_readiness()
        if error:
            return f"Cluster was not ready before timeout: {error}"
            
        return ""
    
    def __setup_local_container_registry(self) -> str:
        # logging.debug(f"Setting up local registry at port {self.config.registry_port}...")
        # client = docker.from_env()

        # try:
        #     # Check if a registry is running on that port
        #     all_containers = client.containers.list(all=True)
        #     registry_running = False
        #     for container in all_containers:
        #         container_ports = container.attrs['HostConfig']['PortBindings'] or {}
        #         for port, bindings in container_ports.items():
        #             if port.split('/')[0] == str(self.config.registry_port) and bindings:
        #                 registry_running = True
        #                 break

        #     if not registry_running:
        #         logging.info("No local registry found. Creating one...")
        #         client.containers.run("registry:2", ports={f'{self.config.registry_port}/tcp': self.config.registry_port}, detach=True)
        #     else:
        #         logging.info("Local registry already running.")

        # except docker.errors.APIError as e:
        #     error_message = f"Failed to check or create local registry: {str(e)}"
        #     logging.error(error_message)
        #     return error_message

        logging.info(f"Local registry at port {self.config.registry_port} setup OK")
        return ""
    
    def __await_for_cluster_readiness(self) -> str:
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
        
        v1 = self.kubernetes_client.CoreV1Api()
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

        apps_v1 = self.kubernetes_client.AppsV1Api()
        core_v1 = self.kubernetes_client.CoreV1Api()

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
        
    # -----------------------------------------------------------------------------
    #                                                                   Main Thread
    #  --------------------------------------------------------------------------*/
    def _main_thread(self):  
        # Setup
        error = self._setup()
        if error:
            logging.error(error)
            self.error = f"Cluster setup error: {error}"
            self.status = ClusterStatus.ERRORED
            return 
        
        # Cluster is now ready for work
        self.status = ClusterStatus.READY
        
        while True:
            # We only NOT fetch updates if there's a test running
            if self.status is not ClusterStatus.RUNNING and self.proxy_connected:
                error = self.__fetch_current_deployment()
                if error:
                    logging.error(error)
                    self.error = error
                    self.status = ClusterStatus.ERRORED         
            
            time.sleep(1)
            
    # -----------------------------------------------------------------------------
    #                                                       Proxy Management Thread
    #  --------------------------------------------------------------------------*/
    def _proxy_management_thread(self):
        retry_counter:int = 0

        while True:
            # Wait some time as to not flood the network or put unwanted load on the proxy
            time.sleep(1)
            
            # If we are not connected to the proxy, our only job here is to await for a connection
            if not self.proxy_connected:
                try:
                    # Do an HTTP request to the proxy for registration
                    endpoint = f"{self.config.proxy_url}/v1/clusters/{self.config.uuid}/register"
                    payload = {
                        "url": self.config.grpc_server_url # Us
                    }

                    response = requests.post(endpoint, json=payload, timeout=100)
                    if response.status_code == 200:
                        logging.info(f"Successfully registered cluster with proxy at {endpoint}")
                        self.proxy_connected = True
                
                    elif response.status_code == 503:
                        logging.error(f"Network error: proxy server was unable to find our URL {self.config.grpc_server_url} in the network")
                    else:
                        logging.error(f"Error response from proxy, status code: {response.status_code}, response: {response.content}")

                except Exception as e:
                    retry_counter += 1
                    if retry_counter % 10 == 0:  # Log every 10th retry attempt
                        logging.warning(f"Exception occurred during cluster registration after {retry_counter} attempts: {str(e)}")
            
            # If we are connected to the proxy, then we keep doing health checks periodically    
            else:
                try:
                    # Do an HTTP request to the proxy for registration
                    endpoint = f"{self.config.proxy_url}/v1/healthcheck"

                    response = requests.get(endpoint, timeout=1)
                    if response.status_code != 200:
                        self.proxy_connected = False
                        logging.error(f"Proxy healthcheck failed. Is the proxy down? Status code for GET {endpoint}: {response.status_code}")

                except Exception as e:
                    self.proxy_connected = False
                    logging.warning(f"Network error: could not GET healthcheck in proxy server {str(e)}")
    
    # -----------------------------------------------------------------------------
    #                                                             Tests Healthcheck
    #  --------------------------------------------------------------------------*/
    def _tests_management_thread(self):
        """Periodically check the health of each cluster."""
        while True:
            for test in list(self.tests):
                try:
                    # Perform a periodic health check to ensure we're still connected and alive
                    test.stub.HealthCheck(HealthCheckRequest())
                    
                except grpc.RpcError as e:
                    logging.error(f"Failed to perform health check on test at {test.port}. Unregistering from operator")
                    test.channel.close()
                    self.tests.remove(test)

            time.sleep(1) 
    
    # -----------------------------------------------------------------------------
    #                                                            Deployment Helpers
    #  --------------------------------------------------------------------------*/
    def __fetch_current_deployment(self) -> str:
        # Try to fetch the latest deployment info from the proxy
        try:
            # Fetch basic cluster information to get the current deployment name
            url = f"{self.config.proxy_url}/v1/clusters/{self.config.uuid}/deployments"
            response = requests.get(url)
            if response.status_code != 200:
                return f"Could not fetch the cluster information from proxy at {self.config.proxy_url}, status code: {response.status_code}, response: {json_response}"
            
            # Check and parse the response
            try:
                json_response = response.json()
            except requests.exceptions.JSONDecodeError:
                return f"Error: Invalid response from server: {response.status_code}"
        except Exception as e:
            logging.warning(f"Exception occurred fetching deployment: {str(e)}")
                        
        # Extract the current deployment file name from the path
        new_deployment_uuid = json_response.get('current_deployment')
        if new_deployment_uuid is None:
            if self.deployment_info.uuid is None:    
                return "" # No deployment is currently set for this cluster, skip
            else:
                self.deployment_info.uuid = None
                
                # User deleted this deployment
                error = self.__delete_k8s_deployments()
                if error:
                    return f"Could not delete deployment: {error}"
                
                # Update the status
                self.status = ClusterStatus.READY
                self.error = None
                
                # Clear all the tests we have
                self.tests.clear()
            
                logging.info("Deployment for cluster was deleted succesfully")
                return ""

        if new_deployment_uuid == self.deployment_info.uuid:
            return "" # Deployment hasn't changed

        # Set the status
        self.status = ClusterStatus.UPDATING
        self.error = None
        
        # First time we fetch the deployment we assign it to the objects deployment name
        if self.deployment_info.uuid is None:
            logging.info(f"Applying first cluster deployment: {new_deployment_uuid}")
        else:
            logging.info(f"New deployment detected: {new_deployment_uuid}, updating over: {self.deployment_info.uuid}")
            
        # We have an update, delete all deployments and install the latest deployment
        error = self.__delete_k8s_deployments()
        if error:
            return f"Could not delete deployments in cluster before updating to new deployment: {error}"

        # Set the operator info
        self.deployment_info.uuid = new_deployment_uuid
        
        # Extract the deployment file content from the response
        try:
            # Fetch the deployment file from your Flask route
            logging.info(f"Fetching deployment: {new_deployment_uuid} from proxy")
            url = f"{self.config.proxy_url}/v1/clusters/{self.config.uuid}/deployments/{new_deployment_uuid}"
            response = requests.get(url)
            if response.status_code != 200:
                return f"Could not fetch the cluster deployment from proxy at {self.config.proxy_url}, status code: {response.status_code}, response: {response.json()}"

            # Save the deployment file to the filesystem
            deployment_file_path = os.path.join(self.config.deployments_path, f"{new_deployment_uuid}.yaml")
            with open(deployment_file_path, 'wb') as f:
                f.write(response.content)
                
            self.deployment_info.path = deployment_file_path
            logging.info(f"Successfully saved deployment file: {deployment_file_path}")

            # Download all the images from the deployment
            logging.info(f"Fetching images in deployment {new_deployment_uuid} from registries")
            error = self.__download_and_update_deployment_images()
            if error:
                return f"Could not fetch all the deployment images: {error}"

            # Install the new deployment
            error = self.__apply_k8s_deployment()
            if error:
                return f"Could not apply new deployment to cluster: {error}"

            # Update the state 
            self.status = ClusterStatus.IDLE
            self.error = None
            logging.info("Deployments is running and ready")
            return ""
    
        except KeyError:
            return f"Deployment file contents not found in the response for {url}"
        except requests.exceptions.JSONDecodeError:
            return f"Error: Invalid deployment response from server: {response.status_code}"

    def _image_exists_and_matches(self, control_plane_image, original_image):
        """Check if the image exists in the control plane registry and matches the original image digest."""
        try:
            # Get the digest from the control plane registry
            control_plane_data = self.docker_client.images.get_registry_data(control_plane_image)
            control_plane_digest = control_plane_data.attrs['Descriptor']['digest']
            
            # Get the digest from the original image
            original_data = self.docker_client.images.get_registry_data(original_image)
            original_digest = original_data.attrs['Descriptor']['digest']
            
            matches = control_plane_digest == original_digest
            logging.info(f"Comparing digests for {control_plane_image} with {original_image}: match: {matches}")
            return matches
        except (docker.errors.ImageNotFound, docker.errors.NotFound):
            logging.info(f"Image {control_plane_image} not found in registry, fetching...")
            return False
        except Exception as e:
            logging.error(f"Error checking image in registry: {e}")
            return False

    def _retry_upload_image(self, image_name):
        """Attempt to upload the image to the registry, retrying if necessary."""
        retries = 3
        for attempt in range(1, retries + 1):
            try:
                self.docker_client.images.push(image_name)
                logging.info(f"Successfully uploaded image: {image_name}")
                return True
            except docker.errors.APIError as e:
                logging.info(f"Attempt {attempt} failed to upload image {image_name}: {e}")
                if attempt == retries:
                    return False

    def __download_and_update_deployment_images(self):
        deployment_path = self.deployment_info.path
        try:
            with open(deployment_path, 'r') as file:
                deployment_contents = file.read()
        except FileNotFoundError:
            return f"Deployment file '{deployment_path}' not found"

        try:
            documents = list(yaml.safe_load_all(deployment_contents))
        except yaml.YAMLError as e:
            return f"Error parsing deployment file: {e}"

        updated_documents = []  # To store the modified documents

        for deployment_yaml in documents:
            if not deployment_yaml:
                continue

            try:
                containers = deployment_yaml['spec']['template']['spec']['containers']
            except KeyError as e:
                return f"Error extracting containers from deployment: {e}"

            # Prepare a dictionary to track image updates
            image_updates = {}

            for container in containers:
                original_image = container['image']
                new_image_name = f"{self.config.registry_host}:{self.config.registry_port}/{os.path.basename(urlparse(original_image).path)}"

                logging.info(f"Checking image {original_image}...")

                # Check if the new image name exists and matches; if not, update and re-upload
                if not self._image_exists_and_matches(new_image_name, original_image):
                    logging.info(f"Pulling image {original_image}...")
                    local_image = self.docker_client.images.pull(original_image)
                    local_image.tag(new_image_name)
                    if self._retry_upload_image(new_image_name):
                        image_updates[original_image] = new_image_name  # Store the new image name
                        logging.info(f"Image pulled, retagged and uploaded succesuful for: {original_image} ({new_image_name})...")
                    else:
                        image_updates[original_image] = original_image  # Upload failed, keep the original
                else:
                    image_updates[original_image] = new_image_name  # Image already matches, use the new name

            # Update the image names in the deployment YAML
            for container in containers:
                original_image = container['image']
                container['image'] = image_updates.get(original_image, original_image)  # Ensure all images are updated

            updated_documents.append(deployment_yaml)  # Add the updated YAML to the list

        # Save the updated documents to the YAML file
        try:
            with open(deployment_path, 'w') as file:
                yaml.safe_dump_all(updated_documents, file)
            logging.info("Updated deployment file saved successfully.")
        except IOError as e:
            return f"Failed to save updated deployment file: {e}"

        return ""

    def __apply_k8s_deployment(self) -> str:
        """Applies Kubernetes deployments to the cluster and waits for the pods and images to be ready."""
        logging.info(f"Applying Kubernetes deployments from: {self.deployment_info.path}")

        # try:
        with open(self.deployment_info.path, 'r') as file:
            deployment_docs = list(yaml.safe_load_all(file))

        if not deployment_docs:
            return "No deployment found in the file."

        k8s_client = kubernetes.client.ApiClient()

        # Apply each deployment document
        applied_deployments = []
        for deployment_yaml in deployment_docs:
            if not deployment_yaml or 'kind' not in deployment_yaml or deployment_yaml['kind'] != 'Deployment':
                logging.warning("Skipping non-Deployment or malformed YAML document.")
                continue

            try:
                kubernetes.utils.create_from_yaml(k8s_client, yaml_objects=[deployment_yaml], namespace="default")
                deployment_name = deployment_yaml.get("metadata", {}).get("name", "")
                if deployment_name:
                    applied_deployments.append(deployment_name)
                else:
                    logging.warning("Deployment name could not be extracted from a YAML document.")
            except kubernetes.client.rest.ApiException as e:
                return f"Failed to apply deployment: {str(e)}"

        if not applied_deployments:
            return "No valid deployments were applied."

        # Wait for image downloads and pod readiness
        for deployment_name in applied_deployments:
            for _ in range(3):  # Retry logic
                error_message = self.__wait_for_deployment_images_ready(deployment_name)
                if not error_message:
                    break
                time.sleep(10)  # Wait a bit before retrying
            else:
                return f"Images for deployment '{deployment_name}' are not ready after retries."

            error_message = self.__wait_for_deployment_pods_ready(deployment_name)
            if error_message:
                return f"Failed to wait for deployment '{deployment_name}' to be ready: {error_message}"

        return ""

        # except Exception as e:
        #     return f"Failed to apply deployment from {self.deployment_info.path}: {str(e)}"

    def __wait_for_deployment_images_ready(self, deployment_name: str) -> str:
        """Wait for all images in the deployment to be ready."""
        core_v1 = self.kubernetes_client.CoreV1Api()
        retry_limit = 3
        attempt = 0

        while attempt < retry_limit:
            attempt += 1
            pod_list = core_v1.list_namespaced_pod(namespace="default", label_selector=f"app={deployment_name}")
            all_images_ready = True
            transitional_states = ["ContainerCreating", "Pending", "ImagePullBackOff", "ErrImagePull"]

            for pod in pod_list.items:
                if pod.status.container_statuses:
                    for container_status in pod.status.container_statuses:
                        if container_status.state.waiting and container_status.state.waiting.reason in transitional_states:
                            logging.info(f"Image for container {container_status.name} in pod {pod.metadata.name} is not ready. Reason: {container_status.state.waiting.reason}")
                            all_images_ready = False
                            break  # Break out of the container loop, check the next pod
                else:
                    logging.info(f"No container statuses available for pod {pod.metadata.name}. Waiting for update...")
                    all_images_ready = False  # Set this as False to ensure it retries

            if all_images_ready:
                logging.info(f"All images for deployment {deployment_name} are ready on attempt {attempt}.")
                return ""

            logging.info(f"Not all images are ready on attempt {attempt}. Retrying after delay...")
            time.sleep(10)  # Sleep to provide time for images to be ready

        return f"Not all images were ready after {retry_limit} attempts for deployment {deployment_name}."

    def __wait_for_deployment_pods_ready(self, deployment_name: str) -> str:
        """Waits for all pods in a specific deployment to be in the 'Ready' state, allowing for delays due to image downloads or other setup processes."""

        initial_check_delay = 5  # Seconds to delay before first readiness check
        post_check_delay = 5  # Seconds to wait after a successful readiness check to ensure stability

        time.sleep(initial_check_delay)  # Delay before starting the checks

        apps_v1 = self.kubernetes_client.AppsV1Api()
        core_v1 = self.kubernetes_client.CoreV1Api()

        try:
            # Get the deployment object to access the selector
            deployment = apps_v1.read_namespaced_deployment(name=deployment_name, namespace="default")
            selector = ','.join([f"{k}={v}" for k, v in deployment.spec.selector.match_labels.items()])
        except kubernetes.client.rest.ApiException as e:
            return f"Failed to get deployment {deployment_name}: {str(e)}"

        while True:
            # Fetch all pods using the deployment selector
            pod_list = core_v1.list_namespaced_pod(namespace="default", label_selector=selector)
            all_pods_ready = True
            transitional_states = ["ContainerCreating", "Pending"]
            error_message = ""

            for pod in pod_list.items:
                pod_status = self.__get_pod_status(pod)
                if pod_status == "Ready":
                    continue
                elif pod_status in transitional_states:
                    all_pods_ready = False
                    break  # Exit the current iteration and allow more time for transition
                else:
                    all_pods_ready = False
                    pod_in_error, logs = self.__find_error_pod_and_logs(core_v1, pod_list)
                    return f"Pods failed after initial readiness check. Error in pod {pod_in_error}: \n{logs}"

            if all_pods_ready:
                logging.info("Initial readiness check passed. Monitoring for stability...")
                time.sleep(post_check_delay)  # Wait to ensure pods remain stable

                # Recheck readiness after the delay
                if self.__are_all_pods_still_ready(core_v1, deployment_name, selector)[0]:
                    logging.info(f"All pods for deployment {deployment_name} are confirmed stable after monitoring.")
                    return ""
                else:
                    logging.info("Rechecking pods for stability after failure.")
                    pod_in_error, logs = self.__find_error_pod_and_logs(core_v1, pod_list)
                    return f"Pods failed after initial readiness check. Error in pod {pod_in_error}: {logs}"

            time.sleep(5)  # Sleep before the next check to avoid overwhelming the API server

    def __get_pod_status(self, pod):
        """Utility function to determine the current status of a pod."""
        if pod.status.conditions:
            return "Ready" if any(condition.type == "Ready" and condition.status == "True" for condition in pod.status.conditions) else "Not Ready"
        return "Unknown"

    def __are_all_pods_still_ready(self, core_v1, deployment_name, selector):
        """Checks if all pods are still in 'Ready' state."""
        pod_list = core_v1.list_namespaced_pod(namespace="default", label_selector=selector)
        return all(
            any(condition.type == "Ready" and condition.status == "True" for condition in pod.status.conditions)
            for pod in pod_list.items
        ), pod_list

    def __find_error_pod_and_logs(self, core_v1, pod_list):
        """Identifies which pod is in error state and fetches its logs if available."""
        for pod in pod_list.items:
            pod_status = self.__get_pod_status(pod)
            if pod_status not in ["Ready", "Running"]:  # Only attempt to fetch logs if pod is not in a running or ready state
                try:
                    if pod_status not in ["ContainerCreating", "Pending"]:  # Avoid fetching logs if the container isn't fully created yet
                        logs = core_v1.read_namespaced_pod_log(name=pod.metadata.name, namespace=pod.metadata.namespace)
                        return pod.metadata.name, logs
                    else:
                        return pod.metadata.name, f"Pod is still in {pod_status} state; logs not available yet."
                except kubernetes.client.exceptions.ApiException as e:
                    return pod.metadata.name, f"Failed to fetch logs: {e.status} {e.reason}"
        return "No error pod found", "No logs available"
        
    def __get_pod_error_details(self, pod, core_v1):
        """Extracts and returns error details from a pod's conditions, and fetches related events."""
        error_messages = [f"{condition.type} is not met: {condition.message}" for condition in pod.status.conditions if condition.status == "False"]
        events = core_v1.list_namespaced_event(namespace="default", field_selector=f"involvedObject.name={pod.metadata.name}")
        event_info = ' | '.join([f"{event.reason}: {event.message}" for event in events.items])

        error_details = ' | '.join(error_messages) if error_messages else "No specific error conditions found."
        return f"{error_details} | Events: {event_info}"







            