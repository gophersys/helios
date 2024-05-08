# Standard includes
import logging
from typing import List

# 3rd party includes
from flask import Blueprint, jsonify

# App includes
from src.services.proxy import appProxyServer, Cluster

# Flask Route
clusters_tests_list_bp = Blueprint('clusters_tests_list', __name__)
@clusters_tests_list_bp.route('/v1/clusters/<cluster_uuid>/tests', methods=['GET'])
def clusters_tests_list_handler(cluster_uuid):
    try:
        # Validate url parameters
        if cluster_uuid is None:
            return jsonify({"error": "Bad request, malformed url."}), 400
        
        # Find the specific cluster
        cluster:Cluster = None
        clusters:List[Cluster] = appProxyServer.clusters_get()
        for c in clusters:
            if c.info.uuid == cluster_uuid:
                cluster = c
                break
        
        if cluster is None:
            return jsonify({"error": f"Cluster {cluster_uuid} not found."}), 400

        # Get the list of tests from the cluster
        error, tests = appProxyServer.clusters_tests_get(cluster_uuid)
        if error:
            logging.error(error)
            return jsonify({"error": f"error"}), 400
        
        # Serialize TestInfo and StepInfo to JSON-compatible dictionaries
        tests_response = [{
            "uuid": test.uuid,
            "name": test.name,
            "description": test.description,
            "step_count": len(test.steps)
        } for test in tests]
        
        # If everything is fine, return success status with deployments info
        return jsonify(tests_response), 200
    
    except Exception as e:
        logging.error(f"An error occurred: {str(e)}")
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500