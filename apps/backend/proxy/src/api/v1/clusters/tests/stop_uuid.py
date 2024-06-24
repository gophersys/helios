# Standard includes
import json
import logging
import queue
import threading
import time
import uuid
from typing import Any, List

# 3rd party includes
from flask import Blueprint, jsonify, request
from flask_socketio import SocketIO, close_room, disconnect, emit, join_room

# Protocol includes
from protos.cluster_operator.cluster_operator_pb2 import ClusterStatus
from protos.cluster_test.cluster_test_pb2 import TestInfo, TestStepResult

# App includes
from src.middleware.permissions import authMiddleware
from src.services.proxy import Cluster, appProxyServer

# Shared message queue
message_queue = queue.Queue()

# Flask Route
clusters_tests_stop_uuid_bp = Blueprint("clusters_tests_stop_uuid", __name__)


@clusters_tests_stop_uuid_bp.route("/v1/clusters/<cluster_uuid>/tests/<test_uuid>/stop", methods=["POST"])
@authMiddleware.check_permissions(["Concord.Cluster.Tests.Stop"])
def clusters_tests_exec_uuid_handler(cluster_uuid, test_uuid):
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

        # Check that the cluster is connected
        if cluster.status is None:
            return jsonify({"error": f"Cluster {cluster_uuid} is not connected, cannot stop test"}), 400
        elif cluster.status is ClusterStatus.ERRORED:
            return jsonify({"error": f"Cluster {cluster_uuid} is in errored state, cannot execute test"}), 400

        # Generate a unique session ID for this test execution
        error = appProxyServer.clusters_test_stop(cluster_uuid, test_uuid)
        if error:
            return jsonify({"error": f"{error}"}), 400

        return "", 202

    except Exception as e:
        logging.error(f"An error occurred: {str(e)}")
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500
