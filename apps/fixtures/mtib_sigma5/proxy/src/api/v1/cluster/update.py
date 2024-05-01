# Standard includes
import logging
import os
import uuid as _uuid
from werkzeug.utils import secure_filename
from typing import Tuple, Dict, Any

# 3rd party includes
from werkzeug.utils import secure_filename
from flask import Blueprint, jsonify, request, Request, Response

# Server services
from src.services.proxy import appProxyServer

# Route blue print
cluster_update_bp = Blueprint('cluster_update', __name__)

@cluster_update_bp.route('/v1/cluster/<uuid>', methods=['PATCH'])
def update_cluster(uuid):
    """ Updates the cluster deployment. """
    try:
        if not uuid:
            return jsonify({"error": "UUID is required"}), 400

        deployment_file = request.files.get('deployment_file')
        if not deployment_file:
            return jsonify({"error": "Bad request, 'deployment_file' field is required."}), 400

         # Save the deployment file with a unique name
        unique_filename = f"{_uuid.uuid4().hex}_{secure_filename(deployment_file.filename)}"
        temp_dir = '/tmp'
        os.makedirs(temp_dir, exist_ok=True)
        temp_file_path = os.path.join(temp_dir, unique_filename)
        deployment_file.save(temp_file_path)

        error = appProxyServer.update_cluster(uuid, temp_file_path)
        if error:
            return jsonify({"error": error}), 400
        else:
            return "", 200
    except Exception as e:
        logging.error(f"An error occurred: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500