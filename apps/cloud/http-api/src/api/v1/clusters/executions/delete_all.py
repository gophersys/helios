# Standard includes
import logging

# 3rd party includes
from flask import Blueprint, jsonify, request

# App includes
from config import env_config
from src.middleware.permissions import authMiddleware
from src.services.proxy import appProxyServer

# Flask Route
clusters_executions_delete_all_bp = Blueprint("clusters_executions_delete_all", __name__)


@clusters_executions_delete_all_bp.route("/v1/clusters/<cluster_uuid>/executions", methods=["DELETE"])
@authMiddleware.check_permissions(["Concord.Cluster.Executions.Delete"])
def clusters_deployments_delete_all_handler(cluster_uuid):
    try:
        # Validate url fields
        if not cluster_uuid:
            return jsonify({"error": "Bad request, malformed url."}), 400

        # Access JSON data from the request
        data = request.get_json()

        # Validate request fields
        key = data.get("magic-key")
        if not key:
            return (
                jsonify(
                    {"error": "You're missing the magic key. Careful! This really does delete all the executions"}
                ),
                400,
            )

        if key != env_config.DELETE_ALL_KEY:  # <- Update confluence if you change this
            return jsonify({"error": "Wrong key. Careful! This really does delete all the executions!"}), 400

        # Call app
        error = appProxyServer.cluster_test_executions_delete_all(cluster_uuid)
        if error:
            logging.error(error)
            return jsonify({"error": error}), 400
        else:
            return "", 200

    except Exception as e:
        logging.error(f"An error occurred: {str(e)}")
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500
