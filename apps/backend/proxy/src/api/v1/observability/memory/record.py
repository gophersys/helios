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
observability_memory_measurement_bp = Blueprint("observability_memory_measurement", __name__)

read_count = 0
write_count = 0
erase_count = 0


@observability_memory_measurement_bp.route("/v1/observability/memory/measurement", methods=["POST"])
def observability_memory_measurement_handler():
    global read_count, write_count, erase_count

    try:
        logging.warn(request)
        data = request.get_json()
        session_id = data.get("session_id")

        if not session_id:
            return jsonify({"error": "Session ID is required"}), 400

        measurements = data.get("measurements", [])

        if not measurements:
            return jsonify({"error": "Measurements are required"}), 400

        json_body = []
        for measurement in measurements:
            operation = measurement.get("operation")
            if operation == "read":
                read_count += 1
            elif operation == "write":
                write_count += 1
            elif operation == "erase":
                erase_count += 1

            json_body.append(
                {
                    "measurement": "memory_operations",
                    "tags": {"session_id": session_id, "operation": operation},
                    "fields": {
                        "address": measurement.get("address"),
                        "size": measurement.get("size"),
                        "time_taken": measurement.get("time_taken"),
                    },
                }
            )

        appProxyServer.influxdb_client.write_points(json_body)

        logging.info(f"Batch of measurements recorded for session {session_id}")
        logging.info(f"Read operations count: {read_count}")
        logging.info(f"Write operations count: {write_count}")
        logging.info(f"Erase operations count: {erase_count}")

        return "", 200

    except Exception as e:
        logging.error(f"An error occurred: {str(e)}")
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500
