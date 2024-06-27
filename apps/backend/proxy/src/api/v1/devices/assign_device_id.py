# standard includes
import logging
import requests
from typing import List

# 3rd party includes
from flask import Blueprint, jsonify, request

# App includes
from config import conf
from src.middleware.permissions import authMiddleware
from src.services.proxy import appProxyServer

# Flask Route
devices_assign_id_bp = Blueprint("devices_assign_id", __name__)


@devices_assign_id_bp.route("/v1/devices/ids/assign", methods=["POST"])
# @authMiddleware.check_permissions(["Concord.Devices.Read"])
def devices_assign_id_handler():
    try:
        # Access JSON data from the request
        data = request.get_json()

        # Validate request fields
        snr = data.get("snr")
        if not snr:
            return jsonify({"error": "Bad request, 'snr' field is required."}), 400

        # Call Manufacturing server
        device_id: str = None
        try:
            assign_device_id_to_board_url = f"{conf.MANU_SERVER_URL}/devices/ids/assign?boardSerialNumber={snr}"
            response = requests.post(assign_device_id_to_board_url, verify=None, timeout=5)

            if response.status_code == 200:
                response_data = response.json()
                device_id = response_data.get("deviceId")
            else:
                return (
                    jsonify(
                        {
                            "error": f'Manufacturing server call "{assign_device_id_to_board_url}" failed ({response.status_code}): {str(response.content)}'
                        }
                    ),
                    response.status_code,
                )

        except Exception as e:
            return (
                jsonify({"error": f"An exception occurred assigning device id from Manufacturing server: {str(e)}"}),
                500,
            )

        response = {"deviceId": device_id}

        return jsonify(response), 200

    except Exception as e:
        logging.error(f"An error occurred: {str(e)}")
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500
