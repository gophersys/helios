from flask import Blueprint, jsonify
import logging

# Assuming proxy_server is already imported and initialized
from src.services.proxy import proxy_server

# Define the Blueprint for the route
cluster_read_bp = Blueprint('cluster_read', __name__)

@cluster_read_bp.route('/v1/clusters/<uuid>', methods=['GET'])  # Corrected the route parameter syntax
def read_cluster(uuid):
    """
    Reads a cluster's metadata based on the UUID provided in the URL path.
    """
    try:
        error, cluster_info = proxy_server.get_cluster_info(uuid)
        if error:
            return jsonify({"error": error}), 400
        else:
            return jsonify(cluster_info), 200

    except Exception as e:
        logging.error(f"An error occurred: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500
