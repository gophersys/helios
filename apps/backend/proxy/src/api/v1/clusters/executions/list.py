# Standard includes
import logging
from typing import List

# 3rd party includes
from flask import Blueprint, jsonify

# App includes
from src.middleware.permissions import authMiddleware
from src.services.proxy import Cluster, appProxyServer

# Flask Route
clusters_executions_list_bp = Blueprint("clusters_executions_list", __name__)


@clusters_executions_list_bp.route("/v1/clusters/<cluster_uuid>/executions", methods=["GET"])
@authMiddleware.check_permissions(["Concord.Cluster.Executions.Read"])
def clusters_executions_list_handler(cluster_uuid):
    try:
        # Validate url parameters
        if cluster_uuid is None:
            return jsonify({"error": "Bad request, malformed url."}), 400

        # Find the specific cluster
        cluster: Cluster = None
        clusters: List[Cluster] = appProxyServer.clusters_get()
        for c in clusters:
            if c.info.uuid == cluster_uuid:
                cluster = c
                break

        if cluster is None:
            return jsonify({"error": f"Cluster {cluster_uuid} not found."}), 400

        # Construct a response list of deployments
        executions_info = []
        for executions in cluster.info.executions:
            executions_info.append(executions.marshal())

        # If everything is fine, return success status with deployments info
        return jsonify(executions_info), 200

    except Exception as e:
        logging.error(f"An error occurred: {str(e)}")
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500
