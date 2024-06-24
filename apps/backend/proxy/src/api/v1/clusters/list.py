# Standard includes
import logging
from typing import List

# 3rd party includes
from flask import Blueprint, jsonify

# Protocol includes
from protos.cluster_operator.cluster_operator_pb2 import ClusterStatus

# App includes
from src.middleware.permissions import authMiddleware
from src.services.proxy import Cluster, ClusterType, appProxyServer

# Flask Route
clusters_list_bp = Blueprint("clusters_list", __name__)


@clusters_list_bp.route("/v1/clusters", methods=["GET"])
@authMiddleware.check_permissions(["Concord.Cluster.View"])
def clusters_list_handler():
    try:
        # Route has no input

        # Call app
        clusters: List[Cluster] = appProxyServer.clusters_get()

        # Construct a response list of clusters
        clusters_response = []
        for cluster in clusters:
            # Set the status accordingly
            cluster_status: str = None
            if cluster.status is not None:
                cluster_status = ClusterStatus.Name(cluster.status)

            cluster_dict = {
                "name": cluster.info.name,
                "type": ClusterType.to_string(cluster.info.type),
                "uuid": cluster.info.uuid,
                "registered": cluster.info.registered,
                "currentDeployment": cluster.info.current_deployment,
                "status": cluster_status,
                "url": cluster.url,
            }
            clusters_response.append(cluster_dict)

        # If everything is fine, return success status with cluster info
        return jsonify({"clusters": clusters_response}), 200

    except Exception as e:
        logging.error(f"An error occurred: {str(e)}")
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500
