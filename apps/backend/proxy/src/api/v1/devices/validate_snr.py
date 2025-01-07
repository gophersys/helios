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
devices_snr_validate_bp = Blueprint("devices_snr_validate", __name__)


@devices_snr_validate_bp.route("/v1/devices/snr/validate", methods=["POST"])
@authMiddleware.check_permissions(["Concord.Devices.Read"])
def devices_snr_validate_handler():
    try:
        # Access JSON data from the request
        data = request.get_json()

        # Validate request fields
        snr = data.get("snr")
        if not snr:
            return jsonify({"error": "Bad request, 'snr' field is required."}), 400

        singleton = data.get("singleton")
        if singleton is None:
            return jsonify({"error": "Bad request, 'singleton' field is required."}), 400

        # Call Manufacturing server
        snr_is_valid = False
        snr_references = [None] * 5
        try:
            # Create auth headers
            token_error, server_token = authMiddleware.get_server_token()
            if token_error:
                logging.error(f"A server error ocurred whilst getting access token: {token_error}")
                return jsonify({"error": f"{token_error}"}), 503

            # Prepare headers for the auth server request
            headers = {
                "X-API-KEY": authMiddleware.config.server_api_key,
                "Authorization": f"Bearer {server_token}",
            }

            search_board_srn_url = f"{conf.MANU_SERVER_URL}/boards/assemblies/Search?boardSerialNumber={snr}"
            response = requests.get(search_board_srn_url, headers=headers, timeout=5)

            if response.status_code == 200:
                response_data = response.json()
                panel_serial_number = response_data.get("panelSerialNumber")
                boards = response_data.get("boards", [])

                if panel_serial_number and len(boards) == 5:
                    snr_is_valid = True
                    for board in boards:
                        position = board.get("panelPosition")
                        serial_number = board.get("boardSerialNumber")
                        if 0 <= position < 5:
                            snr_references[position] = serial_number
                else:
                    return jsonify({"error": "Invalid response structure from Manufacturing server."}), 500
            else:
                return (
                    jsonify(
                        {
                            "error": f"Manufacturing server GET call failed ({response.status_code}): {str(response.content)}"
                        }
                    ),
                    response.status_code,
                )

        except Exception as e:
            return (
                jsonify(
                    {
                        "error": f"An exception occurred getting board serial numbers from Manufacturing server: {str(e)}"
                    }
                ),
                500,
            )

        # Form response
        if singleton and snr_is_valid:
            response = {"snrs": {"slot-6": snr}}
            return jsonify(response), 200

        if not snr_is_valid:
            return jsonify({"error": "Invalid serial number."}), 400

        response = {
            "snrs": {
                "slot-1": snr_references[0],
                "slot-2": snr_references[1],
                "slot-3": snr_references[2],
                "slot-4": snr_references[3],
                "slot-5": snr_references[4],
            }
        }

        return jsonify(response), 200

    except Exception as e:
        logging.error(f"An error occurred: {str(e)}")
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500
