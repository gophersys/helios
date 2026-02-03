# Standard includes
import json
import logging
import queue
import threading
import time
import uuid
from typing import Any, Dict, List

from eventlet.queue import Empty, Queue
from flask import Blueprint, jsonify, request
from flask_socketio import SocketIO, close_room, disconnect, emit, join_room, leave_room

# 3rd party includes
from google.protobuf.json_format import MessageToDict

# Protocol includes
from protocols.cluster_operator.cluster_operator_pb2 import ClusterStatus
from protocols.cluster_test.cluster_test_pb2 import TestInfo, TestStepResult

# App includes
from src.middleware.permissions import authMiddleware
from src.services.proxy import Cluster, appProxyServer

# Shared message queue
message_queues: Dict[int, Queue] = {}
threads = {}

g_session_id = None


# Server callback
def test_result_callback(
    cluster_uuid: int, session_id: int, done: bool, stopped: bool, error: str, sequence: int, results: List[Any]
):
    if done:
        if error:
            logging.error(f"Execution {session_id} in cluster {cluster_uuid} ended with an error: {error}")
        else:
            logging.info(f"Execution {session_id} in cluster {cluster_uuid} ended successfully")

        if session_id in message_queues:
            # Create a dictionary with all the required data
            message = {
                "clusterUuid": cluster_uuid,
                "executionId": session_id,
                "done": done,
                "stopped": stopped,
                "error": error,
                "sequence": sequence,
                "results": [],
            }
            message_queues[session_id].put(message)
        return
    else:
        logging.debug(f"Received response for execution {session_id} in cluster {cluster_uuid}, sequence: {sequence}")

        # Marshal only the results array to a dictionary
        marshalled_results = [
            MessageToDict(result, always_print_fields_with_no_presence=True, preserving_proto_field_name=True)
            for result in results
        ]

        if session_id in message_queues:
            # Create a dictionary with all the required data
            message = {
                "clusterUuid": cluster_uuid,
                "executionId": session_id,
                "done": done,
                "stopped": stopped,
                "error": error,
                "sequence": sequence,
                "results": marshalled_results,
            }

            # Enqueue the message for the WebSocket handler
            message_queues[session_id].put(message)


# WebSocket Event Handler
def clusters_tests_exec_uuid_socketio_handler(data: Any, socketio: SocketIO):
    session_id = data["session_id"]
    join_room(session_id)

    def process_queue(session_id, socketio: SocketIO):
        # Create a new queue for this session if it doesn't exist
        if session_id not in message_queues:
            message_queues[session_id] = Queue()
        queue = message_queues[session_id]

        while True:
            try:
                message = queue.get(timeout=0.1)  # Use a timeout to avoid blocking
            except Empty:
                continue

            if message is None:
                break

            # Check if the done flag is set or if there is an error
            if message.get("done") or message.get("error"):
                socketio.emit("exec_test_response", message, room=session_id)
                break

            socketio.emit("exec_test_response", message, room=session_id)

        socketio.close_room(session_id)
        # Clean up the queue after processing
        del message_queues[session_id]

    # Start background task for processing the queue
    socketio.start_background_task(target=process_queue, session_id=session_id, socketio=socketio)


# Flask Route
clusters_tests_exec_uuid_bp = Blueprint("clusters_tests_exec_uuid", __name__)


@clusters_tests_exec_uuid_bp.route("/v1/clusters/<cluster_uuid>/tests/<test_uuid>/exec", methods=["POST"])
@authMiddleware.check_permissions(["Concord.Cluster.Tests.Execute"])
def clusters_tests_exec_uuid_handler(cluster_uuid, test_uuid):
    try:
        # Validate url fields
        if not cluster_uuid or not test_uuid:
            return jsonify({"error": "Bad request, malformed url."}), 400

        # Access JSON data from the request
        data = request.get_json(silent=True)  # Use silent=True to avoid parsing errors
        if not data:
            return jsonify({"error": "Bad request, no JSON payload."}), 400

        # Validate request fields
        test_config = json.dumps(data.get("config", {}))

        requested_nodes = data.get("nodes", [])  # Default to empty list if 'nodes' is not provided
        if len(requested_nodes) == 0:
            return (
                jsonify({"error": "Bad request, 'nodes' field is required and must contain at least one node."}),
                400,
            )

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
            return jsonify({"error": f"Cluster {cluster_uuid} is not connected, cannot execute test"}), 400
        elif cluster.status is ClusterStatus.RUNNING:
            return jsonify({"error": f"Cluster {cluster_uuid} is already running a test"}), 400
        elif cluster.status is ClusterStatus.ERRORED:
            return jsonify({"error": f"Cluster {cluster_uuid} is in errored state, cannot execute test"}), 400

        # Get nodes information
        error, nodes_info = appProxyServer.clusters_get_nodes_info(cluster.info.uuid)
        if error:
            return jsonify({"error": f"{error}"}), 400

        # Check that the nodes in the request are present in the nodes_info
        available_hosts = {node.host for node in nodes_info}  # Assuming each node info has a 'host' attribute
        missing_nodes = [node for node in requested_nodes if node not in available_hosts]
        if missing_nodes:
            return jsonify({"error": f"Requested nodes not found: {', '.join(missing_nodes)}"}), 400

        # Generate a unique session ID for this test execution
        error, execution_id = appProxyServer.clusters_test_exec(
            cluster_uuid, test_uuid, test_config, requested_nodes, test_result_callback
        )
        if error:
            return jsonify({"error": f"{error}"}), 400

        return jsonify({"executionId": execution_id}), 202

    except Exception as e:
        logging.error(f"An error occurred: {str(e)}")
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500
