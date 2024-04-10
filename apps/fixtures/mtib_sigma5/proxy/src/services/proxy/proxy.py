import logging
import grpc
import uuid
import shutil
import os
import time
import json
from datetime import datetime
import threading
from typing import List, Tuple, Optional

from config import conf

# Assuming protos are already correctly imported
from protos.mtib_controller.mtib_controller_pb2 import (
    ClusterStatus, HealthCheckRequest, HealthCheckResponse,
    ClusterInfo, GetClusterInfoRequest, GetClusterInfoResponse,
    TestInfo, ListTestsRequest, ListTestsResponse,
    ExecuteTestRequest
)
from protos.mtib_controller.mtib_controller_pb2_grpc import MtibControllerStub

# Private includes
from .db import ProxyServerDatabase

class TestCluster:
    def __init__(self,
                uuid:str,
                url: str,
                stub:MtibControllerStub,
                info:ClusterInfo,
                connected_at:str):
        self.uuid:str = uuid
        self.url:str = url
        self.stub:MtibControllerStub = stub
        self.info:ClusterInfo = info
        self.status:ClusterStatus = ClusterStatus.NotReady
        self.error:str = ""
        self.connected_at:str = ""

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
    def create_cluster(self, name:str, deployment:str) -> Tuple[str, Optional[str]]:
        """
        Create a new cluster in the server's database. If there's a cluster with the same name already
        registered, function will return false
        """
        return self.db.create_cluster(name, deployment)

    # -------------------------------------------------------------------------------------------------
    #                                                                                  Register Cluster
    # -----------------------------------------------------------------------------------------------*/
    def register_cluster(self, cluster_uuid, cluster_url:str) -> str:
        """
        Register a new cluster to the server
        """

        # Check if the cluster has already been created
        cluster_created:bool = False
        for uuid in self.db.get_cluster_uuids():
            if uuid == cluster_uuid:
                cluster_created = True
                logging.debug("cluster")
                break
        
        if not cluster_created:
            return f"Cluster {cluster_uuid} at {cluster_url} was not found in server"

        # Check if the cluster is already connected
        for cluster in self.connected_clusters:
            if cluster.url == cluster_url:
                return True
        
        # Get initial metadata
        success, error, cluster = self.__get_cluster_info(cluster_url)
        if not success:
            return False, f"Unable to get cluster info: {error}. Did you "
        
        # Check if we have a deployment for this cluster
        success, error, found, deployment_path = self.__find_cluster_deployment()
        if not success:
            return False, f"An error ocurred trying to find a deployment for cluster: {error}"
        
        if not found:
            return False, f"No deployment was found for cluster {cluster.uuid} at {cluster.url}"
    
    def __get_cluster_info(self, cluster_url:str) -> Tuple[bool, str, Optional[TestCluster]]:
        try:            
            # Create a gRPC channel
            channel = grpc.insecure_channel(cluster_url)

            # Create a stub using the insecure channel
            stub = MtibControllerStub(channel)

            # Get cluster metadata over the gRPC connection
            try:
                response:GetClusterInfoResponse = stub.GetClusterInfo(request=GetClusterInfoRequest())
                if response.info is not None:

                    # Register the cluster with the proxy server (us), with enough information
                    # to execute actions on it
                    new_cluster = TestCluster(
                        uuid=str(uuid.uuid4()),
                        url=cluster_url,
                        stub = stub,
                        info=response.info,
                        connected_at=datetime.now().isoformat()
                    )
                    self.connected_clusters.append(new_cluster)

            except grpc.RpcError as e:
                logging.error(f"Unable to register cluster at {cluster_url}: {e}")
                return False

            logging.info(f"Successfully registered cluster at {cluster_url}!")
            return True

        except grpc.RpcError as e:
            logging.error(f"Failed to connect to cluster at {cluster_url}. Error: {e}")
            return False
        
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
    def get_cluster_info(self, cluster_uuid: str) -> Tuple[bool, Optional[ClusterInfo]]:
        """Get a cluster's information by UUID."""
        for cluster in self.connected_clusters:
            if cluster.uuid == cluster_uuid:
                return True, cluster.info
        return False, None

    # -------------------------------------------------------------------------------------------------
    #                                                                                      Get Clusters
    # -----------------------------------------------------------------------------------------------*/
    def get_cluster_tests(self, cluster_uuid: str) -> Tuple[bool, str, Optional[List[TestInfo]]]:
        """Get a cluster's information by UUID."""
        for cluster in self.connected_clusters:
            if cluster.uuid == cluster_uuid:
                try:
                    response:ListTestsResponse = cluster.stub.ListTests(ListTestsRequest())
                    return True, "", response.tests
                except grpc.RpcError as e:
                    return False, f"Unable to get cluster tests at {cluster.url}: {e}", None

        return False, f"Cluster {cluster_uuid} was not found in proxy", None
    
    # -------------------------------------------------------------------------------------------------
    #                                                                                         Exec Test
    # -----------------------------------------------------------------------------------------------*/
    def exec_cluster_test(self, cluster_uuid: str, test_uuid: str, runner_ids: List[int]) -> Tuple[bool, str]:
        for cluster in self.connected_clusters:
            if cluster.uuid == cluster_uuid:
                logging.warning(f"found cluster {cluster_uuid}")
                try:
                    logging.warning("executing request")
                    # Create the request object properly
                    request = ExecuteTestRequest(testId=test_uuid, runnerIds=runner_ids)
                    # Call the ExecuteTest method with the request
                    response_stream = cluster.stub.ExecuteTest(request)
                    logging.warning("Before entering response_stream loop")
                    for response in response_stream:
                        logging.warning(f"Received response: {response}")
                    return True, ""
                except grpc.RpcError as e:
                    logging.error(f"RPC Error: {e}")
                    return False, str(e)

    # -------------------------------------------------------------------------------------------------
    #                                                                                      Get Clusters
    # -----------------------------------------------------------------------------------------------*/
    def remove_cluster(self, cluster_id):
        """Remove a cluster from the list by ID."""
        for cluster in self.connected_clusters:
            if cluster.uuid == cluster_id:
                self.connected_clusters.remove(cluster)
                logging.info(f"Cluster with ID {cluster_id} removed.")
                return
            
proxy_server:ProxyServer = ProxyServer(conf.DB_PATH) 