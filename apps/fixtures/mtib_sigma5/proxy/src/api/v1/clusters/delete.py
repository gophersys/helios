# 3rd party includes
from flask import Blueprint, jsonify

# Server services
from src.services.proxy import proxy_server

# Route blue print
clusters_delete_bp = Blueprint('clusters_delete', __name__)
@clusters_delete_bp.route('/v1/clusters', methods=['DELETE'])
def clusters_delete_handler():
    error = proxy_server.delete_clusters()
    if error:
        return jsonify({"error": error}), 400
    else:
        return "", 200