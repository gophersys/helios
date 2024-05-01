# Standard includes
import logging
from typing import List

# 3rd party includes
from flask import Blueprint, jsonify, request 

# Application server
from src.services.proxy import appProxyServer, TestInfo

# Route blue print
cluster_tests_list_bp = Blueprint('tests_list', __name__)

# Handler
@cluster_tests_list_bp.route('/v1/cluster/<cluster_uuid>/tests', methods=['GET'])
def tests_list(cluster_uuid):
    # Route has no input
    
    # Register the cluster with the server
    tests:List[TestInfo] 
    error, tests = appProxyServer.get_cluster_tests(cluster_uuid)
    if error:
        return jsonify({"error": f"Unable to read tests from cluster: {error}"}), 404

    # Construct a response list of clusters
    tests_response = {
        # Convert TestInfo into a JSON-serializable dict
        "tests": [
            {
                "name": test.name,
                "description": test.description,
                "steps": [
                    # Convert StepInfo into a JSON-serializable dict
                    {
                        "sequence": step.sequence,
                        "name": step.name,
                        "description": step.description
                    }
                    for step in test.steps # Iterating over repeated StepInfo
                ]
            }
            for test in tests # Iterating over repeated TestInfo
        ]
    }

    # If everything is fine, return success status with cluster info
    return jsonify({"tests": tests_response}), 200