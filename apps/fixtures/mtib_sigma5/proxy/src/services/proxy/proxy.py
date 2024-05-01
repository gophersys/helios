import logging
import grpc
import uuid
import shutil
import yaml
import sys
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
from protos.cluster_test.cluster_test_pb2 import (
    TestInfo
)

from protos.cluster_operator.cluster_operator_pb2 import (
    HealthCheckRequest, HealthCheckResponse,
    OperatorStatus, GetOperatorInfoRequest, GetOperatorInfoResponse,
    ListTestsRequest, ListTestsResponse,
)
from protos.cluster_operator.cluster_operator_pb2_grpc import ClusterOperatorStub

# App includes
from services.db import Database, DatabaseConfiguration
from services.proxy.types import Cluster, ClusterType, ClusterStatus

# ----------------------------------------------------------------------------------
#                                                                      Configuration
# --------------------------------------------------------------------------------*/
class ProxyServerConfiguration:
    """
    Attributes:
        db_storage_path (str): File system path for the internal database.
        supported_registries (List[str]): Where developers will store deployment images.
    """
    def __init__(self,
                db_storage_path:str,
                db_storage_limit_gb:int, 
                supported_registries:List[str]
                ):
        self.db_storage_path:str = db_storage_path
        self.db_storage_limit_gb:str = db_storage_limit_gb
        self.supported_registries:List[str] = supported_registries
    
# ----------------------------------------------------------------------------------
#                                                                         Main Class
# --------------------------------------------------------------------------------*/
class ProxyServer:
    ###
    # @TODO:
    # - Documentation for class
    ###
    
    # -----------------------------------------------------------------------------
    #                                                                          Init
    #  --------------------------------------------------------------------------*/
    def __init__(self):
        self.initialized = False
        self.config:ProxyServerConfiguration = None
        
        # Objects we manage
        self.clusters:List[Cluster] = []

    def init(self, config:ProxyServerConfiguration) -> str:
        if self.initialized:
            return "Do not initialize class again."
        
        self.config = config
        
        # Initialize the server's database
        db_config:DatabaseConfiguration = DatabaseConfiguration(
            db_storage_path=self.config.db_storage_path,
            storage_limit_gb=self.config.db_storage_limit_gb,
            storage_full_cb=self._db_storage_full_cb
        )
        self.db:Database = Database()
        
        error = self.db.init(db_config)
        if error:
            return f"Proxy server could not initialize database: {error}"
        
        # Populate our own objects based on the database info
        clusters_info = self.db.get_clusters_info()
        for info in clusters_info:
            cluster = Cluster(
                name=info.name,
                type=info.type,
                uuid=info.uuid,
                registered=False,
                status=ClusterStatus.DISCONNECTED,
                url=None,
                channel=None,
                stub=None
            )
            self.clusters.append(cluster)

        logging.info(f"{len(self.clusters)} clusters are being managed by the server")
        
        # Start server threads
        self.health_check_thread = threading.Thread(target=self._cluster_healthchecks_thread, daemon=True)
        self.health_check_thread.start()
    
    # -----------------------------------------------------------------------------
    #                                                                     Callbacks
    #  --------------------------------------------------------------------------*/
    def _db_storage_full_cb(self, error):
        logging.error(f"Server ran out of storage :( , database error: {error}")
        sys.exit(1)
        
    # -----------------------------------------------------------------------------
    #                                                                       Threads
    #  --------------------------------------------------------------------------*/
    def _cluster_healthchecks_thread(self):
        while True:
            clusters = self.clusters 
            for cluster in clusters:
                if cluster.registered and cluster.status == ClusterStatus.CONNECTED:
                    try:
                        # Perform a periodic health check to ensure we're still connected and alive
                        cluster.stub.HealthCheck(HealthCheckRequest())
                        
                    except grpc.RpcError as e:
                        logging.error(f"Failed to perform health check on cluster at {cluster.url}. Unregistering from cluster")
                        cluster.channel.close()
                        self.clusters.remove(cluster)

            time.sleep(1)    
    
    # -----------------------------------------------------------------------------
    #                                                               Cluster Methods
    #  --------------------------------------------------------------------------*/
    def clusters_create(self, name:str, type:str) -> Tuple[str, Optional[str]]:
        """
        Create a new cluster in the server's database. If there's a cluster with the same name already
        registered, function will return false
        """
        # Check that we support the type
        if not ClusterType.is_valid_type(type):
            return f"Unsupported cluster type '{type}'.", None
        
        # Add a new database entry
        error, uuid = self.db.cluster_create(name, type)
        if error:
            return error, None
        
        # Get the newly added info
        error, info = self.db.cluster_get_info(uuid)
        if error:
            return error, None
        
        # Add an entry to the local server cache
        cluster = Cluster(
            name=info.name,
            type=info.type,
            uuid=info.uuid,
            registered=False,
            status=ClusterStatus.DISCONNECTED,
            url=None,
            channel=None,
            stub=None
        )
        self.clusters.append(cluster)
        
        logging.info(f"Created proxy {cluster.name} with ID {cluster.uuid} succesfully")
        return "", uuid
    
    def clusters_get(self) -> List[Cluster]:
        return self.clusters
    
    def clusters_delete_all(self) -> str:
        clusters_to_remove = [cluster for cluster in self.clusters if cluster.status != ClusterStatus.CONNECTED]
        
        for cluster in clusters_to_remove:
            logging.info(f"Removing cluster {cluster.name} with ID {cluster.uuid}")
            error = self.db.cluster_delete(cluster.uuid)
            if error:
                return error
            self.clusters.remove(cluster)

        # Log warning for clusters not removed
        for cluster in self.clusters:
            if cluster.status == ClusterStatus.CONNECTED:
                logging.warning(f"Cannot remove cluster {cluster.name} with ID {cluster.uuid} while it's connected")
        
        return ""
    
    def clusters_delete_one(self, cluster_uuid: str) -> str:
        # Iterate over a copy of the list to safely remove items while iterating
        for cluster in list(self.clusters):
            if cluster.uuid == cluster_uuid:
                if cluster.status == ClusterStatus.CONNECTED:
                    return f"Cluster {cluster.name} with UUID {cluster_uuid} is currently connected and cannot be removed."

                # Update database
                error = self.db.cluster_delete(cluster.uuid)
                if error:
                    return error

                # Remove the cluster from the server's cache
                self.clusters.remove(cluster)
                logging.info(f"Removed cluster {cluster.name} with ID {cluster.uuid}")
                return ""

        return f"Cluster with UUID {cluster_uuid} not found in server."
    
    def clusters_register(self, cluster_uuid:str, cluster_url:str) -> str:
        # Check if the cluster is even created yet
        cluster:Cluster = None
        for c in self.clusters:
            if c.uuid == cluster_uuid:
                cluster = c
                break
        
        if cluster is None:
            return f"Cluster {cluster_uuid} at {cluster_url} was not found in server database. You must create a new cluster first"

        # Check if the cluster is already connected
        if cluster.registered and cluster.status == ClusterStatus.CONNECTED:
            logging.warning(f"Cluster {cluster.name} at {cluster.url} is trying to register while in the connected state. Possible operator software bug?")
            return ""
        
        # Get initial metadata
        try:            
            # Create a gRPC channel
            channel = grpc.insecure_channel(cluster_url)

            # Create a stub using the insecure channel
            stub = ClusterOperatorStub(channel)
            
            # Populate missing fields from entry
            cluster.url = cluster_url
            cluster.channel = channel
            cluster.stub = stub
            cluster.status = ClusterStatus.CONNECTED
            logging.info(f"Cluster {cluster.name} with UUID {cluster.uuid} has been successfully registered and connected.")
            
            return ""
            
        except grpc.RpcError as e:
            return f"Failed to connect to cluster at {cluster_url}. Error: {e}"
             
    # -------------------------------------------------------------------------------------------------
    #                                                                                    Create Cluster
    # -----------------------------------------------------------------------------------------------*/
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
                if image_registry_url not in self.supported_registries:
                    return f"Container image '{container_image}' is from an unknown registry: {image_registry_url}"
            else:
                # If no registry URL is specified in the container image, assume it's from one of the known registries
                if not any(registry_url in container_image for registry_url in self.supported_registries):
                    return f"Container image '{container_image}' is from an unknown registry, valid options: {self.supported_registries}"

        # Check if all container images exist in the registries
        client = docker.from_env()
        logging.debug(f"Images {container_images}")
        for image in container_images:
            found = False
            for registry_url in self.supported_registries:
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
    #                                                                                 Get Cluster Tests
    # -----------------------------------------------------------------------------------------------*/
    def get_cluster_tests(self, cluster_uuid:str) -> Tuple[str, Optional[List[TestInfo]]]:
        # Check if the cluster is already connected
        cluster:Cluster = None
        for c in self.clusters:
            if c.uuid == cluster_uuid:
                cluster = c
            
        if cluster is None:
            return f"Cluster {cluster_uuid} is not registered with the proxy", None
        
         # List the tests over gRPC
        try:
            response:ListTestsResponse = cluster.stub.ListTests(ListTestsRequest())
            return "", response.tests
        except grpc.RpcError as e:
            return f"Unable to get tests for cluster at {cluster.url} info over gRPC method ListTests(): {e}", None
    
    
        
    # -------------------------------------------------------------------------------------------------
    #                                                                                      Get Clusters
    # -----------------------------------------------------------------------------------------------*/
    
    
    # -------------------------------------------------------------------------------------------------
    #                                                                                  Get Cluster Info
    # -----------------------------------------------------------------------------------------------*/
    def get_cluster_info(self, cluster_uuid: str) -> Tuple[str, Optional[dict]]:
        """Get a cluster's information by UUID."""
        return self.db.cluster_get_info(cluster_uuid)

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

# Class Singleton                
appProxyServer:ProxyServer = ProxyServer() 