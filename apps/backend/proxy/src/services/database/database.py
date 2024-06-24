import json
import logging
import os
import shutil
import threading
import time
import uuid
from abc import abstractmethod
from dataclasses import asdict, dataclass, field
from datetime import datetime
from json.decoder import JSONDecodeError
from typing import Callable, List, Optional, Tuple

# Protocol includes
from protos.cluster_test.cluster_test_pb2 import TestInfo, TestStepResult

from .schema import (ClusterInfo, ClusterType, DeploymentInfo, TestExecution,
                     TestExecutionInfo)

# -------------------------------------------------------------------------------------------------
#                                                                                          Database
# -----------------------------------------------------------------------------------------------*/

# ----------------------------------------------------------------------------------
#                                                                      Configuration
# --------------------------------------------------------------------------------*/
# Defines a callback that passes a verbose error when this happens.
DatabaseStorageFullCallback = Callable[[str], None]


class DatabaseConfiguration:
    """
    Attributes:
        db_storage_path (str): File system path for the internal database.
        storage_limit_gb (List[str]): Max size we will ever let it get to.
        storage_full_cb (DatabaseStorageFullCallback): Called when we run out of space
    """

    def __init__(self, db_storage_path: str, storage_limit_gb: int, storage_full_cb: DatabaseStorageFullCallback):
        self.storage_path: str = db_storage_path
        self.storage_limit_gb: int = storage_limit_gb
        self.storage_full_cb: DatabaseStorageFullCallback = storage_full_cb


# ----------------------------------------------------------------------------------
#                                                                         Main Class
# --------------------------------------------------------------------------------*/
class Database:
    ###
    # @TODO:
    # - Implement the out of storage monitoring thread
    ###

    """
    The database only hosts cluster entries for now. A typicail SQL database would
    be created with links to tables, but a file system database is easier to create
    in a folder based style.

    The cluster file system contains 3 folders per cluster:

    - A deployments folder containing information about the current deployment and its updates
    - A logs folder used to periodically synchronize logs from the cluster operator
    - An executions folder used to periodically synchronize test results from the cluster operator

    storage/
    ├── clusters/
    │   ├── cluster_uuid_1/
    │   │   │   ├── info.json
    │   │   ├── deployments/
    │   │   │   ├── deployment_a.yaml
    │   │   │   ├── deployment_b.yaml
    │   │   ├── logs/
    │   │   │   ├── log_mm_dd_ss/
    │   │   ├── executions/
    |   │   │   ├── execution_uuid0.json
    |   │   │   ├── execution_uuid1.json
    """

    # -----------------------------------------------------------------------------
    #                                                                          Init
    #  --------------------------------------------------------------------------*/
    def __init__(
        self,
    ):
        self.initialized = False
        self.config = DatabaseConfiguration = None

        # Tables we manage
        self.cluster_entries: List[ClusterInfo] = []

        self.lock = threading.Lock()

    def init(self, config: DatabaseConfiguration) -> str:
        """
        Attempts to read all the entries that are saved in storage.

        Returns:
            str: An error string if we couldn't initialize the database. Empty if successful.
        """
        with self.lock:
            if self.initialized:
                return "Do not initialize class again."

            self.config = config

            # Check if there exists a clusters folder, which indicates a virgin file system or not
            clusters_dir = os.path.join(self.config.storage_path, "clusters")
            if not os.path.exists(clusters_dir):
                logging.warning(
                    f"No data detected in storage path: {self.config.storage_path}, server will start with no data!"
                )
                time.sleep(2)
                return ""

            # Empty the cache always
            logging.info("Initializaing database, reading from storage...")

            for cluster_uuid in os.listdir(clusters_dir):
                logging.debug(f"Uploading cluster {cluster_uuid}")
                info_path = os.path.join(clusters_dir, cluster_uuid, "info.json")

                if os.path.exists(info_path):
                    try:
                        with open(info_path, "r") as file:
                            entry_json = json.load(file)  # Open the JSON file
                            # TODO: Check that the entry below isnt nil
                            entry = ClusterInfo.unmarshal(entry_json)  # Unmarshal it into a struct
                            self.cluster_entries.append(entry)  # Add it to the server's cache

                            logging.debug(f"Loaded cluster entry {entry.name} OK")

                    except JSONDecodeError as e:
                        logging.warning(f"Invalid JSON in {info_path}: {e}. Skipping cluster database entry.")
                    except Exception as e:  # Any other errors.
                        return f"An unexpected error occurred while processing {info_path}: {e}"
                else:
                    logging.warning(f"No info.json found for cluster {cluster_uuid}. Skipping cluster.")

            self.initialized = True
            logging.info(f"Database initialized OK")

            return ""

    # -----------------------------------------------------------------------------
    #                                                                        Health
    #  --------------------------------------------------------------------------*/
    def get_storage_use(self) -> Tuple[int, int]:
        """
        Returns:
            - (int): Storage used in bytes
            - (int): Total storage in bytes
        """
        with self.lock:
            # Calculate the total storage in bytes (1 GB = 2^30 bytes)
            total_storage = self.config.storage_limit_gb * (2**30)

            # Function to sum the sizes of all files in a directory
            def get_directory_size(path):
                total_size = 0
                for root, dirs, files in os.walk(path):
                    for file in files:
                        file_path = os.path.join(root, file)
                        if os.path.exists(file_path):
                            total_size += os.path.getsize(file_path)
                return total_size

            # Calculate storage used
            storage_used = get_directory_size(self.config.storage_path)

            return storage_used, total_storage

    # -----------------------------------------------------------------------------
    #                                                                Cluster Schema
    #  --------------------------------------------------------------------------*/
    def clusters_get_info(self) -> List[ClusterInfo]:
        with self.lock:
            return self.cluster_entries

    def cluster_create(self, name: str, type: str) -> Tuple[str, Optional[str]]:
        """
        Create a new cluster entry in the file system

        Args:
            name (str): The name of the cluster to be created.
            type (ClusterType): The type of the cluster, represented by an instance of the ClusterType enum.

        Returns:
            Tuple[str, Optional[str]]: A tuple containing two elements:
                - The first element is an error message if the cluster could not be created.
                  Empty string is returned if the creation is successful without any additional remarks.
                - The second element is an optional string representing the unique identifier (UUID) of the newly created cluster.
                  If there's an error this string will be None.
        """
        with self.lock:
            # Check that the entry doesn't exist already
            for cluster in self.cluster_entries:
                if cluster.name == name:
                    return f'A cluster with name "{name}" already exists on the server.', None

            # Generate a UUID for the new entry
            cluster_uuid = str(uuid.uuid4())

            try:
                # Create the necessary directories for a new entry
                cluster_dir = os.path.join(self.config.storage_path, "clusters", cluster_uuid)
                os.makedirs(cluster_dir, exist_ok=True)

                deployments_dir = os.path.join(cluster_dir, "deployments")
                os.makedirs(deployments_dir, exist_ok=True)

                logs_dir = os.path.join(cluster_dir, "logs")
                os.makedirs(logs_dir, exist_ok=True)

                executions_dir = os.path.join(cluster_dir, "executions")
                os.makedirs(executions_dir, exist_ok=True)

                # Get the time at which the cluster was created (now)
                now = datetime.now().isoformat()

                # Create a new entry and append it to the cache
                cluster_info = ClusterInfo(
                    name=name,
                    type=ClusterType.from_string(type),
                    uuid=cluster_uuid,
                    registered=False,
                    created_at=now,
                    last_updated_at=now,
                    current_deployment="",
                    deployments=[],
                    logs=[],
                    executions=[],
                )

                self.cluster_entries.append(cluster_info)

                # Save the JSON file for the new entry
                info_path = os.path.join(cluster_dir, "info.json")
                with open(info_path, "w") as file:
                    json.dump(cluster_info.marshal(), file, indent=4)

                # Creation succesful
                return "", cluster_uuid

            except Exception as e:
                return f"Error creating cluster: {e}", None

    def cluster_delete(self, cluster_uuid: str) -> str:
        """
        Deletes a cluster folder and all its information from the database.

        Returns:
            str (error): An error if any ocurred. Empty other wise
        """
        with self.lock:
            cluster_dir = os.path.join(self.config.storage_path, "clusters", cluster_uuid)
            try:
                for cluster in self.cluster_entries:
                    if cluster.uuid == cluster_uuid:
                        shutil.rmtree(cluster_dir)
                        self.cluster_entries.remove(cluster)
                        return ""
                return f"Cluster with UUID {cluster_uuid} not found in the database."
            except Exception as e:
                return str(e)

    def cluster_register(self, cluster_uuid: str) -> str:
        with self.lock:
            # Check that the cluster exists
            cluster_info: ClusterInfo = None
            for cluster in self.cluster_entries:
                if cluster.uuid == cluster_uuid:
                    cluster_info = cluster

            if cluster_info is None:
                return f"Cluster with UUID {cluster_uuid} not found in the database."

            cluster_info.registered = True
            self._cluster_save_info(cluster_uuid)
            return ""

    def cluster_unregister(self, cluster_uuid: str) -> str:
        with self.lock:
            # Check that the cluster exists
            cluster_info: ClusterInfo = None
            for cluster in self.cluster_entries:
                if cluster.uuid == cluster_uuid:
                    cluster_info = cluster

            if cluster_info is None:
                return f"Cluster with UUID {cluster_uuid} not found in the database."

            cluster_info.registered = False
            self._cluster_save_info(cluster_uuid)
            return ""

    def cluster_get_info(self, cluster_uuid: str) -> Tuple[str, Optional[ClusterInfo]]:
        """Retrieves information about a specific cluster identified by its UUID."""
        with self.lock:
            try:
                for cluster in self.cluster_entries:
                    if cluster.uuid == cluster_uuid:
                        return "", cluster

                return f"Cluster with UUID {cluster_uuid} not found in the database", None
            except Exception as e:
                return str(e), None

    def _cluster_save_info(self, cluster_uuid: str):
        """Save cluster information to the info.json file in the cluster's directory."""

        cluster_info: ClusterInfo = None
        for cluster in self.cluster_entries:
            if cluster.uuid == cluster_uuid:
                cluster_info = cluster

        cluster_info.last_updated_at = datetime.now().isoformat()

        # Construct the path to the info.json file
        cluster_dir = os.path.join(self.config.storage_path, "clusters", cluster_info.uuid)
        info_path = os.path.join(cluster_dir, "info.json")

        # Serialize the ClusterSchema object to JSON. Replace 'marshal()' with your method of serialization if different.
        serialized_data = cluster_info.marshal()

        # Open the info.json file in write mode and dump the serialized data into it.
        try:
            with open(info_path, "w") as file:
                json.dump(serialized_data, file, indent=4)
        except IOError as e:
            return f"Failed to update cluster info due to an I/O error: {str(e)}"
        except Exception as e:
            return f"Failed to update cluster info due to an unexpected error: {str(e)}"

        # Indicate success if no exceptions were thrown
        return "Cluster info updated successfully."

    def _load_cluster_info(self, info_path: str) -> ClusterInfo:
        """Load cluster information from the info.json file"""
        with open(info_path, "r") as f:
            data = json.load(f)
        return ClusterInfo.unmarshal(data)

    # -----------------------------------------------------------------------------
    #                                                                    Deployment
    #  --------------------------------------------------------------------------*/
    def cluster_deployment_create(
        self, cluster_uuid: str, deployment_name: str, deployment_file_path: str
    ) -> Tuple[str, Optional[str]]:
        with self.lock:
            # Check that the cluster exists
            cluster_info: ClusterInfo = None
            for cluster in self.cluster_entries:
                if cluster.uuid == cluster_uuid:
                    cluster_info = cluster

            if cluster_info is None:
                return f"Cluster with UUID {cluster_uuid} not found in the database."

            cluster_dir = os.path.join(self.config.storage_path, "clusters", cluster_uuid)
            deployments_dir = os.path.join(cluster_dir, "deployments")

            try:
                # Create an unique file name
                deployment_uuid = str(uuid.uuid4())
                now = datetime.now().isoformat()
                new_deployment_filename = f"{deployment_uuid}.yaml"

                # Copy the deployment from the passed path into the database
                new_deployment_path = os.path.join(deployments_dir, new_deployment_filename)
                shutil.copy(deployment_file_path, new_deployment_path)

                # Update the cache
                cluster_info.deployments.append(
                    DeploymentInfo(name=deployment_name, uuid=deployment_uuid, created_at=now)
                )

                # Update the filesystem
                self._cluster_save_info(cluster_uuid)
                return "", deployment_uuid

            except Exception as e:
                return str(e), None

    def cluster_deployment_get_path(self, cluster_uuid: str, deployment_uuid: str) -> Tuple[str, Optional[str]]:
        with self.lock:
            # Check that the cluster exists
            cluster_info = None
            for cluster in self.cluster_entries:
                if cluster.uuid == cluster_uuid:
                    cluster_info = cluster
                    break

            if cluster_info is None:
                return f"Cluster with UUID {cluster_uuid} not found in the database.", None

            # Check that the deployment exists
            deployment = None
            for deployment in cluster_info.deployments:
                if deployment.uuid == deployment_uuid:
                    deployment = deployment
                    break

            if deployment is None:
                return f"Deployment with UUID {deployment_uuid} not found in cluster {cluster_uuid}.", None

            # Form and return the file path
            return "", os.path.abspath(
                os.path.join(
                    self.config.storage_path, "clusters", cluster_uuid, "deployments", f"{deployment_uuid}.yaml"
                )
            )

    def cluster_deployment_delete(self, cluster_uuid: str, deployment_uuid: str) -> str:
        with self.lock:
            # Check that the cluster exists
            cluster_info = None
            for cluster in self.cluster_entries:
                if cluster.uuid == cluster_uuid:
                    cluster_info = cluster
                    break

            if cluster_info is None:
                return f"Cluster with UUID {cluster_uuid} not found in the database."

            # Check that the deployment exists
            deployment_to_delete = None
            for deployment in cluster_info.deployments:
                if deployment.uuid == deployment_uuid:
                    deployment_to_delete = deployment
                    break

            if deployment_to_delete is None:
                return f"Deployment with UUID {deployment_uuid} not found in cluster {cluster_uuid}."

            # Attempt to remove the deployment file from the filesystem
            try:
                deployments_dir = os.path.join(self.config.storage_path, "clusters", cluster_uuid, "deployments")
                deployment_file_path = os.path.join(deployments_dir, f"{deployment_uuid}.yaml")

                if os.path.exists(deployment_file_path):
                    os.remove(deployment_file_path)
                else:
                    return f"No file found for deployment with UUID {deployment_uuid}."

                # Update the cache and remove the deployment from the cluster_info
                cluster_info.deployments.remove(deployment_to_delete)
                if deployment_uuid == cluster_info.current_deployment:
                    cluster_info.current_deployment = None

                # Update the filesystem
                self._cluster_save_info(cluster_uuid)

                return ""

            except Exception as e:
                return str(e)

    def cluster_deployment_get_info(
        self, cluster_uuid: str, deployment_uuid: str
    ) -> Tuple[str, Optional[ClusterInfo]]:
        """Retrieves information about a specific cluster identified by its UUID."""
        with self.lock:
            try:
                for cluster in self.cluster_entries:
                    if cluster.uuid == cluster_uuid:
                        for deployment in cluster.deployments:
                            if deployment.uuid == deployment_uuid:
                                return deployment

                return (
                    f"Deployment with UUID {deployment_uuid} in cluster {cluster_uuid} not found in the database",
                    None,
                )
            except Exception as e:
                return str(e), None

    def cluster_deployment_set(self, cluster_uuid: str, deployment_uuid: str) -> str:
        with self.lock:
            # Check that the cluster exists
            cluster_info = None
            for cluster in self.cluster_entries:
                if cluster.uuid == cluster_uuid:
                    cluster_info = cluster
                    break

            if cluster_info is None:
                return f"Cluster with UUID {cluster_uuid} not found in the database."

            # Check that the deployment exists
            deployment_to_delete = None
            for deployment in cluster_info.deployments:
                if deployment.uuid == deployment_uuid:
                    deployment_to_delete = deployment
                    break

            if deployment_to_delete is None:
                return f"Deployment with UUID {deployment_uuid} not found in cluster {cluster_uuid}."

            # Attempt to remove the deployment file from the filesystem
            try:
                # Update the cache
                cluster_info.current_deployment = deployment_uuid

                # Update the filesystem
                self._cluster_save_info(cluster_uuid)

                return ""

            except Exception as e:
                return str(e)

    # -----------------------------------------------------------------------------
    #                                                                  Test Results
    #  --------------------------------------------------------------------------*/
    def cluster_test_execution_create(
        self, cluster_uuid: str, test_uuid: str, test_info: TestInfo, test_config: str, test_nodes: List[str]
    ) -> Tuple[str, Optional[str]]:
        with self.lock:
            # Check that the cluster exists
            cluster_info: ClusterInfo = None
            for cluster in self.cluster_entries:
                if cluster.uuid == cluster_uuid:
                    cluster_info = cluster

            if cluster_info is None:
                return f"Cluster with UUID {cluster_uuid} not found in the database.", None

            # Set the correct paths
            cluster_dir = os.path.join(self.config.storage_path, "clusters", cluster_uuid)
            executions_dir = os.path.join(cluster_dir, "executions")

            try:
                # Create an unique file name
                execution_uuid = str(uuid.uuid4())
                now = datetime.now().isoformat()
                new_execution_filename = f"{execution_uuid}.json"

                # Create the initial file contents
                contents: TestExecution = TestExecution(
                    test_info=test_info,
                    deployment_uuid=cluster_info.current_deployment,
                    test_config=test_config,
                    test_nodes=test_nodes,
                    started_at=now,
                    finished_at=now,
                    error="",
                    stopped=False,
                    results=[],
                )

                # Write the file
                new_execution_path = os.path.join(executions_dir, new_execution_filename)
                with open(new_execution_path, "w") as file:
                    json.dump(contents.marshal(), file, indent=4)

                # Update the cache
                cluster_info.executions.append(
                    TestExecutionInfo(
                        test_name=test_info.name, uuid=execution_uuid, error="", uploaded=False, created_at=now
                    )
                )

                # Update the filesystem
                self._cluster_save_info(cluster_uuid)
                return "", execution_uuid

            except Exception as e:
                return (
                    f"An error occurred while trying to create an execution instance in the database: {str(e)}",
                    None,
                )

    def cluster_test_execution_set_error(self, cluster_uuid: str, execution_uuid: str, error: str) -> str:
        with self.lock:
            # Check that the cluster exists
            cluster_info: ClusterInfo = None
            for cluster in self.cluster_entries:
                if cluster.uuid == cluster_uuid:
                    cluster_info = cluster
                    break

            if cluster_info is None:
                return f"Cluster with UUID {cluster_uuid} not found in the database."

            # Check that the execution instance exists
            execution_info: TestExecutionInfo = None
            for exec in cluster_info.executions:
                if exec.uuid == execution_uuid:
                    execution_info = exec
                    break

            if execution_info is None:
                return f"Test execution with UUID {execution_info} not found cluster {cluster_uuid}."

            # Define file paths
            cluster_dir = os.path.join(self.config.storage_path, "clusters", cluster_uuid)
            executions_dir = os.path.join(cluster_dir, "executions")
            execution_instance_file = os.path.join(executions_dir, f"{execution_uuid}.json")

            try:
                # Read the existing data
                with open(execution_instance_file, "r") as file:
                    data = json.load(file)
                    current_execution = TestExecution.unmarshal(data)

                # Update the error and the stopped status
                current_execution.error = error
                current_execution.stopped = True  # Assuming setting an error also means stopping the test

                # Update the finished_at time if not already set
                current_execution.finished_at = datetime.now().isoformat()

                # Write the updated data back to the file
                with open(execution_instance_file, "w") as file:
                    json.dump(current_execution.marshal(), file, indent=4)

                # Update the error in the high level entry
                execution_info.error = error
                self._cluster_save_info(cluster_uuid)
                return ""
            except Exception as e:
                return f"An error occurred while setting the error message: {str(e)}"

    def cluster_test_execution_append_result(
        self, cluster_uuid: str, execution_uuid: str, results: List[TestStepResult], stopped: bool
    ) -> str:
        with self.lock:
            # Check that the cluster exists
            cluster_info: ClusterInfo = None
            for cluster in self.cluster_entries:
                if cluster.uuid == cluster_uuid:
                    cluster_info = cluster
                    break

            if cluster_info is None:
                return f"Cluster with UUID {cluster_uuid} not found in the database."

            # Check that the execution instance exists
            execution_info: TestExecutionInfo = None
            for exec in cluster_info.executions:
                if exec.uuid == execution_uuid:
                    execution_info = exec
                    break

            if execution_info is None:
                return f"Test execution with UUID {execution_uuid} not found in cluster {cluster_uuid}."

            # Set the correct paths
            cluster_dir = os.path.join(self.config.storage_path, "clusters", cluster_uuid)
            executions_dir = os.path.join(cluster_dir, "executions")
            execution_instance_file = os.path.join(executions_dir, f"{execution_uuid}.json")

            try:
                # Read and update the execution data
                with open(execution_instance_file, "r") as file:
                    data = json.load(file)
                    current_execution = TestExecution.unmarshal(data)

                # Append the new results as a single group in the list of lists
                current_execution.results.append(results)
                if stopped:
                    current_execution.stopped = True

                # Check if there's an error in the results
                for result in results:
                    if result.error:
                        current_execution.error = result.error
                        execution_info.error = result.error
                        break  # We only need to set that first error, the user can investigate further afterwards

                # Always update the finished at time to the last step
                current_execution.finished_at = datetime.now().isoformat()

                # Write the updated data back to the file
                with open(execution_instance_file, "w") as file:
                    json.dump(current_execution.marshal(), file, indent=4)

                # Update the last updated timestamp and save changes
                self._cluster_save_info(cluster_uuid)
                return ""
            except Exception as e:
                return f"An error occurred while updating the test execution: {str(e)}"

    def cluster_test_execution_get(
        self, cluster_uuid: str, execution_uuid: str
    ) -> Tuple[str, Optional[TestExecution]]:
        with self.lock:
            # Check that the cluster exists
            cluster_info: ClusterInfo = None
            for cluster in self.cluster_entries:
                if cluster.uuid == cluster_uuid:
                    cluster_info = cluster
                    break

            if cluster_info is None:
                return f"Cluster with UUID {cluster_uuid} not found in the database.", None

            # Check that the execution instance exists
            execution_info: TestExecutionInfo = None
            for exec in cluster_info.executions:
                if exec.uuid == execution_uuid:
                    execution_info = exec
                    break

            if execution_info is None:
                return f"Test execution with UUID {execution_uuid} not found in cluster {cluster_uuid}.", None

            # Set the correct paths
            cluster_dir = os.path.join(self.config.storage_path, "clusters", cluster_uuid)
            executions_dir = os.path.join(cluster_dir, "executions")
            execution_instance_file = os.path.join(executions_dir, f"{execution_uuid}.json")

            try:
                # Read and update the execution data
                with open(execution_instance_file, "r") as file:
                    data = json.load(file)
                    current_execution = TestExecution.unmarshal(data)

                return "", current_execution
            except Exception as e:
                return f"An error occurred while updating the test execution: {str(e)}", None

    def cluster_test_execution_delete(self, cluster_uuid: str, execution_uuid: str) -> str:
        with self.lock:
            # Check that the cluster exists
            cluster_info = None
            for cluster in self.cluster_entries:
                if cluster.uuid == cluster_uuid:
                    cluster_info = cluster
                    break

            if cluster_info is None:
                return f"Cluster with UUID {cluster_uuid} not found in the database."

            # Check that the execution exists
            execution_to_delete = None
            for execution in cluster_info.executions:
                if execution.uuid == execution_uuid:
                    execution_to_delete = execution
                    break

            if execution_to_delete is None:
                return f"Execution with UUID {execution_uuid} not found in cluster {cluster_uuid}."

            # Attempt to remove the execution file from the filesystem
            try:
                executions_dir = os.path.join(self.config.storage_path, "clusters", cluster_uuid, "executions")
                execution_file_path = os.path.join(executions_dir, f"{execution_uuid}.json")

                if os.path.exists(execution_file_path):
                    os.remove(execution_file_path)
                else:
                    return f"No file found for execution with UUID {execution_uuid}."

                # Update the cache and remove the execution from the cluster_info
                cluster_info.executions.remove(execution_to_delete)

                # Update the filesystem
                self._cluster_save_info(cluster_uuid)

                return ""

            except Exception as e:
                return str(e)
