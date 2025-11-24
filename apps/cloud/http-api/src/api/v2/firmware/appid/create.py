# Standard includes
import logging

from corekinect.database import Prisma
from corekinect.http.response import ConcordHttpResponse
from corekinect.utils import Logger

# 3rd party includes
from flask import Blueprint, jsonify, request

# App includes
from src.middleware.permissions import authMiddleware
from src.services.database.prisma import get_db_client
from src.services.log.logger import get_logger
from src.services.proxy import appProxyServer

# Local includes
from .types import FirmwareAppIDCreateRequest, FirmwareAppIDResponse

# Flask Route
v2_firmware_appid_create_bp = Blueprint("v2_firmware_appid_create", __name__)


# -------------------------------------------------
#                                           Handler
# -------------------------------------------------
@v2_firmware_appid_create_bp.route("/v2/firmware/appid", methods=["POST"])
@authMiddleware.check_permissions(["Concord.Firmware.AppID.Create"])
def v2_firmware_appid_create_handler():
    """
    Create a new firmware appid

    Payload:
    {
        "appId": "integer",
        "name": "string",
        "chipset": "string",
        "target": "string",
        "notes": "string (optional)"
    }
    """
    logger: Logger = get_logger()
    db_client: Prisma = get_db_client()

    try:
        # Parse input data
        data, error = FirmwareAppIDCreateRequest.from_json(request.get_json())
        if error:
            return jsonify(ConcordHttpResponse(data=None, errors=[{"message": error}]).to_dict()), 400

        # Check if appId already exists
        existing_appid = db_client.appid.find_unique(where={"appId": data.appId})
        if existing_appid:
            return (
                jsonify(
                    ConcordHttpResponse(
                        data=None, errors=[{"message": f"Application ID {data.appId} already exists"}]
                    ).to_dict()
                ),
                400,
            )

        # Create firmware appid entry in database
        logger.info(f"Creating firmware appid entry in database: {data.name} (ID: {data.appId})")

        new_appid = db_client.appid.create(
            data={
                "appId": data.appId,
                "name": data.name,
                "chipset": data.chipset,
                "target": data.target,
                "notes": data.notes,
            }
        )

        logger.info(f"Successfully created firmware appid: {new_appid.appId}")

        # Create success response using the response struct
        response_data = FirmwareAppIDResponse.from_appid(new_appid).to_dict()
        return jsonify(ConcordHttpResponse.new_create_response(response_data).to_dict()), 201

    except Exception as e:
        logger.error(f"An error occurred while creating firmware appid: {str(e)}")
        return (
            jsonify(
                ConcordHttpResponse(data=None, errors=[{"message": f"Internal server error: {str(e)}"}]).to_dict()
            ),
            500,
        )
