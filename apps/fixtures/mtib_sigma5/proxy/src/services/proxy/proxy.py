import logging
import docker.errors
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
from flask_socketio import SocketIO

from config import conf

# Assuming protos are already correctly imported
from protos.cluster_test.cluster_test_pb2 import (
    TestInfo
)

from protos.cluster_operator.cluster_operator_pb2 import (
    HealthCheckRequest, NodeInfo,
    GetClusterInfoRequest, GetClusterInfoResponse,
    ListTestsRequest, ListTestsResponse,
    DeploymentInfo,GetDeploymentInfoResponse, GetDeploymentInfoRequest
)
from protos.cluster_operator.cluster_operator_pb2_grpc import ClusterOperatorStub

# App includes
from services.db import Database, DatabaseConfiguration
from services.db.schema import Cluster, ClusterType

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
                supported_registries:List[str],
                socketio:SocketIO,
                ):
        self.db_storage_path:str = db_storage_path
        self.db_storage_limit_gb:str = db_storage_limit_gb
        self.supported_registries:List[str] = supported_registries
        self.socketio:SocketIO = socketio
    
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
        
        # Docker info
        logger = logging.getLogger('docker')
        logger.setLevel(logging.INFO)
        self.docker_client:docker.DockerClient = None

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
                info=info,
                error=None,
                status=None,
                url=None,
                channel=None,
                stub=None
            )
            self.clusters.append(cluster)

        logging.info(f"{len(self.clusters)} clusters are being managed by the server")
        
        # Services we use
        self.docker_client = docker.from_env()
        
        # Start server threads
        self.health_check_thread = threading.Thread(target=self._cluster_healthchecks_thread, daemon=True)
        self.health_check_thread.start()
        
        return ""
    
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
                if cluster.info.registered and cluster.status is not None:
                    try:
                        # Perform a periodic health check to ensure we're still connected and alive
                        response = cluster.stub.HealthCheck(HealthCheckRequest())
                        cluster.status = response.status
                        cluster.error = response.error
                        
                    except grpc.RpcError as e:
                        error:str = f"Failed to perform health check on cluster at {cluster.url}. Disconnecting from cluster"
                        logging.error(error)
                        cluster.status = None
                        cluster.error = error
                        cluster.channel.close()

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
            info=info,
            status=None,
            error=None,
            url=None,
            channel=None,
            stub=None
        )
        self.clusters.append(cluster)
        
        logging.info(f"Created proxy {cluster.info.name} with ID {cluster.info.uuid} succesfully")
        return "", uuid
    
    def clusters_get(self) -> List[Cluster]:
        return self.clusters
    
    def clusters_get_nodes_info(self, cluster_uuid:str) -> List[NodeInfo]:
        # First find the cluster
        cluster:Cluster = None
        for c in list(self.clusters):
            if c.info.uuid == cluster_uuid:
                cluster = c
                
        if cluster is None:
            return f"Cluster with UUID {cluster_uuid} not found in server."
        
        if cluster.status is not None:
            try:
                # Perform a periodic health check to ensure we're still connected and alive
                response:GetClusterInfoResponse = cluster.stub.GetClusterInfo(GetClusterInfoRequest())
                return response.nodes_info
                
            except grpc.RpcError as e:
                error:str = f"Failed to get GetClusterInfo on cluster at {cluster.url}. Disconnecting from cluster"
                logging.error(error)
                cluster.status = None
                cluster.error = error
                cluster.channel.close()
        else:
            return []
    
    def clusters_delete_all(self) -> str:
        clusters_to_remove = [cluster for cluster in self.clusters if cluster.status is None]
        
        for cluster in clusters_to_remove:
            logging.info(f"Removing cluster {cluster.info.name} with ID {cluster.info.uuid}")
            error = self.db.cluster_delete(cluster.info.uuid)
            if error:
                return error
            self.clusters.remove(cluster)

        # Log warning for clusters not removed
        for cluster in self.clusters:
            if cluster.status is not None:
                logging.warning(f"Cannot remove cluster {cluster.info.name} with ID {cluster.info.uuid} while it's connected")
        
        return ""
    
    def clusters_delete_one(self, cluster_uuid: str) -> str:
        # Iterate over a copy of the list to safely remove items while iterating
        for cluster in list(self.clusters):
            if cluster.info.uuid == cluster_uuid:
                if cluster.status is not None:
                    return f"Cluster {cluster.info.name} with UUID {cluster_uuid} is currently connected and cannot be removed."

                # Update database
                error = self.db.cluster_delete(cluster.info.uuid)
                if error:
                    return error

                # Remove the cluster from the server's cache
                self.clusters.remove(cluster)
                logging.info(f"Removed cluster {cluster.info.name} with ID {cluster.info.uuid}")
                return ""

        return f"Cluster with UUID {cluster_uuid} not found in server."
    
    def clusters_register(self, cluster_uuid:str, cluster_url:str) -> str:
        # Check if the cluster is even created yet
        cluster:Cluster = None
        for c in self.clusters:
            if c.info.uuid == cluster_uuid:
                cluster = c
                break
        
        if cluster is None:
            return f"Cluster {cluster_uuid} at {cluster_url} was not found in server database. You must create a new cluster first"

        # Check if the cluster is already connected
        if cluster.info.registered and cluster.status is not None:
            logging.warning(f"Cluster {cluster.info.name} at {cluster.url} is trying to register while in the connected state. Possible operator software bug?")
            return ""
        
        # Get initial metadata
        try:            
            # Create a gRPC channel
            channel = grpc.insecure_channel(cluster_url)

            # Create a stub using the insecure channel
            stub = ClusterOperatorStub(channel)
            
            # Update the database
            error = self.db.cluster_register(cluster_uuid)
            if error:
                return f"Database error while trying to register: {error}"
            
            # Do an initial health check to get status
            response = stub.HealthCheck(HealthCheckRequest())
                        
            # Populate missing fields from entry
            cluster.status = response.status
            cluster.error = response.error
            cluster.url = cluster_url
            cluster.channel = channel
            cluster.stub = stub
            
            logging.info(f"Cluster {cluster.info.name} with UUID {cluster.info.uuid} has been successfully registered and connected.")
            return ""
            
        except grpc.RpcError as e:
            return f"Failed to connect to cluster at {cluster_url}. Error: {e}"
    
    # -----------------------------------------------------------------------------
    #                                                   Cluster Deployments Methods
    #  --------------------------------------------------------------------------*/ 
    def cluster_deployments_create(self, cluster_uuid:str, deployment_name:str, deployment_file_path:str) -> Tuple[str, Optional[str]]:
        # Make sure the contents of the file make sense
        error = self._deployment_verify(deployment_file_path)
        if error:
            return f"Deployment is not valid: {error}", None
        
        # Create a new entry in the database
        error, deployment_uuid = self.db.cluster_deployment_create(cluster_uuid, deployment_name, deployment_file_path)
        if error:
            return f"Unable to save new deployment to database: {error}", None
        
        logging.info(f"New deployment created for cluster {cluster_uuid}")
        return "", deployment_uuid
    
    def cluster_deployments_get_info(self, cluster_uuid:str) -> Tuple[str, Optional[List[DeploymentInfo]]]:
        # First find the cluster
        cluster:Cluster = None
        for c in list(self.clusters):
            if c.info.uuid == cluster_uuid:
                cluster = c
                
        if cluster is None:
            return f"Cluster with UUID {cluster_uuid} not found in server.", None
        
        if cluster.status is not None:
            try:
                # Perform a periodic health check to ensure we're still connected and alive
                response:GetDeploymentInfoResponse = cluster.stub.GetDeploymentInfo(GetDeploymentInfoRequest())
                return "", response.deployment_info
                
            except grpc.RpcError as e:
                return f"Failed to get GetClusterInfo on cluster at {cluster.url}: {str(e)}", None
        else:
            return f"Cluster {cluster_uuid} is not connected", None
        
    def cluster_deployments_get_path(self, cluster_uuid:str, deployment_uuid:str) -> Tuple[str, Optional[str]]:
        return self.db.cluster_deployment_get_path(cluster_uuid, deployment_uuid)
    
    def cluster_deployments_delete_all(self, cluster_uuid:str) -> str:
        # First find the cluster
        cluster:Cluster = None
        for c in list(self.clusters):
            if c.info.uuid == cluster_uuid:
                cluster = c
                
        if cluster is None:
            return f"Cluster with UUID {cluster_uuid} not found in server."
        
        # Delete from the database
        for deployment in list(cluster.info.deployments):
            error = self.db.cluster_deployment_delete(cluster_uuid, deployment.uuid)
            if error:
                return f"Unable to delete deployment {deployment.uuid} from database: {error}"
        
        # Relaod the cluster info
        error, info = self.db.cluster_get_info(cluster_uuid)
        if error:
            return error, None
        
        cluster.info = info
        
        logging.info(f"Removed all deployments for cluster {cluster_uuid}")
        return ""
    
    def cluster_deployments_delete_one(self, cluster_uuid:str, deployment_uuid:str) -> str:
        # First find the cluster
        cluster:Cluster = None
        for c in list(self.clusters):
            if c.info.uuid == cluster_uuid:
                cluster = c
                
        if cluster is None:
            return f"Cluster with UUID {cluster_uuid} not found in server."
        
        # Delete from the database
        error = self.db.cluster_deployment_delete(cluster_uuid, deployment_uuid)
        if error:
            return f"Unable to delete deployment from database: {error}"
        
        logging.info(f"Removed deployment {deployment_uuid} for cluster {cluster_uuid}")
        return ""
    
    def clusters_deployments_apply(self, cluster_uuid:str, deployment_uuid:str) -> str:
        # Set the deployment so that the cluster will fetch it next time it's ready for an update
        error = self.db.cluster_deployment_set(cluster_uuid, deployment_uuid)
        if error:
            return f"Could not set cluster deployment {deployment_uuid} for cluster {cluster_uuid}"

        logging.info(f"Cluster {cluster_uuid} deployment was updated to {deployment_uuid}")
        return ""
    
    def _deployment_verify(self, deployment_file_path) -> str:
        # Read the deployment file content
        try:
            with open(deployment_file_path, 'r') as f:
                deployment_contents = f.read()
        except FileNotFoundError:
            return f"Deployment file '{deployment_file_path}' not found"

        try:
            documents = list(yaml.safe_load_all(deployment_contents))
        except yaml.YAMLError as e:
            return f"Error parsing deployment file: {e}"

        if not documents:
            return "No valid Kubernetes deployment found in the file"

        for deployment_yaml in documents:
            if not deployment_yaml or 'kind' not in deployment_yaml:
                continue  # Skip empty or malformed documents

            # Check if the deployment is a Pod or Deployment
            if deployment_yaml['kind'] != 'Deployment':
                return "File is not a Kubernetes Deployment type"

            # Find all container images in the deployment
            try:
                containers = deployment_yaml['spec']['template']['spec']['containers']
            except KeyError as e:
                return f"Error extracting containers from deployment: {e}"

            container_images = []
            for container in containers:
                container_image = container['image']
                container_images.append(container_image)

                # Check if the registry URL of the container image is in the list of known registry URLs
                image_registry_url = urlparse(container_image).netloc
                if image_registry_url:
                    if image_registry_url not in self.config.supported_registries:
                        return f"Container image '{container_image}' is from an unknown registry: {image_registry_url}"
                else:
                    # If no registry URL is specified in the container image, assume it's from one of the known registries
                    if not any(registry_url in container_image for registry_url in self.config.supported_registries):
                        return f"Container image '{container_image}' is from an unknown registry, valid options: {self.config.supported_registries}"

            # Check if all container images exist in the registries and support arm64 architecture
            for image in container_images:
                found = False
                arm64_supported = False
                for registry_url in self.config.supported_registries:
                    try:
                        # Connect to the registry and check if the image exists
                        image_data = self.docker_client.images.get_registry_data(image, registry_url)
                        found = True
                        # Check for arm64 support using the has_platform method
                        if image_data.has_platform('linux/arm64'):
                            arm64_supported = True
                            logging.info(f"Image {image} with arm64 support found!")
                            break
                    except docker.errors.NotFound:
                        pass
                    except docker.errors.APIError as e:
                        logging.error(f"API error while fetching image data: {e}")
                        return f"API error while checking image '{image}'"

                if not found:
                    return f"Container image '{image}' not found in known registries"
                if not arm64_supported:
                    return f"Container image '{image}' does not support arm64 architecture"

            logging.info("All images in deployment found with arm64 support in the registries")

        return ""

    # -----------------------------------------------------------------------------
    #                                                         Cluster Tests Methods
    #  --------------------------------------------------------------------------*/ 
    def clusters_tests_get(self, cluster_uuid:str) -> Tuple[str, Optional[List[TestInfo]]]:
        # First find the cluster
        cluster:Cluster = None
        for c in list(self.clusters):
            if c.info.uuid == cluster_uuid:
                cluster = c
                
        if cluster is None:
            return f"Cluster with UUID {cluster_uuid} not found in server."
        
        # Use gRPC to get a list of the tests currently present in the cluster
        try:
            # Perform a periodic health check to ensure we're still connected and alive
            response:ListTestsResponse = cluster.stub.ListTests(ListTestsRequest())
            return "", response.tests
            
        except grpc.RpcError as e:
            error = f"Unable to get tests for cluster at {cluster.url} info over gRPC method ListTests(): {e}"
            cluster.error = error
            return error, None

    def clusters_test_exec(self, cluster_uuid:str, test_uuid:str, results_cb, session_id:str) -> str:
        def run_test_simulation():
            for i in range(5):  # Send 5 updates
                time.sleep(1)  # Wait for a second between updates
                results_cb({
                    'test_uuid': test_uuid,
                    'update': f"Update {i+1}",
                    'done': False
                },
                session_id)
            
            # Send the final message indicating the test is done
            time.sleep(1)
            results_cb({
                'test_uuid': test_uuid,
                'update': "Final result",
                'done': True
            },
                session_id)
        
        # Start the thread to simulate test execution
        test_thread = threading.Thread(target=run_test_simulation)
        test_thread.start()
    
        return "Test execution started"
    
# Class Singleton                
appProxyServer:ProxyServer = ProxyServer() 