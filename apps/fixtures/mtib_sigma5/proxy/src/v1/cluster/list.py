# Standard includes
import logging
from typing import List

# 3rd party includes
from flask import Blueprint, jsonify, request 

# Application server
from src.proxy import ProxyServer, TestCluster, ClusterStatus

# Route blue print
cluster_list_bp = Blueprint('cluster_list', __name__)

# Handler
@cluster_list_bp.route('/v1/cluster/list', methods=['GET'])
def cluster_register():
    # Route has no input
    
    # Register the cluster with the server
    clusters:List[TestCluster] = ProxyServer().get_clusters()

    # Construct a response list of clusters
    clusters_response = []
    for cluster in clusters:
        cluster_dict = {
            "uuid": cluster.uuid,
            "url": cluster.url,
            "status": ClusterStatus.Name(cluster.status),  # Converts enum value to its name
            "error": cluster.error
        }

        clusters_response.append(cluster_dict)

    # If everything is fine, return success status with cluster info
    return jsonify({"clusters": clusters_response}), 200