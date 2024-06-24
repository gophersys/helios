# Standard includes
import logging

# 3rd party includes
from flask import Blueprint, jsonify

# App includes
from src.middleware.permissions import authMiddleware
from src.services.proxy import appProxyServer

# Flask Route
clusters_executions_delete_uuid_bp = Blueprint("clusters_executions_uuid_delete", __name__)


@clusters_executions_delete_uuid_bp.route(
    "/v1/clusters/<cluster_uuid>/executions/<execution_uuid>", methods=["DELETE"]
)
@authMiddleware.check_permissions(["Concord.Cluster.Executions.Delete"])
def clusters_executions_delete_uuid_handler(cluster_uuid, execution_uuid):
    try:
        # Validate url fields
        if not cluster_uuid or not execution_uuid:
            return jsonify({"error": "Bad request, malformed url."}), 400

        # Call app
        error = appProxyServer.cluster_test_executions_delete_one(cluster_uuid, execution_uuid)
        if error:
            logging.error(error)
            return jsonify({"error": error}), 400
        else:
            return "", 200

    except Exception as e:
        logging.error(f"An error occurred: {str(e)}")
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500
