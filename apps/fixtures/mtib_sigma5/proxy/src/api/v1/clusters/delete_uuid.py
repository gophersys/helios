# Standard includes
import logging
import os
import uuid
from typing import Tuple, Dict, Any

# 3rd party includes
from werkzeug.utils import secure_filename
from flask import Blueprint, jsonify, request, Request, Response

# Server services
from src.services.proxy import proxy_server

# Route blue print
clusters_delete_uuid_bp = Blueprint('clusters_uuid_delete', __name__)

@clusters_delete_uuid_bp.route('/v1/clusters/<uuid>', methods=['DELETE'])
def clusters_delete_uuid_handler(uuid):
    """
    Deletes a cluster based on the UUID provided in the URL path.
    """
    try:
        if not uuid:
            return jsonify({"error": "UUID is required"}), 400

        error = proxy_server.delete_cluster(uuid)
        if error:
            return jsonify({"error": error}), 400
        else:
            return "", 200

    except Exception as e:
        logging.error(f"An error occurred: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500