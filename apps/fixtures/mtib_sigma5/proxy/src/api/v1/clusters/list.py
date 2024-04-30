# Standard includes
from typing import List

# 3rd party includes
from flask import Blueprint, jsonify, request 

# Services
from src.services.proxy import proxy_server, TestCluster, TestClusterStatus

# Define the Blueprint for the route
clusters_list_bp = Blueprint('clusters_list', __name__)
@clusters_list_bp.route('/v1/clusters', methods=['GET'])
def clusters_list_handler():
    # Route has no input
    
    clusters:List[TestCluster] = proxy_server.list_clusters()

    # Construct a response list of clusters
    clusters_response = []
    for cluster in clusters:
        cluster_dict = {
            "name": cluster.name,
            "type": cluster.type,
            "uuid": cluster.uuid,
            "registered": cluster.registered,
            "status": TestClusterStatus.to_human_readable(cluster.status),
            "url": cluster.url
        }
        clusters_response.append(cluster_dict)

    # If everything is fine, return success status with cluster info
    return jsonify({"clusters": clusters_response}), 200