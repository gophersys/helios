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
devices_save_pub_key_bp = Blueprint("devices_save_pub_key", __name__)


@devices_save_pub_key_bp.route("/v1/devices/keys/upload", methods=["POST"])
# @authMiddleware.check_permissions(["Concord.Devices.Read"])
def devices_save_pub_key_handler():
    try:
        # Access JSON data from the request
        data = request.get_json()

        # Validate request fields
        device_id = data.get("deviceId")
        if not device_id:
            return jsonify({"error": "Bad request, 'deviceId' field is required."}), 400

        pub_key = data.get("pubKey")
        if not pub_key:
            return jsonify({"error": "Bad request, 'pubKey' field is required."}), 400

        # Call Manufacturing server
        try:
            # Create the request body
            body = {"DeviceId": device_id, "PublicKey": pub_key}

            # Do request
            save_public_key_url = f"{conf.MANU_SERVER_URL}/devices/publickeys/save"
            response = requests.post(save_public_key_url, json=body, verify=None, timeout=5)

            if response.status_code == 200:
                return "", 200
            else:
                return (
                    jsonify(
                        {
                            "error": f'Manufacturing server call "{save_public_key_url}" failed ({response.status_code}): {str(response.content)}'
                        }
                    ),
                    response.status_code,
                )

        except Exception as e:
            return (
                jsonify({"error": f"An exception occurred assigning device id from Manufacturing server: {str(e)}"}),
                500,
            )

    except Exception as e:
        logging.error(f"An error occurred: {str(e)}")
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500
