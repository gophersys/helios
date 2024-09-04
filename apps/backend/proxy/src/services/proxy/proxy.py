import json
import logging
import os
import shutil
import sys
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Callable, List, Optional, Tuple
from urllib.parse import urlparse

import docker
import docker.errors
import grpc
import yaml
from flask import Flask
from protos.cluster_operator.cluster_operator_pb2 import (
    DeploymentInfo,
    ExecuteTestRequest,
    GetClusterInfoRequest,
    GetClusterInfoResponse,
    GetDeploymentInfoRequest,
    GetDeploymentInfoResponse,
    HealthCheckRequest,
    ListTestsRequest,
    ListTestsResponse,
    NodeInfo,
    StopTestRequest,
    StopTestResponse,
)
from protos.cluster_operator.cluster_operator_pb2_grpc import ClusterOperatorStub

# Assuming protos are already correctly imported
from protos.cluster_test.cluster_test_pb2 import TestInfo, TestStepResult

from config import conf

# App includes
from src.services.database import Database, DatabaseConfiguration
from src.services.database.schema import Cluster, ClusterType, TestExecution

# ----------------------------------------------------------------------------------
#                                                                        Event Types
# --------------------------------------------------------------------------------*/


# ----------------------------------------------------------------------------------
#                                                                      Configuration
# --------------------------------------------------------------------------------*/
class ProxyServerConfiguration:
    """
    Attributes:
        db_storage_path (str): File system path for the internal database.
        supported_registries (List[str]): Where developers will store deployment images.
    """

    def __init__(
        self,
        db_storage_path: str,
        db_storage_limit_gb: int,
        supported_registries: List[str],
    ):
        self.db_storage_path: str = db_storage_path
        self.db_storage_limit_gb: str = db_storage_limit_gb
        self.supported_registries: List[str] = supported_registries


"""
Text execution callback. Called after a test step completes.

Args:
    (int): Cluster Id.
    (int): Execution Id.
    (bool): done, indicates the last call to this function.
    (bool): stopped, indicates if the test was stopped.
    (str): error, indicates an error running test.
    (int): The sequence of the test, used for percentage calculation.
    (List[TestStepResult]): A list of results for the step

Returns:
    None.
"""
TestResultCallbackFuncType = Callable[
    [int, int, bool, bool, Optional[str], Optional[int], Optional[List[TestStepResult]]], None
]


# ----------------------------------------------------------------------------------
#                                                                         Main Class
# --------------------------------------------------------------------------------*/
class ProxyServer:
    # TODO:
    #
    # What happens when a gRPC cluster to a cluster fails in a function call?

    # -----------------------------------------------------------------------------
    #                                                                          Init
    #  --------------------------------------------------------------------------*/
    def __init__(self):
        self.initialized = False
        self.config: ProxyServerConfiguration = None

        # Objects we manage
        self.clusters: List[Cluster] = []

        # Docker info
        logger = logging.getLogger("docker")
        logger.setLevel(logging.INFO)
        self.docker_client: docker.DockerClient = None

    def init(self, config: ProxyServerConfiguration) -> str:
        if self.initialized:
            return "Do not initialize class again."

        self.config = config

        # Initialize the server's database
        db_config: DatabaseConfiguration = DatabaseConfiguration(
            db_storage_path=self.config.db_storage_path,
            storage_limit_gb=self.config.db_storage_limit_gb,
            storage_full_cb=self._db_storage_full_cb,
        )
        self.db: Database = Database()

        error = self.db.init(db_config)
        if error:
            return f"Proxy server could not initialize database: {error}"

        # Populate our own objects based on the database info
        clusters_info = self.db.clusters_get_info()
        for info in clusters_info:
            cluster = Cluster(info=info, error=None, status=None, url=None, channel=None, stub=None)
            self.clusters.append(cluster)

        logging.info(f"{len(self.clusters)} clusters are being managed by the server")

        # Services we use
        self.docker_client = docker.from_env()

        # Start server threads
        self.health_check_thread = threading.Thread(target=self._cluster_healthchecks_thread, daemon=True)
        self.health_check_thread.start()

        return ""

    def get_database_usage(self) -> Tuple[str, str]:
        """
        Returns:
            - (int): Storage used in bytes
            - (int): Total storage in bytes
        """
        return self.db.get_storage_use()

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
                        response = cluster.stub.HealthCheck(HealthCheckRequest(), timeout=10)
                        cluster.status = response.status
                        cluster.error = response.error

                    except grpc.RpcError as e:
                        error: str = (
                            f"Failed to perform health check on cluster at {cluster.url}. Disconnecting from cluster"
                        )
                        logging.error(error)
                        cluster.status = None
                        cluster.error = error
                        cluster.channel.close()

            time.sleep(1)

    # -----------------------------------------------------------------------------
    #                                                               Cluster Methods
    #  --------------------------------------------------------------------------*/
    def clusters_create(self, name: str, type: str) -> Tuple[str, Optional[str]]:
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
        cluster = Cluster(info=info, status=None, error=None, url=None, channel=None, stub=None)
        self.clusters.append(cluster)

        logging.info(f"Created proxy {cluster.info.name} with ID {cluster.info.uuid} succesfully")
        return "", uuid

    def clusters_get(self) -> List[Cluster]:
        return self.clusters

    def clusters_get_nodes_info(self, cluster_uuid: str) -> Tuple[str, Optional[List[NodeInfo]]]:
        cluster: Cluster = self._find_cluster_by_uuid(cluster_uuid)
        if cluster is None:
            return f"Cluster with UUID {cluster_uuid} not found in server.", None

        if cluster.status is None:
            return "", []  # We can only return a list of nodes info if it's connected
        else:
            try:
                # Perform a periodic health check to ensure we're still connected and alive
                response: GetClusterInfoResponse = cluster.stub.GetClusterInfo(GetClusterInfoRequest())
                return "", response.nodes_info

            except grpc.RpcError as e:
                return f"gRPC error for GetClusterInfo() on cluster at {cluster.url}: {str(e)}", None

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
                logging.warning(
                    f"Cannot remove cluster {cluster.info.name} with ID {cluster.info.uuid} while it's connected"
                )

        return ""

    def clusters_delete_one(self, cluster_uuid: str) -> str:
        cluster: Cluster = self._find_cluster_by_uuid(cluster_uuid)
        if cluster is None:
            return f"Cluster with UUID {cluster_uuid} not found in server."

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

    def clusters_register(self, cluster_uuid: str, cluster_url: str) -> str:
        # Check if the cluster is even created yet
        cluster: Cluster = self._find_cluster_by_uuid(cluster_uuid)
        if cluster is None:
            return f"Cluster {cluster_uuid} at {cluster_url} was not found in server database. You must create a new cluster first!"

        # Check if the cluster is already connected
        if cluster.info.registered and cluster.status is not None:
            logging.warning(
                f"Cluster {cluster.info.name} at {cluster.url} is trying to register while in the connected state. Possible operator software bug?"
            )
            return ""

        # Get initial metadata
        try:
            # Create a gRPC channel
            channel = grpc.insecure_channel(cluster_url, options=(("grpc.enable_http_proxy", 0),))

            logging.info(f"Connecting to cluster at {cluster_url}")

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

            logging.info(
                f"Cluster {cluster.info.name} with UUID {cluster.info.uuid} has been successfully registered and connected."
            )
            return ""

        except grpc.RpcError as e:
            return f"Failed to connect to cluster at {cluster_url}. Error: {e}"

    # -----------------------------------------------------------------------------
    #                                                   Cluster Deployments Methods
    #  --------------------------------------------------------------------------*/
    def cluster_deployments_create(
        self, cluster_uuid: str, deployment_name: str, deployment_file_path: str
    ) -> Tuple[str, Optional[str]]:
        cluster: Cluster = self._find_cluster_by_uuid(cluster_uuid)
        if cluster is None:
            return f"Cluster with UUID {cluster_uuid} not found in server.", None

        # Make sure the contents of the file make sense
        error = self._deployment_verify(deployment_file_path)
        if error:
            return f"Deployment is not valid: {error}", None

        # Create a new entry in the database
        error, deployment_uuid = self.db.cluster_deployment_create(cluster_uuid, deployment_name, deployment_file_path)
        if error:
            return f"Unable to save new deployment to database: {error}", None

        # Relaod the cluster info
        error, info = self.db.cluster_get_info(cluster_uuid)
        if error:
            return error, None

        cluster.info = info

        logging.info(f"New deployment created for cluster {cluster_uuid}")
        return "", deployment_uuid

    def cluster_deployments_get_status(self, cluster_uuid: str) -> Tuple[str, Optional[List[DeploymentInfo]]]:
        cluster: Cluster = self._find_cluster_by_uuid(cluster_uuid)
        if cluster is None:
            return f"Cluster with UUID {cluster_uuid} not found in server.", None

        if cluster.status is not None:
            try:
                # Get the most up to date information about the deployment
                response: GetDeploymentInfoResponse = cluster.stub.GetDeploymentInfo(GetDeploymentInfoRequest())
                return "", response.deployment_info

            except grpc.RpcError as e:
                return f"Failed to get GetClusterInfo on cluster at {cluster.url}: {str(e)}", None
        else:
            return f"Cluster {cluster_uuid} is not connected", None

    def cluster_deployments_get_path(self, cluster_uuid: str, deployment_uuid: str) -> Tuple[str, Optional[str]]:
        return self.db.cluster_deployment_get_path(cluster_uuid, deployment_uuid)

    def cluster_deployments_delete_all(self, cluster_uuid: str) -> str:
        cluster: Cluster = self._find_cluster_by_uuid(cluster_uuid)
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
            return error

        cluster.info = info

        logging.info(f"Removed all deployments for cluster {cluster_uuid}")
        return ""

    def cluster_deployments_delete_one(self, cluster_uuid: str, deployment_uuid: str) -> str:
        cluster: Cluster = self._find_cluster_by_uuid(cluster_uuid)
        if cluster is None:
            return f"Cluster with UUID {cluster_uuid} not found in server."

        # Delete from the database
        error = self.db.cluster_deployment_delete(cluster_uuid, deployment_uuid)
        if error:
            return f"Unable to delete deployment from database: {error}"

        # Relaod the cluster info
        error, info = self.db.cluster_get_info(cluster_uuid)
        if error:
            return error

        cluster.info = info

        logging.info(f"Removed deployment {deployment_uuid} for cluster {cluster_uuid}")
        return ""

    def clusters_deployments_apply(self, cluster_uuid: str, deployment_uuid: str) -> str:
        cluster: Cluster = self._find_cluster_by_uuid(cluster_uuid)
        if cluster is None:
            return f"Cluster with UUID {cluster_uuid} not found in server."

        # Set the deployment so that the cluster will fetch it next time it's ready for an update
        error = self.db.cluster_deployment_set(cluster_uuid, deployment_uuid)
        if error:
            return f"Could not apply deployment: {error}"

        logging.info(f"Cluster {cluster_uuid} deployment was updated to {deployment_uuid}")
        return ""

    def _deployment_verify(self, deployment_file_path) -> str:
        # Load the deployment file contents
        try:
            with open(deployment_file_path, "r") as f:
                deployment_contents = f.read()
        except FileNotFoundError:
            return f"Deployment file '{deployment_file_path}' not found"

        # There may be more than 1 yaml document inside the same file, so parse them
        try:
            documents = list(yaml.safe_load_all(deployment_contents))
        except yaml.YAMLError as e:
            return f"Error parsing deployment file: {e}"

        if not documents:
            return "Did you upload an empty file?"

        # Check each document
        for document in documents:
            if not document or "kind" not in document:
                continue  # Skip empty or malformed documents

            # Check if the deployment is a Pod or Deployment
            if document["kind"] != "Deployment":
                return "File is not a Kubernetes Deployment type"

            # Find all container images in the deployment
            try:
                containers = document["spec"]["template"]["spec"]["containers"]
            except KeyError as e:
                return f"Error extracting containers from deployment: {e}"

            container_images = [container["image"] for container in containers]

            # Check container images against supported registries and architecture
            for container_image in container_images:
                image_registry_url = urlparse(container_image).netloc
                if image_registry_url and image_registry_url not in self.config.supported_registries:
                    return f"Container image '{container_image}' is from an unknown registry: {image_registry_url}"

                if not image_registry_url and not any(
                    registry_url in container_image for registry_url in self.config.supported_registries
                ):
                    return f"Container image '{container_image}' is from an unknown registry"

                # # Checking ARM64 support
                # if not self._check_arm64_support(container_image):
                #     return f"Container image '{container_image}' does not support arm64 architecture"

        logging.info("All images in deployment found with arm64 support in the registries")
        return ""

    def _check_arm64_support(self, image):
        """Check if the specified image supports ARM64 architecture."""
        try:
            image_data = self.docker_client.images.get(image)  # This retrieves the image data
            architecture = image_data.attrs.get("Architecture")
            if architecture == "arm64":
                logging.info(f"Image {image} supports arm64.")
                return True
            else:
                logging.info(f"Image {image} does not support arm64; it supports {architecture}.")
                return False
        except docker.errors.NotFound:
            logging.error(f"Image {image} not found.")
            return False
        except Exception as e:
            logging.error(f"Error retrieving image data for {image}: {str(e)}")
            return False

    # -----------------------------------------------------------------------------
    #                                                         Cluster Tests Methods
    #  --------------------------------------------------------------------------*/
    def clusters_tests_get(self, cluster_uuid: str) -> Tuple[str, Optional[List[TestInfo]]]:
        # First find the cluster
        cluster: Cluster = None
        for c in list(self.clusters):
            if c.info.uuid == cluster_uuid:
                cluster = c

        if cluster is None:
            return f"Cluster with UUID {cluster_uuid} not found in server.", None

        # Use gRPC to get a list of the tests currently present in the cluster
        try:
            # Perform a periodic health check to ensure we're still connected and alive
            response: ListTestsResponse = cluster.stub.ListTests(ListTestsRequest())
            return "", response.tests

        except grpc.RpcError as e:
            error = f"Unable to get tests for cluster at {cluster.url} info over gRPC method ListTests(): {e}"
            cluster.error = error
            return error, None

    def clusters_test_exec(
        self,
        cluster_uuid: str,
        test_uuid: str,
        test_config: str,
        test_nodes: List[str],
        results_cb: TestResultCallbackFuncType,
    ) -> Tuple[str, Optional[str]]:
        cluster: Cluster = self._find_cluster_by_uuid(cluster_uuid)
        if cluster is None:
            return f"Cluster with {cluster_uuid} not found in server.", None

        error, test_info = self._find_test_in_cluster_by_uuid(cluster, test_uuid)
        if error:
            return error, None

        # Create an execution entry in our database
        error, execution_uuid = self.db.cluster_test_execution_create(
            cluster_uuid, test_uuid, test_info, test_config, test_nodes
        )
        if error:
            return error, None

        # Run the test in a new thread
        def run_test_execution():
            # Create a request for the RPC with the relevant fields
            request = ExecuteTestRequest(uuid=test_uuid, config=test_config, nodes=test_nodes)

            try:
                # Call the RPC, which will return an array of stre
                for response in cluster.stub.ExecuteTest(request):
                    error = self.db.cluster_test_execution_append_result(
                        cluster_uuid, execution_uuid, response.results, response.stopped
                    )
                    if error:
                        logging.error(f"Could not append result to entry in database: f{error}")

                    # Callback for websockets
                    if results_cb is not None:
                        # Not done, stopped flag, No error, sequence, and results
                        results_cb(
                            cluster_uuid,
                            execution_uuid,
                            False,
                            response.stopped,
                            None,
                            response.sequence,
                            response.results,
                        )

                # Test execution is done, no more results
                if results_cb is not None:
                    # Done, no error, no sequence, no results
                    results_cb(cluster_uuid, execution_uuid, True, False, None, None, None)

            except grpc.RpcError as e:
                error = self.db.cluster_test_execution_set_error(cluster_uuid, execution_uuid, e.details())
                if error:
                    logging.error(f"Could not set error in execution entry in database: f{error}")

                # An error ocurred, let websockets know
                if results_cb is not None:
                    # Done, error, no sequence, no results
                    results_cb(cluster_uuid, execution_uuid, True, False, e.details(), None, None)

        # Start the thread to simulate test execution
        test_thread = threading.Thread(target=run_test_execution, daemon=True)
        test_thread.start()

        return "", execution_uuid

    def clusters_test_stop(self, cluster_uuid: str, test_uuid: str) -> str:
        cluster: Cluster = self._find_cluster_by_uuid(cluster_uuid)
        if cluster is None:
            return f"Cluster with {cluster_uuid} not found in server.", None

        error, _ = self._find_test_in_cluster_by_uuid(cluster, test_uuid)
        if error:
            return error, None

        try:
            response: StopTestResponse = cluster.stub.StopTest(StopTestRequest(uuid=test_uuid))
            if response.error:
                return f"Could not stop test in cluster {cluster_uuid}: {error}"

        except grpc.RpcError as e:
            return f"An exception ocurred trying to stop test {test_uuid} in cluster {cluster_uuid}: {e.details()}"

        return ""

    def clusters_test_executions_get(
        self, cluster_uuid: str, execution_uuid: str
    ) -> Tuple[str, Optional[TestExecution]]:
        return self.db.cluster_test_execution_get(cluster_uuid, execution_uuid)

    def cluster_test_executions_delete_all(self, cluster_uuid: str) -> str:
        cluster: Cluster = self._find_cluster_by_uuid(cluster_uuid)
        if cluster is None:
            return f"Cluster with UUID {cluster_uuid} not found in server."

        # Delete all test executions from the database
        for execution in list(cluster.info.executions):
            error = self.db.cluster_test_execution_delete(cluster_uuid, execution.uuid)
            if error:
                return f"Unable to delete execution {execution.uuid} from database: {error}"

        # Reload the cluster info
        error, info = self.db.cluster_get_info(cluster_uuid)
        if error:
            return error

        cluster.info = info

        logging.info(f"Removed all test executions for cluster {cluster_uuid}")
        return ""

    def cluster_test_executions_delete_one(self, cluster_uuid: str, execution_uuid: str) -> str:
        cluster: Cluster = self._find_cluster_by_uuid(cluster_uuid)
        if cluster is None:
            return f"Cluster with UUID {cluster_uuid} not found in server."

        # Delete from the database
        error = self.db.cluster_test_execution_delete(cluster_uuid, execution_uuid)
        if error:
            return f"Unable to delete execution from database: {error}"

        # Relaod the cluster info
        error, info = self.db.cluster_get_info(cluster_uuid)
        if error:
            return error

        cluster.info = info

        logging.info(f"Removed test execution {execution_uuid} for cluster {cluster_uuid}")
        return ""

    # -----------------------------------------------------------------------------
    #                                                               General Helpers
    #  --------------------------------------------------------------------------*/
    def _find_cluster_by_uuid(self, cluster_uuid: str) -> Cluster:
        for cluster in list(self.clusters):
            if cluster.info.uuid == cluster_uuid:
                return cluster

    def _find_test_in_cluster_by_uuid(self, cluster: Cluster, test_uuid) -> Tuple[str, Optional[TestInfo]]:
        error, tests_info = self.clusters_tests_get(cluster.info.uuid)
        if error:
            return error, None

        for info in tests_info:
            if info.uuid == test_uuid:
                return None, info

        return f"Test {test_uuid} was not found", None


# Class Singleton
appProxyServer: ProxyServer = ProxyServer()
