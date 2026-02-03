# standard includes
import logging
from collections import OrderedDict
from typing import List

import requests

# App includes
from config import env_config

# 3rd party includes
from flask import Blueprint, jsonify, request
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
        snr_references = [None] * 4
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

            search_board_srn_url = f"{env_config.COREOPS_SERVER_URL}/boards/assemblies/search?boardSerialNumber={snr}"
            response = requests.get(search_board_srn_url, verify=None, timeout=5, headers=headers)

            if response.status_code == 200:
                response_data = response.json()
                panel_serial_number = response_data.get("panelSerialNumber")
                boards = response_data.get("boards", [])

                # Singleton devices have 1 board, panels have 4
                if singleton and len(boards) >= 1:
                    snr_is_valid = True
                elif panel_serial_number and len(boards) == 4:
                    snr_is_valid = True
                    for board in boards:
                        position = board.get("panelPosition")
                        serial_number = board.get("boardSerialNumber")
                        if 0 <= position < 4:
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
            # Sigma5 app
            response = {
                "snrs": OrderedDict(
                    [
                        ("verdin-imx8mm-15005679", snr),
                    ]
                ),
            }

            # # Theta app
            # response = {
            #     "snrs": OrderedDict(
            #         [
            #             ("verdin-imx8mm-15702161", snr),
            #         ]
            #     ),
            # }

            return jsonify(response), 200

        if not snr_is_valid:
            return jsonify({"error": "Invalid serial number."}), 400

        # response = {
        #     "snrs": {
        #         "slot-1": snr_references[0],
        #         "slot-2": snr_references[1],
        #         "slot-3": snr_references[2],
        #         "slot-4": snr_references[3],
        #         "slot-5": snr_references[4],
        #     }
        # }

        # TODO: Remove this once we have a proper way to validate SNRS
        # per cluster

        # Sort SNR values alphabetically while keeping hostnames in order
        # Filter out None values and manually sort
        valid_snrs = [snr for snr in snr_references if snr is not None]

        # Use the actual sorted array
        sorted_snrs = sorted(valid_snrs)

        # Sigma 5
        # response = {
        #     "snrs": OrderedDict(
        #         [
        #             ("verdin-imx8mm-15005658", sorted_snrs[4]),  # 05AU - .11 // 9160 yes, 52840 yes, POST yes
        #             ("verdin-imx8mm-15005689", sorted_snrs[3]),  # 05AV - .9  // 9160 yes, 52840 yes, POST yes
        #             ("verdin-imx8mm-15005817", sorted_snrs[2]),  # 05AW - .13 // 9160 yes, 52840 yes, POST yes
        #             ("verdin-imx8mm-15005816", sorted_snrs[1]),  # 05AX - .10 // 9160 yes, 52840 yes, POST yes // cook
        #             ("verdin-imx8mm-15005665", sorted_snrs[0]),  # 05AY - .6  // 9160 yes, 52840 yes, POST yes
        #         ]
        #     ),
        # }

        # # Theta
        # response = {
        #     "snrs": OrderedDict(
        #         [
        #             ("verdin-imx8mm-15005816", sorted_snrs[2]),  # Slot 1 - .33
        #             ("verdin-imx8mm-15005817", sorted_snrs[3]),  # Slot 2 - .34
        #             ("verdin-imx8mm-15005658", sorted_snrs[0]),  # Slot 3 - .35
        #             ("verdin-imx8mm-15005689", sorted_snrs[1]),  # Slot 4 - .36
        #         ]
        #     ),
        # }

        # Alpha
        response = {
            "snrs": OrderedDict(
                [
                    ("verdin-imx8mm-15005816", sorted_snrs[1]),  # Slot 1 - .33
                    ("verdin-imx8mm-15005817", sorted_snrs[0]),  # Slot 2 - .34
                    ("verdin-imx8mm-15005658", sorted_snrs[3]),  # Slot 3 - .35
                    ("verdin-imx8mm-15005689", sorted_snrs[2]),  # Slot 4 - .36
                ]
            ),
        }

        return jsonify(response), 200

    except Exception as e:
        logging.error(f"An error occurred: {str(e)}")
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500
