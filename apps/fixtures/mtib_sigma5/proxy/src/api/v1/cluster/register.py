from flask import Blueprint, request, jsonify
import os
import logging
import uuid
from werkzeug.utils import secure_filename

# Assuming proxy_server is already imported and initialized
from src.services.proxy import proxy_server

# Define the Blueprint for the route
cluster_register_bp = Blueprint('cluster_register', __name__)

@cluster_register_bp.route('/v1/clusters/<uuid>/register', methods=['POST'])
def register_cluster(uuid):
    try:
        if not uuid:
            return jsonify({"error": "UUID is required"}), 400

        # Get the required fields from the request
        request_data = request.get_json()
        cluster_url = request_data.get('url')
        if not cluster_url:
            return jsonify({"error": "Bad request, 'url' field is required."}), 400

        # Tell the proxy a new cluster is trying to register itself
        error = proxy_server.register_cluster(uuid, cluster_url)
        if error:
            return jsonify({"error": error}), 400
        else:
            return "", 200

    except Exception as e:
        logging.error(f"An error occurred: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500