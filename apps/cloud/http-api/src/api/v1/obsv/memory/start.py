# Standard includes
import logging
import requests
from typing import List
import uuid
import json

# 3rd party includes
from flask import Blueprint, jsonify, request

# App includes
from src.middleware.permissions import authMiddleware
from src.services.proxy import appProxyServer
from src.services.database.schema import ObservabilityMemMetadata

# Flask Route
obsv_memory_start_bp = Blueprint("obsv_memory_start", __name__)


@obsv_memory_start_bp.route("/v1/obsv/memory/start", methods=["POST"])
def obsv_memory_start_handler():
    try:
        data = request.get_json()

        # Generate a UUID for the session
        session_id = str(uuid.uuid4())

        logging.info(f"Session started: {session_id}")

        # Create the ObservabilityMemMetadata object from the JSON data
        metadata = ObservabilityMemMetadata(
            data_bytes_per_page=data["data_bytes_per_page"],
            spare_bytes_per_page=data["spare_bytes_per_page"],
            pages_per_block=data["pages_per_block"],
            blocks_per_lu=data["blocks_per_lu"],
            num_lus=data["num_lus"],
        )

        # Call the obsv_mem_session_create function
        result = appProxyServer.db.obsv_mem_session_create(session_id, metadata)

        if result:
            return jsonify({"error": result}), 500

        # Return the session ID to the microcontroller
        return jsonify({"session_id": session_id}), 200

    except Exception as e:
        logging.error(f"An error occurred: {str(e)}")
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500
