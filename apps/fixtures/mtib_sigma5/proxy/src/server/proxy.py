import logging

class ProxyServer:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(ProxyServer, cls).__new__(cls, *args, **kwargs)
            cls.clusters = {}  # Initialize the cluster list
        return cls._instance

    def add_cluster(self, cluster_id, cluster_info):
        """Add or update a cluster's information."""
        logging.info(f"Adding cluster {cluster_id} with info {cluster_info}")
        self.clusters[cluster_id] = cluster_info

    def get_cluster(self, cluster_id):
        """Get a cluster's information by ID."""
        return self.clusters.get(cluster_id)

    def remove_cluster(self, cluster_id):
        """Remove a cluster from the list by ID."""
        if cluster_id in self.clusters:
            del self.clusters[cluster_id]

    def get_all_clusters(self):
        """Return a list of all clusters."""
        return self.clusters

