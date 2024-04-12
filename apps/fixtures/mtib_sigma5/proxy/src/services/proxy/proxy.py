import logging
import grpc
import uuid
import shutil
import yaml
import os
import time
import json
from urllib.parse import urlparse
from datetime import datetime
import threading
from typing import List, Tuple, Optional
import docker
from pathlib import Path


from config import conf

# Assuming protos are already correctly imported
from protos.cluster_operator.cluster_operator_pb2 import (
    HealthCheckRequest, HealthCheckResponse,
    OperatorStatus, GetOperatorInfoRequest, GetOperatorInfoResponse,
)
from protos.cluster_operator.cluster_operator_pb2_grpc import ClusterOperatorStub

# Private includes
from .db import ProxyServerDatabase, ClusterEntry
from .cluster import TestCluster


# -----------------------------------------------------------------------------------------------------
#                                                                                          Proxy Server 
# ---------------------------------------------------------------------------------------------------*/
class ProxyServer:
    def __init__(self, database_path:str):
        self.connected_clusters:List[TestCluster] = []

        # Read the current file system
        self.db:ProxyServerDatabase = ProxyServerDatabase(database_path)
        err = self.db.init()
        if err:
            raise ValueError("Unable to initiate database")

        self.registries_url:List[str] = [
            "ccr01.ad.corekinect.com"
        ]

        # Start the health check thread
        health_check_thread = threading.Thread(target=self.__perform_health_checks, daemon=True)
        health_check_thread.start()

    # -------------------------------------------------------------------------------------------------
    #                                                                             Cluster Health Checks
    # -----------------------------------------------------------------------------------------------*/
    def __perform_health_checks(self):
        """Periodically check the health of each cluster."""
        while True:
            for cluster in self.connected_clusters:
                try:
                    response: HealthCheckResponse = cluster.stub.HealthCheck(HealthCheckRequest())
                    cluster.status = response.status
                    if response.status is not ClusterStatus.Ready:
                        logging.error(f"Health check failed for cluster at {cluster.url},status: {response.status} error: {response.error}")
                except grpc.RpcError as e:
                    logging.error(f"Failed to perform health check on cluster at {cluster.url}. Error: {e}")
                    self.remove_cluster(cluster.uuid)

            time.sleep(1)

    # -------------------------------------------------------------------------------------------------
    #                                                                                    Create Cluster
    # -----------------------------------------------------------------------------------------------*/
    def create_cluster(self, name:str, deployment_path:str) -> Tuple[str, Optional[str]]:
        """
        Create a new cluster in the server's database. If there's a cluster with the same name already
        registered, function will return false
        """
        # Let's verify that the deployment is valid
        error = self.__verify_cluster_deployment(deployment_path)
        if error: 
            return f"Invalid deployment: {error}", None
        
        logging.info(f"Deployment passed is valid")

        return self.db.create_cluster(name, deployment_path)
    
    def __verify_cluster_deployment(self, deployment_path) -> str:
        # This is a k8s deployment, so what we want to do is
        # 1. guarantee that it's a pod, and
        # 2. search for all the container images in the registries we have access to

        # Read the deployment file content
        try:
            with open(deployment_path, 'r') as f:
                deployment = f.read()
        except FileNotFoundError:
            return f"Deployment file '{deployment_path}' not found"

        # Parse the deployment as YAML
        try:
            deployment_yaml = yaml.safe_load(deployment)
        except yaml.YAMLError as e:
            return f"Error parsing deployment file: {e}"

        # Check if the deployment is a Pod or Deployment
        if deployment_yaml['kind'] != 'Deployment':
            return "File is not a Kubernetes Deployment type"

        # Find all container images in the deployment
        container_images = []
        for container in deployment_yaml['spec']['template']['spec']['containers']:
            container_image = container['image']
            container_images.append(container_image)

            # Check if the registry URL of the container image is in the list of known registry URLs
            image_registry_url = urlparse(container_image).netloc
            if image_registry_url:
                if image_registry_url not in self.registries_url:
                    return f"Container image '{container_image}' is from an unknown registry: {image_registry_url}"
            else:
                # If no registry URL is specified in the container image, assume it's from one of the known registries
                if not any(registry_url in container_image for registry_url in self.registries_url):
                    return f"Container image '{container_image}' is from an unknown registry, valid options: {self.registries_url}"

        # Check if all container images exist in the registries
        client = docker.from_env()
        logging.debug(f"Images {container_images}")
        for image in container_images:
            found = False
            for registry_url in self.registries_url:
                try:
                    # Connect to the registry and check if the image exists
                    client.images.get_registry_data(image, registry_url)
                    found = True
                    logging.info(f"Image {image} found!")
                    break
                except docker.errors.NotFound:
                    pass
            if not found:
                return f"Container image '{image}' not found in known registries"

        return ""
    
    # -------------------------------------------------------------------------------------------------
    #                                                                                    Cluster Update
    # -----------------------------------------------------------------------------------------------*/
    def update_cluster(self, cluster_uuid:str, deployment_path:str) -> str:
        """Remove a cluster from the list by ID."""

        # Let's verify that the deployment is valid
        error = self.__verify_cluster_deployment(deployment_path)
        if error: 
            return f"Invalid deployment: {error}", None
        
        # Update the database
        error:str = self.db.update_cluster_deployment(cluster_uuid, deployment_path)
        if error: 
            return f"Could not update database: {error}"
        
        logging.info(f"Deployment updated succesfully {cluster_uuid}")

        # Easiest way to reload the cache is to just update 
        error = self.db.init()
        if error:
            return f"Could not update database cache: {error}"

        # # Update the cluster itself
        # for cluster in self.connected_clusters:
        #     if cluster.uuid == cluster_uuid:
        #         try:
        #             # Read the deployment directly from the database, as we've changed a few things
        #             error, cluster_info = self.get_cluster_info(cluster_uuid)
        #             if error:
        #                 return f"Fatal error, an UUID that was supposed to be in the database was not found: {error}"

        #             # Using the dictionary above extract the latest deployment file path
        #             entry = ClusterEntry.from_dict(cluster_info)

        #             # Open the latest deployment file
        #             deployment_file_path = Path(entry.current_deployment)  # Assuming this is a file path
        #             if not deployment_file_path.is_file():
        #                 return f"Deployment file does not exist: {entry.current_deployment}"

        #             # Read the file's content
        #             with open(deployment_file_path, 'rb') as file:
        #                 deployment_data = file.read()

        #             # Create a request to update the deployment on the gRPC server
        #             response = cluster.stub.UpdateClusterDeployment(
        #                 UpdateDeploymentRequest(
        #                     deployment_file=deployment_data,
        #                     filename=deployment_file_path.name,  # Extract just the file name
        #                 )
        #             )

        #             # Check for response from gRPC server, assuming you need to handle this part
        #             if not response.success:
        #                 return f"Failed to update cluster deployment: {response.error_message}"

        #             logging.info(f"Deployment sent to cluster {cluster_uuid}")
                    
        #         except grpc.RpcError as e:
        #             return f"Could not update cluster {cluster_uuid} deployment: {e}"
        #         except Exception as e:
        #             return f"Unexpected error occurred: {str(e)}"        
        return ""
    
    # -------------------------------------------------------------------------------------------------
    #                                                                                    Cluster Update
    # -----------------------------------------------------------------------------------------------*/

    # -------------------------------------------------------------------------------------------------
    #                                                                                  Register Cluster
    # -----------------------------------------------------------------------------------------------*/
    def register_cluster(self, cluster_uuid, cluster_url:str) -> str:
        """
        Register a new cluster to the server. This involves this proxy 
        connecting to the cluster at hand
        """

        # Check if the cluster is even created yet
        cluster_created:bool = False
        for uuid in self.db.get_cluster_uuids():
            if uuid == cluster_uuid:
                cluster_created = True
                break
        
        if not cluster_created:
            return f"Cluster {cluster_uuid} at {cluster_url} was not found in server"

        # Check if the cluster is already connected
        for cluster in self.connected_clusters:
            if cluster.url == cluster_url:
                return ""
        
        # Get initial metadata
        error = self.__get_cluster_info(cluster_url)
        if error:
            return f"Unable to get cluster info: {error}. Did you "
        
        return ""
    
    def __get_cluster_info(self, cluster_url:str) -> str:
        try:            
            # Create a gRPC channel
            channel = grpc.insecure_channel(cluster_url)

            # Create a stub using the insecure channel
            stub = ClusterOperatorStub(channel)

            # Get cluster metadata over the gRPC connection
            # try:
            #     response:GetClusterInfoResponse = stub.GetClusterInfo(request=GetClusterInfoRequest())
            #     if response.info is not None:

            #         # Register the cluster with the proxy server (us), with enough information
            #         # to execute actions on it
            #         new_cluster = TestCluster(
            #             uuid=str(uuid.uuid4()),
            #             url=cluster_url,
            #             stub = stub,
            #             info=response.info,
            #             connected_at=datetime.now().isoformat()
            #         )
            #         self.connected_clusters.append(new_cluster)

            # except grpc.RpcError as e:
            #     return f"Unable to register cluster at {cluster_url}: {e}"

            logging.info(f"Successfully registered cluster at {clusterp_url}!")
            return ""

        except grpc.RpcError as e:
            return f"Failed to connect to cluster at {cluster_url}. Error: {e}"
        
    def __find_cluster_deployment(self, cluster:TestCluster) -> Tuple[bool, str, bool, str]:
        """This function is going to look through a  """

        pass
        
    # -------------------------------------------------------------------------------------------------
    #                                                                                      Get Clusters
    # -----------------------------------------------------------------------------------------------*/
    def get_clusters(self) -> List[TestCluster]:
        """Get a cluster's information by ID."""
        return self.connected_clusters
    
    # -------------------------------------------------------------------------------------------------
    #                                                                                  Get Cluster Info
    # -----------------------------------------------------------------------------------------------*/
    def get_cluster_info(self, cluster_uuid: str) -> Tuple[str, Optional[dict]]:
        """Get a cluster's information by UUID."""
        return self.db.get_cluster_info(cluster_uuid)

    # -------------------------------------------------------------------------------------------------
    #                                                                                      Get Clusters
    # -----------------------------------------------------------------------------------------------*/
    # def get_cluster_tests(self, cluster_uuid: str) -> Tuple[bool, str, Optional[List[TestInfo]]]:
    #     """Get a cluster's information by UUID."""
    #     for cluster in self.connected_clusters:
    #         if cluster.uuid == cluster_uuid:
    #             try:
    #                 response:ListTestsResponse = cluster.stub.ListTests(ListTestsRequest())
    #                 return True, "", response.tests
    #             except grpc.RpcError as e:
    #                 return False, f"Unable to get cluster tests at {cluster.url}: {e}", None

    #     return False, f"Cluster {cluster_uuid} was not found in proxy", None
    
    # -------------------------------------------------------------------------------------------------
    #                                                                                         Exec Test
    # -----------------------------------------------------------------------------------------------*/
    # def exec_cluster_test(self, cluster_uuid: str, test_uuid: str, runner_ids: List[int]) -> Tuple[bool, str]:
    #     for cluster in self.connected_clusters:
    #         if cluster.uuid == cluster_uuid:
    #             logging.warning(f"found cluster {cluster_uuid}")
    #             try:
    #                 logging.warning("executing request")
    #                 # Create the request object properly
    #                 request = ExecuteTestRequest(testId=test_uuid, runnerIds=runner_ids)
    #                 # Call the ExecuteTest method with the request
    #                 response_stream = cluster.stub.ExecuteTest(request)
    #                 logging.warning("Before entering response_stream loop")
    #                 for response in response_stream:
    #                     logging.warning(f"Received response: {response}")
    #                 return True, ""
    #             except grpc.RpcError as e:
    #                 logging.error(f"RPC Error: {e}")
    #                 return False, str(e)

    # -------------------------------------------------------------------------------------------------
    #                                                                                    Cluster Delete
    # -----------------------------------------------------------------------------------------------*/
    def delete_cluster(self, cluster_uuid:str) -> str:
        """Remove a cluster from the list by ID."""
        return self.db.delete_cluster(cluster_uuid)
    
    

# Class Singleton                
proxy_server:ProxyServer = ProxyServer(conf.DB_PATH) 