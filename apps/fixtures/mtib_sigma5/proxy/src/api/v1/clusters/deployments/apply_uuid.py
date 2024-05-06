# Standard includes
import logging

# 3rd party includes
from flask import Blueprint, request, jsonify

# App includes
from src.services.proxy import appProxyServer

# Flask Route
clusters_deployments_apply_uuid_bp = Blueprint('clusters_deployments_apply', __name__)
@clusters_deployments_apply_uuid_bp.route('/v1/clusters/<cluster_uuid>/deployments/<deployment_uuid>/apply', methods=['POST'])
def clusters_deployments_apply_uuid_handler(cluster_uuid, deployment_uuid):
    try:
        # Validate url fields
        if not cluster_uuid or not deployment_uuid:
            return jsonify({"error": "Bad request, malformed url."}), 400

        # Tell the proxy a new cluster is trying to register itself
        error = appProxyServer.clusters_deployments_apply(cluster_uuid, deployment_uuid)
        if error:
            logging.error(error)
            return jsonify({"error": error}), 400
        else:
            return "", 200

    except Exception as e:
        logging.error(f"An error occurred: {str(e)}")
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500