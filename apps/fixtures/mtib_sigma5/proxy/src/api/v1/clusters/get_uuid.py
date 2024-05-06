# Standard includes
import logging
from typing import List

# 3rd party includes
from flask import Blueprint, jsonify

# App includes
from src.services.proxy import appProxyServer, Cluster, ClusterStatus, ClusterType

# Flask Route
clusters_get_uuid_bp = Blueprint('clusters_get_uuid', __name__)
@clusters_get_uuid_bp.route('/v1/clusters/<uuid>', methods=['GET'])
def clusters_get_uuid_handler(uuid):
    try:
        # Validate url fields
        if not uuid:
            return jsonify({"error": "Bad request, malformed url."}), 400
        
        # Call app
        clusters:List[Cluster] = appProxyServer.clusters_get()
        
        # Get the cluster at question
        cluster:Cluster = None
        for c in clusters:
            if c.info.uuid == uuid:
                cluster = c
                break
            
        if cluster is None:
            return jsonify({"error": f"Cluster {uuid} not found in server."}), 400
        
        # Construct a response list of clusters
        cluster_response = {
            "status": ClusterStatus.to_string(cluster.status),
            "error": cluster.error,
            "url": cluster.url,
            "info": cluster.info.marshal()
        }

        # If everything is fine, return success status with cluster info
        return jsonify(cluster_response), 200
    
    except Exception as e:
        logging.error(f"An error occurred: {str(e)}")
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500