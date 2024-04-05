# Standard includes
import logging

# 3rd party includes
from flask import Blueprint, jsonify, request 

# Application server
from src.server.proxy import ProxyServer

# Route blue print
cluster_register_bp = Blueprint('cluster_register', __name__)

# Handler
@cluster_register_bp.route('/v1/cluster/register', methods=['POST'])
def cluster_register():
    # Parse input data from the request body
    data = request.json
    
    # Input validation
    if not data or 'url' not in data or not isinstance(data['url'], str):
        return jsonify({"error": "Bad request, 'url' field is required and must be a string."}), 400
    
    cluster_url = data['url']
    
    # Register the cluster with the server
    if not ProxyServer().register_cluster(cluster_url):
        return "", 503
    
    # If everything is fine, return success status
    return jsonify({"message": "Cluster registered successfully."}), 200