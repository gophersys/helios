import logging
from flask import Blueprint, jsonify, request  # Import `request` to access request data

from src.server.proxy import ProxyServer

cluster_register_bp = Blueprint('cluster_register', __name__)

@cluster_register_bp.route('/v1/cluster/register', methods=['POST'])
def cluster_register():
    # Parse input data from the request body
    data = request.json
    cluster_id = data.get('cluster_id')  # Assuming 'cluster_id' is a key in your request JSON
    cluster_info = data.get('cluster_info')  # 'cluster_info' should contain all necessary cluster information
    
    # Use parsed data to add the cluster
    ProxyServer().add_cluster(cluster_id, cluster_info)
    
    # Return a response indicating success
    return jsonify(status="Registered", cluster_id=cluster_id), 200
