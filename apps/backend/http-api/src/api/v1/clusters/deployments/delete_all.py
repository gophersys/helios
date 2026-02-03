# standard includes
import logging

# 3rd party includes
from flask import Blueprint, jsonify

# App includes
from src.middleware.permissions import authMiddleware
from src.services.proxy import appProxyServer

# Flask Route
clusters_deployments_delete_all_bp = Blueprint("clusters_deployments_delete", __name__)


@clusters_deployments_delete_all_bp.route("/v1/clusters/<cluster_uuid>/deployments", methods=["DELETE"])
@authMiddleware.check_permissions(["Concord.Cluster.Deployment.Delete"])
def clusters_delete_all_handler(cluster_uuid):
    try:
        # Validate url parameters
        if not cluster_uuid:
            return jsonify({"error": "Bad request, malformed url."}), 400

        # Call app
        error = appProxyServer.cluster_deployments_delete_all(cluster_uuid)
        if error:
            logging.error(error)
            return jsonify({"error": error}), 400
        else:
            return "", 200

    except Exception as e:
        logging.error(f"An error occurred: {str(e)}")
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500
