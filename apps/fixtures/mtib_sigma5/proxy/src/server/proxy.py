import logging
import grpc
import uuid
import time
import threading
from typing import List, Tuple, Optional

# Assuming protos are already correctly imported
from protos.mtib_controller.mtib_controller_pb2 import (
    ClusterStatus, HealthCheckRequest, HealthCheckResponse,
    ClusterInfo, GetClusterInfoRequest, GetClusterInfoResponse,
)
from protos.mtib_controller.mtib_controller_pb2_grpc import MtibControllerStub

class ClusterItem:
    status:ClusterStatus = ClusterStatus.NotReady
    error:str = None

    def __init__(self, uuid:str, url: str, stub:MtibControllerStub, info:ClusterInfo):
        self.uuid:str = uuid
        self.url:str = url
        self.stub:MtibControllerStub = stub
        self.info:ClusterInfo = info

class ProxyServer:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(ProxyServer, cls).__new__(cls, *args, **kwargs)
            cls.clusters:List[ClusterItem] = []

            # Start the health check thread
            health_check_thread = threading.Thread(target=cls._instance.__perform_health_checks, daemon=True)
            health_check_thread.start()
        return cls._instance

    def __perform_health_checks(self):
        """Periodically check the health of each cluster."""
        while True:
            for cluster in self.clusters:
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
    #                                                                                  Register Cluster
    # -----------------------------------------------------------------------------------------------*/
    def register_cluster(self, cluster_url:str) -> bool:
        """Register a new cluster to the server"""

        # Check if the cluster is already connected
        for cluster in self.clusters:
            if cluster.url == cluster_url:
                return True
            
        logging.info(f"Connecting to cluster at {cluster_url}...")

        try:            
            # Create a gRPC channel
            channel = grpc.insecure_channel(cluster_url)

            # Create a stub using the insecure channel
            stub = MtibControllerStub(channel)

            # Get cluster metadata
            try:
                response:GetClusterInfoResponse = stub.GetClusterInfo(request=GetClusterInfoRequest())
                if response.info is not None:

                    # Register the cluster with the proxy server (us)
                    new_cluster_item = ClusterItem(
                        uuid=str(uuid.uuid4()),
                        url=cluster_url,
                        stub = stub,
                        info=response.info
                    )
                    self.clusters.append(new_cluster_item)

            except grpc.RpcError as e:
                logging.error(f"Unable to register cluster at {cluster_url}: {e}")
                return False

            logging.info(f"Successfully registered cluster at {cluster_url}!")
            return True

        except grpc.RpcError as e:
            logging.error(f"Failed to connect to cluster at {cluster_url}. Error: {e}")
            return False

    # -------------------------------------------------------------------------------------------------
    #                                                                                      Get Clusters
    # -----------------------------------------------------------------------------------------------*/
    def get_clusters(self) -> List[ClusterItem]:
        """Get a cluster's information by ID."""
        return self.clusters
    
    # -------------------------------------------------------------------------------------------------
    #                                                                                  Get Cluster Info
    # -----------------------------------------------------------------------------------------------*/
    def get_cluster_info(self, cluster_uuid: str) -> Tuple[bool, Optional[ClusterInfo]]:
        """Get a cluster's information by UUID."""
        for cluster in self.clusters:
            if cluster.uuid == cluster_uuid:
                return True, cluster.info
        return False, None

    # -------------------------------------------------------------------------------------------------
    #                                                                                      Get Clusters
    # -----------------------------------------------------------------------------------------------*/
    def remove_cluster(self, cluster_id):
        """Remove a cluster from the list by ID."""
        for cluster in self.clusters:
            if cluster.uuid == cluster_id:
                self.clusters.remove(cluster)
                logging.info(f"Cluster with ID {cluster_id} removed.")
                return