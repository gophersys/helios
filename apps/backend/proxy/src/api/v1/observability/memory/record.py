# Standard includes
import logging
import requests
from typing import List
import uuid
import json
import datetime
import struct

# 3rd party includes
from flask import Blueprint, jsonify, request

# App includes
from config import conf
from src.middleware.permissions import authMiddleware
from src.services.proxy import appProxyServer
from src.services.database.schema import ObservabilityMemEntry

# Flask Route
observability_memory_measurement_bp = Blueprint("observability_memory_measurement", __name__)


@observability_memory_measurement_bp.route("/v1/observability/memory/<session_uuid>/measurement", methods=["POST"])
def observability_memory_measurement_handler(session_uuid):
    global read_count, write_count, erase_count

    try:
        data = request.get_data()
        if len(data) < 2:
            return jsonify({"error": "Invalid payload"}), 400

        event_count = struct.unpack("<H", data[:2])[0]
        events_data = data[2:]

        # Correct struct format string for 32-bit platform (24 bytes)
        format_string = "<8sIIIB3x"
        expected_size = event_count * struct.calcsize(format_string)
        if len(events_data) != expected_size:
            logging.error(f"Payload size does not match event count. Expected {expected_size}, got {len(events_data)}")
            return jsonify({"error": "Payload size does not match event count"}), 400

        measurements = []
        for i in range(event_count):
            offset = i * struct.calcsize(format_string)
            event = struct.unpack_from(format_string, events_data, offset)
            measurements.append(
                {
                    "operation": event[0].decode("utf-8").strip("\x00"),
                    "time": event[1],
                    "address": event[2],
                    "size": event[3],
                    "time_taken": event[4],
                }
            )

        # logging.warning(f"Received {event_count} measurements, length {len(data)} bytes")

        for measurement in measurements:
            entry = ObservabilityMemEntry(
                time=measurement["time"],
                operation=measurement["operation"],
                address=measurement["address"],
                size=measurement["size"],
                time_taken=measurement["time_taken"],
            )

            error = appProxyServer.db.obsv_mem_session_add_measurement(session_uuid, entry)
            if error:
                return jsonify({"error": error}), 500

        return "", 200

    except Exception as e:
        logging.error(f"An error occurred: {str(e)}")
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500
