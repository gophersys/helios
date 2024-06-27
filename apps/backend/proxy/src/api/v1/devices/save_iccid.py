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
devices_save_iccid_bp = Blueprint("devices_save_iccid", __name__)


@devices_save_iccid_bp.route("/v1/devices/iccids/save", methods=["POST"])
# @authMiddleware.check_permissions(["Concord.Devices.Read"])
def devices_save_iccid_handler():
    try:
        # Access JSON data from the request
        data = request.get_json()

        # Validate request fields
        iccid = data.get("iccid")
        if not iccid:
            return jsonify({"error": "Bad request, 'iccid' field is required."}), 400

        carrier = data.get("carrier")
        if not carrier:
            return jsonify({"error": "Bad request, 'carrier' field is required."}), 400

        snr = data.get("snr")
        if not snr:
            return jsonify({"error": "Bad request, 'snr' field is required."}), 400

        imei = data.get("imei")
        if not imei:
            return jsonify({"error": "Bad request, 'imei' field is required."}), 400

        # Call Manufacturing servers
        try:
            # Create payload
            body = {"Iccid": iccid, "Carrier": carrier, "boardSerialNumber": snr, "Imei": imei}

            # Do request
            save_iccid_url = f"{conf.MANU_SERVER_URL}/iccids/save"
            response = requests.post(save_iccid_url, json=body, verify=None, timeout=5)

            if response.status_code == 200:
                logging.info(response.content)
                return "", 200
            else:
                if response.status_code == 400:
                    response_data = response.json()
                    if response_data.get("code") == "Iccids.AlreadyExists":
                        logging.info(response.content)
                        return "", 200
                return (
                    jsonify(
                        {
                            "error": f'Manufacturing server call "{save_iccid_url}" with body {body} failed ({response.status_code}): {str(response.content)}'
                        }
                    ),
                    response.status_code,
                )

        except Exception as e:
            return (
                jsonify({"error": f"An exception occurred saving ICCID info to manufacturing server: {str(e)}"}),
                500,
            )

    except Exception as e:
        logging.error(f"An error occurred: {str(e)}")
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500
