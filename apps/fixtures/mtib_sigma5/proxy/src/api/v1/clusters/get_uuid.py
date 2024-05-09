# Standard includes
import logging
from typing import List

# 3rd party includes
from flask import Blueprint, jsonify

# Protocol includes
from protos.cluster_operator.cluster_operator_pb2 import (
    ClusterStatus, NodeInfo
)

# App includes
from src.services.proxy import appProxyServer, ClusterType

# Flask Route
clusters_get_uuid_bp = Blueprint('clusters_get_uuid', __name__)
@clusters_get_uuid_bp.route('/v1/clusters/<uuid>', methods=['GET'])
def clusters_get_uuid_handler(uuid):
    try:
        # Validate UUID
        if not uuid:
            return jsonify({"error": "Bad request, malformed URL."}), 400

        # Retrieve all clusters
        clusters = appProxyServer.clusters_get()
        cluster = next((c for c in clusters if c.info.uuid == uuid), None)

        if not cluster:
            return jsonify({"error": f"Cluster {uuid} not found in server."}), 404

        # Get nodes information
        error, nodes_info = appProxyServer.clusters_get_nodes_info(cluster.info.uuid)
        if error:
            return jsonify({"error": f"{error}"}), 400
    
        # Set the status
        cluster_status = ClusterStatus.Name(cluster.status) if cluster.status else None

        # Construct a response object
        cluster_response = {
            "uuid": cluster.info.uuid,
            "name": cluster.info.name,
            "type": ClusterType.to_string(cluster.info.type),
            "status": cluster_status,
            "created_at": cluster.info.created_at,
            "last_updated_at": cluster.info.last_updated_at,
            "registered": cluster.info.registered,
            "current_deployment": cluster.info.current_deployment,
            "deployments": cluster.info.deployments,
            "logs": cluster.info.logs,
            "results": cluster.info.results,
            "error": cluster.error,
            "url": cluster.url,
            "nodes": [
                {
                    "name": node.name,
                    "hostname": node.hostname,
                    "os_image": node.os_image,
                    "kernel_version": node.kernel_version,
                    "cpu_cores": node.cpu_cores,
                    "memory_used_bytes": node.memory_used_bytes,
                    "memory_capacity_bytes": node.memory_capacity_bytes,
                    "storage_used_bytes": node.storage_used_bytes,
                    "storage_capacity_bytes": node.storage_capacity_bytes,
                } for node in nodes_info
            ]
        }

        # Return successful response with cluster details
        return jsonify(cluster_response), 200

    except Exception as e:
        logging.error(f"An error occurred: {str(e)}")
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500