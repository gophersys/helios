# Standard includes
import logging
from typing import List

# 3rd party includes
from flask import Blueprint, jsonify

# Protocol includes
from protocols.cluster_operator.cluster_operator_pb2 import ClusterStatus, NodeInfo
from src.services.database.schema import DeploymentInfo, TestExecutionInfo

# App includes
from src.middleware.permissions import authMiddleware
from src.services.proxy import ClusterType, appProxyServer

# Flask Route
clusters_get_uuid_bp = Blueprint("clusters_get_uuid", __name__)


@clusters_get_uuid_bp.route("/v1/clusters/<uuid>", methods=["GET"])
@authMiddleware.check_permissions(["Concord.Cluster.View"])
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
        cluster_status = ClusterStatus.Name(cluster.status) if cluster.status is not None else None

        # Marshall individual lists
        deployments = [DeploymentInfo.marshal(deployment) for deployment in cluster.info.deployments]
        executions = [TestExecutionInfo.marshal(execution) for execution in cluster.info.executions]

        # Construct a response object
        cluster_response = {
            "uuid": cluster.info.uuid,
            "name": cluster.info.name,
            "type": ClusterType.to_string(cluster.info.type),
            "status": cluster_status,
            "createdAt": cluster.info.created_at,
            "lastUpdatedAt": cluster.info.last_updated_at,
            "registered": cluster.info.registered,
            "currentDeployment": cluster.info.current_deployment,
            "deployments": deployments,
            "logs": cluster.info.logs,
            "results": executions,
            "error": cluster.error,
            "url": cluster.url,
            "nodes": [
                {
                    "name": node.name,
                    "host": node.host,
                    "osImage": node.os_image,
                    "kernelVersion": node.kernel_version,
                    "cpuCores": node.cpu_cores,
                    "memoryUsedBytes": node.memory_used_bytes,
                    "memoryCapacityBytes": node.memory_capacity_bytes,
                    "storageUsedBytes": node.storage_used_bytes,
                    "storageCapacityBytes": node.storage_capacity_bytes,
                }
                for node in nodes_info
            ],
        }

        # Return successful response with cluster details
        return jsonify(cluster_response), 200

    except Exception as e:
        logging.error(f"An error occurred: {str(e)}")
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500
