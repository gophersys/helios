# standard includes
import os
import logging

# 3rd party includes
from uuid import uuid4
from flask import Blueprint, request, jsonify
from werkzeug.utils import secure_filename

# App includes
from src.services.proxy import appProxyServer

# Flask Route
clusters_deployments_create_bp = Blueprint('clusters_deployments_create', __name__)
@clusters_deployments_create_bp.route('/v1/clusters/<uuid>/deployments', methods=['POST'])
def clusters_deployments_create_handler(uuid):
    try:
        # Validate url fields
        if not uuid:
            return jsonify({"error": "Bad request, malformed url."}), 400

        # Access JSON data from the request
        file = request.files.get('file')
        if not file:
            return jsonify({"error": "Bad request, 'file' field is required."}), 400

         # Generate a unique filename and save it to a temporary folder for post-processing
        unique_filename = secure_filename(f"{uuid4()}-{file.filename}")
        temp_file_path = os.path.join('/tmp', unique_filename)
        file.save(temp_file_path)
        
        # Call App
        error, cluster_uuid = appProxyServer.deployment_create(uuid, temp_file_path)
        
        os.remove(temp_file_path) # Delete the temporary file created regardless of request success
        
        if error:
            logging.error(error)
            return jsonify({"error": error}), 400

        return jsonify({"uuid": cluster_uuid}), 200

    except Exception as e:
        logging.error(f"An error occurred: {str(e)}")
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500