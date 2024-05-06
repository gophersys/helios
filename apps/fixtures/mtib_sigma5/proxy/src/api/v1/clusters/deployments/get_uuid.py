# Standard includes
import os
import logging

# 3rd party includes
from flask import Blueprint, jsonify, send_file

# App includes
from src.services.proxy import appProxyServer

# Flask Route
clusters_deployments_get_uuid_bp = Blueprint('clusters_deployments_get_uuid', __name__)
@clusters_deployments_get_uuid_bp.route('/v1/clusters/<cluster_uuid>/deployments/<deployment_uuid>', methods=['GET'])
def clusters_deployments_get_uuid_handler(cluster_uuid, deployment_uuid):
    try:
        # Validate url fields
        if not cluster_uuid or not deployment_uuid:
            return jsonify({"error": "Bad request, malformed url."}), 400
        
        # Call app
        error, file_path = appProxyServer.cluster_deployments_get_path(cluster_uuid, deployment_uuid)
        if error:
            logging.error(error)
            return jsonify({"error": error}), 400

        # Send the file as the response
        return send_file(
            path_or_file=file_path,
            as_attachment=True,  # Force download
            download_name=f"{deployment_uuid}.yaml"
        )
    
    except Exception as e:
        logging.error(f"An error occurred: {str(e)}")
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500