from typing import List
import os
import logging
import uuid
import json
from json.decoder import JSONDecodeError

from typing import Tuple, Optional
import shutil

from dataclasses import dataclass, field, asdict
from datetime import datetime

@dataclass
class DeploymentUpdate:
    timestamp: str
    deployment_file: str

    def to_dict(self):
        return {
            "timestamp": self.timestamp,
            "deployment_file": self.deployment_file   
        }

@dataclass
class ClusterEntry:
    name: str
    uuid: str
    created_at: str
    last_updated_at: str
    current_deployment: str
    deployment_updates: List[DeploymentUpdate] = field(default_factory=list)

    def to_dict(self):
        deployment_updates_dicts = []
        for update in self.deployment_updates:
            if isinstance(update, DeploymentUpdate):
                deployment_updates_dicts.append(update.to_dict())
            elif isinstance(update, dict):
                deployment_updates_dicts.append(update)  # Already a dict, no conversion needed
            else:
                logging.error(f"Unexpected type in deployment_updates: {type(update)}")
        return {
            "name": self.name,
            "uuid": self.uuid,
            "created_at": self.created_at,
            "last_updated_at": self.last_updated_at,
            "current_deployment": self.current_deployment,
            "deployment_updates": deployment_updates_dicts,
        }


class ProxyServerDatabase:
    def __init__(self, database_path: str):
        self.path: str = database_path
        self.clusters: List[ClusterEntry] = []

    def init(self) -> str:
        err = self.__init_clusters()
        if err:
            return f"Could not initialize clusters from database: {err}"
        return ""

    def __init_clusters(self) -> str:
        """
        The cluster file system contains 2 folders per cluster, a deployments folder containing
        information about the current deployment and its updates, and a logs folder used to
        periodically synchronize logs from the remote servers.

        The goal of this function is to create a list of clusters in the database with their UUIDs
        for further operations.

        db_dir/
        ├── clusters/
        │   ├── cluster_uuid_1/
        │   │   ├── deployments/
        │   │   │   ├── info.json
        │   │   │   ├── deployment_a.yaml
        │   │   │   ├── deployment_b.yaml
        │   │   ├── logs/
        │   │   │   ├── log_mm_dd_ss/
        """
        logging.debug("Reading known clusters from filesystem")
        clusters_dir = os.path.join(self.path, 'clusters')
        if not os.path.exists(clusters_dir):
            logging.debug("No clusters present in database")
            return ""

        for cluster_uuid in os.listdir(clusters_dir):
            logging.debug(f"Found cluster {cluster_uuid}")
            info_path = os.path.join(clusters_dir, cluster_uuid, 'deployments', 'info.json')
            if os.path.exists(info_path):
                try:
                    with open(info_path, 'r') as file:
                        cluster_info = json.load(file)
                        cluster = ClusterEntry(**cluster_info)
                        self.clusters.append(cluster)
                except JSONDecodeError:
                    logging.warning(f"Invalid JSON in {info_path}. Skipping cluster.")
                    continue  # Skip this cluster and move to the next
            else:
                logging.warning(f"No info.json found for cluster {cluster_uuid}. Skipping cluster.")
                continue

        return ""

    def get_cluster_uuids(self) -> List[str]:
        """
        Returns a list of all cluster UUIDs currently stored in the database.
        """
        return self.cluster_uuids

    def create_cluster(self, cluster_name: str, deployment: str) -> Tuple[str, Optional[str]]:
        """Create a new cluster entry in the file system"""
        for cluster in self.clusters:
            if cluster.name == cluster_name:
                return f"Cluster \"{cluster_name}\" is already present in server", None

        cluster_uuid = str(uuid.uuid4())
        cluster_dir = os.path.join(self.path, 'clusters', cluster_uuid)
        deployments_dir = os.path.join(cluster_dir, 'deployments')
        logs_dir = os.path.join(cluster_dir, 'logs')

        try:
            os.makedirs(deployments_dir, exist_ok=True)
            os.makedirs(logs_dir, exist_ok=True)

            deployment_uuid = str(uuid.uuid4())  # Unique identifier for the deployment
            deployment_filename = f"{deployment_uuid}.yaml"  # Unique deployment file name

            deployment_path = os.path.join(deployments_dir, deployment_filename)
            shutil.copy(deployment, deployment_path)

            now = datetime.now().isoformat()
            cluster_info = ClusterEntry(
                name=cluster_name,
                uuid=cluster_uuid,
                created_at=now,
                last_updated_at=now,
                current_deployment=deployment_path,
                deployment_updates=[DeploymentUpdate(timestamp=now, deployment_file=deployment_path)]
            )

            self.clusters.append(cluster_info)

            info_path = os.path.join(deployments_dir, 'info.json')
            with open(info_path, 'w') as file:
                json.dump(cluster_info.to_dict(), file, indent=4)

            return "", cluster_uuid
        except Exception as e:
            return f"Error creating cluster: {e}", None
        
    def delete_cluster(self, cluster_uuid: str) -> str:
        """Deletes a cluster folder and all its deployments from the database."""
        cluster_dir = os.path.join(self.path, 'clusters', cluster_uuid)
        try:
            for cluster in self.clusters:
                if cluster.uuid == cluster_uuid:
                    shutil.rmtree(cluster_dir)
                    self.clusters.remove(cluster)
                    return ""
            return f"Cluster with UUID {cluster_uuid} not found in the database."
        except Exception as e:
            return str(e)

    def update_cluster_deployment(self, cluster_uuid: str, new_deployment: str) -> str:
        """Updates an existing cluster entry in the file system"""
        cluster_dir = os.path.join(self.path, 'clusters', cluster_uuid)
        deployments_dir = os.path.join(cluster_dir, 'deployments')
        info_path = os.path.join(deployments_dir, 'info.json')

        try:
            if cluster_uuid not in self.cluster_uuids:
                return f"Cluster with UUID {cluster_uuid} not found in the database."

            cluster_info = self._load_cluster_info(info_path)

            update_uuid = str(uuid.uuid4())[:8]  # Short identifier for the update
            now = datetime.now().isoformat(timespec='seconds').replace(':', '-')  # More filesystem-friendly
            new_deployment_filename = f"deployment_{now}_{update_uuid}.yaml"  # Unique filename

            new_deployment_path = os.path.join(deployments_dir, new_deployment_filename)
            shutil.copy(new_deployment, new_deployment_path)

            cluster_info.last_updated_at = now
            cluster_info.current_deployment = new_deployment_path
            cluster_info.deployment_updates.append(DeploymentUpdate(timestamp=now, deployment_file=new_deployment_path))

            self._save_cluster_info(cluster_info, info_path)
            return ""
        except Exception as e:
            return str(e)

    def get_cluster_info(self, cluster_uuid: str) -> Tuple[str, Optional[dict]]:
        """Retrieves information about a specific cluster identified by its UUID."""
        try:
            for cluster in self.clusters:
                if cluster.uuid == cluster_uuid:
                    # Ensure 'cluster' is an instance of ClusterEntry before calling to_dict
                    if isinstance(cluster, ClusterEntry):
                        logging.warning("Yep indeed its the right type")
                        return "", cluster.to_dict() 
                    else:
                        # Log or handle the unexpected type
                        return f"Unexpected type for cluster object. Expected ClusterEntry, got {type(cluster)}", None
            return f"Cluster with UUID {cluster_uuid} not found in the database", None
        except Exception as e:
            return str(e), None

    def get_latest_deployment(self, cluster_uuid: str) -> str:
        """
        Returns the path to the latest deployment file for the given cluster UUID.
        If the cluster UUID is not found or there are no deployments available,
        it returns an empty string.
        """
        cluster_dir = os.path.join(self.path, 'clusters', cluster_uuid)
        deployments_dir = os.path.join(cluster_dir, 'deployments')
        info_path = os.path.join(deployments_dir, 'info.json')

        try:
            if cluster_uuid not in self.cluster_uuids:
                return ""

            cluster_info = self._load_cluster_info(info_path)
            return cluster_info.current_deployment
        except Exception as e:
            logging.error(f"Error getting latest deployment for cluster {cluster_uuid}: {str(e)}")
            return ""
    
    def _load_cluster_info(self, info_path: str) -> ClusterEntry:
        """Load cluster information from the info.json file"""
        with open(info_path, 'r') as f:
            data = json.load(f)
        return ClusterEntry(
            uuid=data['uuid'],
            created_at=data['created_at'],
            last_updated_at=data['last_updated_at'],
            current_deployment=data['current_deployment'],
            deployment_updates=[DeploymentUpdate(**update) for update in data['deployment_updates']]
        )

    def _save_cluster_info(self, cluster_info: ClusterEntry, info_path: str):
        """Save cluster information to the info.json file"""
        data = {
            'uuid': cluster_info.uuid,
            'created_at': cluster_info.created_at,
            'last_updated_at': cluster_info.last_updated_at,
            'current_deployment': cluster_info.current_deployment,
            'deployment_updates': [update.__dict__ for update in cluster_info.deployment_updates]
        }
        with open(info_path, 'w') as f:
            json.dump(data, f, indent=4)