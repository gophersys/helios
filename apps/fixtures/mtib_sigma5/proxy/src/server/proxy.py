import logging
import grpc
import uuid
import time
import threading

# Assuming protos are already correctly imported
from protos.mtib_controller.mtib_controller_pb2 import (
    HealthCheckRequest, HealthCheckResponse
)
from protos.mtib_controller.mtib_controller_pb2_grpc import MtibControllerStub

# TODO: Create types for cluster information, and general purpose metadata, etc.

class ProxyServer:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(ProxyServer, cls).__new__(cls, *args, **kwargs)
            cls.clusters = {}  # Initialize the cluster list as a dictionary

            # Start the health check thread
            health_check_thread = threading.Thread(target=cls._instance.perform_health_checks, daemon=True)
            health_check_thread.start()
        return cls._instance

    def perform_health_checks(self):
        """Periodically check the health of each cluster."""
        while True:
            for cluster_id, cluster_info in list(self.clusters.items()):
                try:
                    stub = cluster_info['stub']
                    response: HealthCheckResponse = stub.HealthCheck(HealthCheckRequest())
                    if not response.ok:
                        logging.error(f"Health check failed for cluster {cluster_id}, error: {response.error}")
                except grpc.RpcError as e:
                    logging.error(f"Failed to perform health check on cluster {cluster_id}. Error: {e}")
                    self.remove_cluster(cluster_id)

            time.sleep(5)

    def add_cluster(self, cluster_url) -> bool:
        """Add a new cluster to the server"""

        # Check if the cluster is already connected
        for cluster_id, cluster_info in self.clusters.items():
            if cluster_info['url'] == cluster_url:
                return True

        logging.info(f"Connecting to cluster at {cluster_url}...")

        # Create a gRPC channel
        channel = grpc.insecure_channel(cluster_url)

        try:
            stub = MtibControllerStub(channel)

            # If connection is successful, generate a UUID for the cluster and store its info
            cluster_id = str(uuid.uuid4())
            self.clusters[cluster_id] = {
                'url': cluster_url,
                'stub': stub,
                'status': 'connected'  # Maintain a status variable
            }

            logging.info(f"Successfully connected to the cluster with ID {cluster_id}!")
            return True

        except grpc.RpcError as e:
            logging.error(f"Failed to connect to cluster at {cluster_url}. Error: {e}")
            return False

    def get_cluster(self, cluster_id):
        """Get a cluster's information by ID."""
        return self.clusters.get(cluster_id)

    def remove_cluster(self, cluster_id):
        """Remove a cluster from the list by ID."""
        if cluster_id in self.clusters:
            del self.clusters[cluster_id]
            logging.info(f"Cluster with ID {cluster_id} removed.")

    def get_all_clusters(self):
        """Return a list of all clusters."""
        return self.clusters
