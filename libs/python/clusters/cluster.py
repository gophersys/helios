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
    # Runner config
    RUNNNER_SERVER_PORT=12345               # Where the runner service is being served at

    # Timeouts
    HOST_STARTUP_TIMEOUT_S=120              # Linux kernel up and running
    K8S_AWAIT_NODES_TIMEOUT_S=120           # Docker & k8s
    K8S_DELETE_DEPLOYMENT_TIMEOUT_S=120     # Delete deployment
    K8S_APPLY_DEPLOYMENT_TIMEOUT_S=240      # Apply deployment, a new image could take a while!

    def __init__(self, uuid:str, config:TestClusterConfig):
        """Instantiates a new test cluster instance with the desired configuration."""
        
        self.uuid:str = uuid
        self.config:TestClusterConfig = config
        self.runners:List[TestClusterRunner] = []

        self.deployment_namespace = "default"   
        self.docker_client = docker.from_env()
        self.deployment_path:str = ""
        self.k8s_config_set:bool = False
        logger = logging.getLogger('kubernetes')
        logger.setLevel(logging.INFO)
        logger = logging.getLogger('docker')
        logger.setLevel(logging.INFO)

    def setup(self, kubeconfig_path:str) -> Tuple[bool, str]:
        """Tries to initialize the cluster by following the same steps a human operator
           would follow when trying to recover and or setup the cluster"""
        
        self.kubeconfig_path:str = kubeconfig_path

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

        # Await for Kubernetes to be fully setup on all the runners
        success, err = self.__await_for_k8s_nodes()
        if not success:
            return False, f"Kubernetes nodes failed to initialize: {err}. Are all the servers "
        
        logging.info("All nodes are ready. Proceeding to delete all deployments...")
        
        # Wipe everything ont the cluster, and start fresh every time, with the latest deployment
        success, err = self.__delete_k8s_deployments()
        if not success:
            return False, f"Failed to delete kubernetes deployment: {err}"
        
        logging.info("Deployments deleted. Proceeding to apply latest deployment...")

        # Fetch the latest deployment from the network
        error = self.__fetch_current_deployment()
        if error:
            return False, f"Failed to fetch kubernetes deployment from the proxy: {error}"

        # Apply the latest deployment to the cluster
        success, err = self.__apply_k8s_deployment()
        if not success:
            return False, f"Failed to apply kubernetes deployment to cluster: {err}"

        # Await for all the pods to be ready
        success, err = self.__wait_for_deployment_pods_ready()
        if not success:
            return False, f"Failed to apply kubernetes deployment to cluster: {err}"

        logging.info("Deployments is running and ready. Proceeding to connect to runners...")

        # Allow for some time for the servers to be up
        time.sleep(10)

        # Connect to all the runners service over gRPC
        success, err = self.__connect_to_runners()
        if not success:
            return False, f"Failed to apply kubernetes deployment to cluster: {err}"

        logging.info("Sigma 5 test cluster was setup correctly")
        return True, ""

    def update(self) -> str:
        return ""

    def get_cluster_info(self) -> ClusterInfo:
        runners_info:List[RunnerInfo] = []
        for runner in self.runners:
            runners_info.append(runner.info)
    
        return ClusterInfo(
            name = "My test cluster",
            runners=runners_info,
        )

    def __await_for_hosts_ping(self) -> Tuple[bool, str]:
        logging.info("Attempting to ping all hosts in the runners list...")

        start_time = time.time()
        timeout = self.HOST_STARTUP_TIMEOUT_S
        unreachable_runners = self.config.runners_info.copy()

        # Function to ping a single host
        def ping_host(runner):
            target = runner.hostname
            try:
                response = subprocess.run(["ping", "-c", "1", "-W", "1", target], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                if response.returncode == 0:
                    logging.debug(f"Successfully pinged {target}.")
                    unreachable_runners.remove(runner)
                else:
                    logging.debug(f"Host {target} not yet reachable.")
            except Exception as e:
                logging.warning(f"Error occurred pinging host {target}: {str(e)}")

        # Thread list
        threads = []

        # Keep pinging until all hosts are reachable or timeout occurs
        while time.time() - start_time < timeout and unreachable_runners:
            for runner in unreachable_runners[:]:
                thread = threading.Thread(target=ping_host, args=(runner,))
                threads.append(thread)
                thread.start()

            # Wait for all threads to complete
            for thread in threads:
                thread.join(timeout=(timeout - (time.time() - start_time)))

            time.sleep(0.2)  # Sleep to prevent too many rapid pings

        if not unreachable_runners:
            return True, ""
        else:
            unreachable_hosts = ', '.join([runner.hostname for runner in unreachable_runners])
            return False, f"Timeout reached. Could not verify hosts: {unreachable_hosts}"


    def __await_for_k8s_nodes(self) -> Tuple[bool, str]:
        """Awaits for the Kubernetes nodes in the cluster to all be in the Ready state."""

        timeout:int = self.K8S_AWAIT_NODES_TIMEOUT_S
        
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
    
    def __delete_k8s_deployments(self) -> Tuple[bool, str]:
        """Deletes all Kubernetes deployments in the default namespace and waits for their pods to be terminated."""
        logging.info("Deleting all Kubernetes deployments in the default namespace.")

        timeout:int = self.K8S_DELETE_DEPLOYMENT_TIMEOUT_S

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

    def __fetch_current_deployment(self) -> str:
        # Fetching cluster info from proxy
        logging.info(f"Fetching cluster {self.uuid} from proxy at {self.config.proxy_url}")

        # Fetch basic cluster information to get the current deployment name
        url = f"{self.config.proxy_url}/v1/cluster/{self.uuid}"
        response = requests.get(url)
        
        # Check and parse the response
        try:
            json_response = response.json()
            if response.status_code != 200:
                return f"Could not fetch the cluster information from proxy at {self.config.proxy_url}, status code: {response.status_code}, response: {json_response}"
        except requests.exceptions.JSONDecodeError:
            return f"Error: Invalid response from server: {response.status_code}"

        # Extract the current deployment file name from the path
        current_deployment_path = json_response.get('current_deployment')
        if not current_deployment_path:
            return f"Invalid server response for {url}: field 'current_deployment' was not present"

        current_deployment_name = os.path.basename(current_deployment_path)
        if not current_deployment_name:
            return f"No valid deployment file name found in the current_deployment path."

        # Fetch the latest Kubernetes deployment from the proxy
        logging.info(f"Fetching deployment: {current_deployment_name} from proxy")
        url = f"{self.config.proxy_url}/v1/cluster/{self.uuid}/deployment/{current_deployment_name}"
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

            # Download all the images from the deployment
            logging.info(f"Fetching images in deployment {current_deployment_name} from registries")
            error = self.__download_and_update_deployment_images()
            if error:
                return f"Could not fetch all the deployment images: {error}"
            
            logging.info(f"Successfully saved deployment file: {deployment_file_path}")
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
            new_image_name = f"{self.config.registry_url}/{image_name}"
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
        
    def __apply_k8s_deployment(self) -> Tuple[bool, str]:
        """Applies a specific Kubernetes deployment to the cluster and waits for the pods to be ready."""
        logging.info(f"Applying Kubernetes deployment from: {self.deployment_path}")

        try:
            with open(self.deployment_path, 'r') as file:
                deployment_yaml = yaml.safe_load(file)
            
            k8s_client = client.ApiClient()
            utils.create_from_yaml(k8s_client, yaml_objects=[deployment_yaml], namespace="default")
            
            self.deployment_name = deployment_yaml.get("metadata", {}).get("name", "")
            if not self.deployment_name:
                return False, "Deployment name could not be extracted from the YAML file."

            logging.info("Deployment applied successfully. Waiting for pods to become ready.")
            
            return True, ""
            
        except Exception as e:
            return False, f"Failed to apply deployment from {self.deployment_path}: {str(e)}"

    def __wait_for_deployment_pods_ready(self) -> Tuple[bool, str]:
        """Waits for all pods in a deployment to be in the 'Ready' state and reports any errors."""

        timeout:int = self.K8S_APPLY_DEPLOYMENT_TIMEOUT_S

        apps_v1 = client.AppsV1Api()
        core_v1 = client.CoreV1Api()
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            try:
                deployment = apps_v1.read_namespaced_deployment(name=self.deployment_name, namespace=self.deployment_namespace)
                if deployment.status.ready_replicas == deployment.spec.replicas:
                    logging.info(f"All pods for deployment {self.deployment_name} are ready.")
                    return True, ""
            except client.exceptions.ApiException as e:
                return False, f"Error fetching deployment {self.deployment_name}: {str(e)}"

            pod_list = core_v1.list_namespaced_pod(namespace=self.deployment_namespace, label_selector=f"app={self.deployment_name}")
            for pod in pod_list.items:
                if pod.status.phase == "Pending":
                    field_selector = f"involvedObject.name={pod.metadata.name},involvedObject.namespace={self.deployment_namespace}"
                    events = core_v1.list_namespaced_event(namespace=self.deployment_namespace, field_selector=field_selector)
                    for event in events.items:
                        logging.debug(f"Event for {pod.metadata.name}: {event.message}")
                        if "Failed" in event.reason:
                            error_details = f"{event.reason}: {event.message}"
                            return False, error_details

            time.sleep(1)  # Sleep before the next check to avoid overwhelming the API server

        return False, "Timeout reached. Not all pods are ready."

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