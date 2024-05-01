from flask import Blueprint, jsonify, send_file
import logging
import os

# Assuming proxy_server is already imported and initialized
from src.services.proxy import appProxyServer

# Define the Blueprint for the route
cluster_get_deployment_bp = Blueprint('cluster_get_deployment', __name__)

@cluster_get_deployment_bp.route('/v1/cluster/<uuid>/deployment/<deployment>', methods=['GET'])
def read_cluster_deployment(uuid, deployment):
    """
    Reads a cluster's deployment file based on the UUID provided in the URL path and the deployment name.
    """
    try:
        # Retrieve cluster information from proxy server
        error, cluster_info = appProxyServer.get_cluster_info(uuid)
        if error:
            return jsonify({"error": error}), 400

        # Extract the current deployment file path
        current_deployment_path = cluster_info.get('current_deployment')
        if not current_deployment_path:
            return jsonify({"error": "Current deployment information is missing"}), 404
        
        # Ensure the requested deployment is the current one
        deployment_filename = os.path.basename(current_deployment_path)
        if deployment != deployment_filename:
            return jsonify({"error": "Requested deployment does not match the current deployment"}), 404

        # Check if the file exists
        if not os.path.exists(current_deployment_path):
            return jsonify({"error": "Deployment file not found"}), 404

        # Read the file content
        with open(current_deployment_path, 'rb') as file:
            deployment_data = file.read()
        
        # Pack the response
        response = jsonify({
            "deployment_name": deployment_filename,
            "deployment_file_contents": deployment_data.decode('utf-8')
        })
        response.headers['Content-Type'] = 'application/json'
        return response, 200

    except Exception as e:
        logging.error(f"An error occurred: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500
