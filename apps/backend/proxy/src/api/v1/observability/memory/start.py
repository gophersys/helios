# Standard includes
import logging
import requests
from typing import List
import uuid

# 3rd party includes
from flask import Blueprint, jsonify, request

# App includes
from config import conf
from src.middleware.permissions import authMiddleware
from src.services.proxy import appProxyServer

# Flask Route
observability_memory_start_bp = Blueprint("observability_memory_start", __name__)


@observability_memory_start_bp.route("/v1/observability/memory/start", methods=["POST"])
def observability_memory_start_handler():
    try:
        data = request.get_json()

        # Generate a UUID for the session
        session_id = str(uuid.uuid4())

        # Store session metadata in InfluxDB
        json_body = [{"measurement": "session_start", "tags": {"session_id": session_id}, "fields": data}]
        appProxyServer.influxdb_client.write_points(json_body)

        logging.info(f"Session started: {session_id}")

        # Return the session ID to the microcontroller
        return jsonify({"session_id": session_id}), 200

    except Exception as e:
        logging.error(f"An error occurred: {str(e)}")
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500
