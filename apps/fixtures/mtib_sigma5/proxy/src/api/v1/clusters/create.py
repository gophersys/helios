# 3rd party includes
from flask import Blueprint, request, jsonify

# Services
from src.services.proxy import proxy_server

# Define the Blueprint for the route
clusters_create_bp = Blueprint('clusters_create', __name__)

@clusters_create_bp.route('/v1/clusters', methods=['POST'])
def clusters_create_handler():
    # Access JSON data from the request
    data = request.get_json()
    
    
    # Validate request fields
    name = data.get('name')
    if not name:
        return jsonify({"error": "Bad request, 'name' field is required."}), 400

    type = data.get('type')
    if not type:
        return jsonify({"error": "Bad request, 'type' field is required."}), 400

    # Execute
    error, cluster_uuid = proxy_server.create_cluster(name, type)
    if error:
        return jsonify({"error": error}), 400

    return jsonify({"uuid": cluster_uuid}), 200