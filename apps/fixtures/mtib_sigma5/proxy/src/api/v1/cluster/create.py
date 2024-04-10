from flask import Blueprint, request, jsonify
import os
import uuid
from werkzeug.utils import secure_filename

# Assuming proxy_server is already imported and initialized
from src.services.proxy import proxy_server

# Define the Blueprint for the route
cluster_create_bp = Blueprint('cluster_create', __name__)

@cluster_create_bp.route('/v1/cluster', methods=['POST'])
def create_cluster():
    # Validate input
    name = request.form.get('name')
    if not name:
        return jsonify({"error": "Bad request, 'name' field is required."}), 400

    deployment_file = request.files.get('deployment_file')
    if not deployment_file:
        return jsonify({"error": "Bad request, 'deployment_file' field is required."}), 400

    # Save the deployment file with a unique name
    unique_filename = f"{uuid.uuid4().hex}_{secure_filename(deployment_file.filename)}"
    temp_dir = '/tmp'
    os.makedirs(temp_dir, exist_ok=True)
    temp_file_path = os.path.join(temp_dir, unique_filename)
    deployment_file.save(temp_file_path)

    # Execute the creation logic
    error, cluster_uuid = proxy_server.create_cluster(name, temp_file_path)
    if error:
        return jsonify({"error": error}), 400

    return jsonify({"uuid": cluster_uuid}), 200
