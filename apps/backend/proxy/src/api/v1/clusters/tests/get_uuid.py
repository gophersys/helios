# Standard includes
import json
import logging
from typing import List

# 3rd party includes
from flask import Blueprint, jsonify
from google.protobuf.json_format import MessageToDict

# Protocol includes
from protos.cluster_test.cluster_test_pb2 import TestInfo

# App includes
from src.middleware.permissions import authMiddleware
from src.services.proxy import Cluster, appProxyServer

# Flask Route
clusters_tests_get_uuid_bp = Blueprint("clusters_tests_get_uuid", __name__)


@clusters_tests_get_uuid_bp.route("/v1/clusters/<cluster_uuid>/tests/<test_uuid>", methods=["GET"])
@authMiddleware.check_permissions(["Concord.Cluster.Tests.Read"])
def clusters_tests_get_uuid_handler(cluster_uuid, test_uuid):
    try:
        # Validate url fields
        if not cluster_uuid or not test_uuid:
            return jsonify({"error": "Bad request, malformed url."}), 400

        # Find the specific cluster
        cluster: Cluster = None
        clusters: List[Cluster] = appProxyServer.clusters_get()
        for c in clusters:
            if c.info.uuid == cluster_uuid:
                cluster = c
                break

        if cluster is None:
            return jsonify({"error": f"Cluster {cluster_uuid} not found."}), 400

        # Check the state of the cluster before we do anything
        if cluster.status is None:
            return jsonify({"error": f"Cluster {cluster_uuid} is not connected."}), 400

        # Get the list of tests from the cluster
        error, tests = appProxyServer.clusters_tests_get(cluster_uuid)
        if error:
            logging.error(error)
            return jsonify({"error": f"error"}), 400

        # Find the specific test
        test: TestInfo = None
        for t in tests:
            if t.uuid == test_uuid:
                test = t
                break

        if test is None:
            return jsonify({"error": f"Test {test_uuid} not found in cluster {cluster_uuid}"}), 400

        test_response = {
            "uuid": test.uuid,
            "name": test.name,
            "defaultConfig": json.loads(test.defaultConfig),
            "description": test.description,
            "steps": [
                [
                    MessageToDict(step, always_print_fields_with_no_presence=True, preserving_proto_field_name=True)
                    for step in test.steps
                ]
            ],
        }

        # If everything is fine, return success status with deployment info
        return jsonify(test_response), 200

    except Exception as e:
        logging.error(f"An error occurred: {str(e)}")
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500
