# Standard includes
import logging
from typing import List

# 3rd party includes
from flask import Blueprint, jsonify

# App includes
from src.services.proxy import appProxyServer, Cluster, ClusterStatus, ClusterType

# Flask Route
clusters_list_bp = Blueprint('clusters_list', __name__)
@clusters_list_bp.route('/v1/clusters', methods=['GET'])
def clusters_list_handler():
    try:
        # Route has no input
        
        # Call app
        clusters:List[Cluster] = appProxyServer.clusters_get()

        # Construct a response list of clusters
        clusters_response = []
        for cluster in clusters:
            cluster_dict = {
                "name": cluster.info.name,
                "type": ClusterType.to_string(cluster.info.type),
                "uuid": cluster.info.uuid,
                "registered": cluster.info.registered,
                "current_deployment": cluster.info.current_deployment,
                "status": ClusterStatus.to_string(cluster.status),
                "url": cluster.url,
            }
            clusters_response.append(cluster_dict)

        # If everything is fine, return success status with cluster info
        return jsonify({"clusters": clusters_response}), 200
    
    except Exception as e:
        logging.error(f"An error occurred: {str(e)}")
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500