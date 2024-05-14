# Standard includes
import os
import logging

# 3rd party includes
from flask import Blueprint, jsonify, send_file

# App includes
from src.services.proxy import appProxyServer

# Flask Route
clusters_executions_get_uuid_bp = Blueprint('clusters_executions_get_uuid', __name__)
@clusters_executions_get_uuid_bp.route('/v1/clusters/<cluster_uuid>/executions/<executions_uuid>', methods=['GET'])
def clusters_executions_get_uuid_handler(cluster_uuid, executions_uuid):
    try:
        # Validate url fields
        if not cluster_uuid or not executions_uuid:
            return jsonify({"error": "Bad request, malformed url."}), 400
        
        # Call app
        error, execution = appProxyServer.clusters_test_execution_get(cluster_uuid, executions_uuid)
        if error:
            logging.error(error)
            return jsonify({"error": error}), 400
        
        # Send the file as the response
        return jsonify(execution.marshal()), 400
    
    except Exception as e:
        logging.error(f"An error occurred: {str(e)}")
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500