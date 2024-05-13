# Standard includes
import logging
from typing import List, Any
import uuid
import threading
import time
import json
import queue

# 3rd party includes
from flask import Blueprint, jsonify, request
from flask_socketio import SocketIO, join_room, emit, close_room, disconnect

# Protocol includes
from protos.cluster_operator.cluster_operator_pb2 import  ClusterStatus
from protos.cluster_test.cluster_test_pb2 import TestInfo

# App includes
from src.services.proxy import appProxyServer, Cluster

# Shared message queue
message_queue = queue.Queue()

# Server callback
def test_result_callback(data: Any, session_id: str):
    logging.error(f"session_id: {data}, Received response: {data}")
    # Put the test update and session_id into the queue
    # emit('server', {'data': "some data"}, room=session_id)
    # message_queue.put((session_id, data))
    # if data['done']:
    #     # Also enqueue a message to close the room after the test is complete
    #     message_queue.put((session_id, {'message': 'Test completed', 'action': 'close'}))

# SocketIO event handler
def clusters_tests_exec_uuid_socketio_handler(data: Any, socketio:SocketIO):
    session_id = data['session_id']
    join_room(session_id)
    for x in range(5):
        # logging.info("Sending message")
        # emit('server', {'data': "some data"}, room=session_id)
        time.sleep(1)
    close_room(session_id)
    
# Flask Route
clusters_tests_exec_uuid_bp = Blueprint('clusters_tests_exec_uuid', __name__)
@clusters_tests_exec_uuid_bp.route('/v1/clusters/<cluster_uuid>/tests/<test_uuid>/exec', methods=['POST'])
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
        test_config = json.dumps(data.get('config', {}))

        requested_nodes = data.get('nodes', [])  # Default to empty list if 'nodes' is not provided
        if len(requested_nodes) == 0:
            return jsonify({"error": "Bad request, 'nodes' field is required and must contain at least one node."}), 400
        
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
        error, session_id = appProxyServer.clusters_test_exec(cluster_uuid, test_uuid, test_config, requested_nodes, test_result_callback)
        if error:
            return jsonify({"error": f"{error}"}), 400
        
        return jsonify({"message": "Test execution started", "session_id": session_id}), 202
    
    except Exception as e:
        logging.error(f"An error occurred: {str(e)}")
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500
    

# Ensure to pass socketio instance when registering the blueprint in main.py
