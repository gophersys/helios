# Standard includes
import logging

# 3rd party includes
from flask import Blueprint, jsonify

# App includes
from src.services.proxy import appProxyServer

# Flask Route
clusters_deployments_delete_uuid_bp = Blueprint('clusters_deployment_uuid_delete', __name__)
@clusters_deployments_delete_uuid_bp.route('/v1/clusters/<cluster_uuid>/deployments/<deployment_uuid>', methods=['DELETE'])
def clusters_deployments_delete_uuid_handler(cluster_uuid, deployment_uuid):
    try:
        # Validate url fields
        if not cluster_uuid or not deployment_uuid:
            return jsonify({"error": "Bad request, malformed url."}), 400

        # Call app
        error = appProxyServer.deployment_delete_one(cluster_uuid, deployment_uuid)
        if error:
            logging.error(error)
            return jsonify({"error": error}), 400
        else:
            return "", 200

    except Exception as e:
        logging.error(f"An error occurred: {str(e)}")
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500