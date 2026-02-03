# Standard includes
import logging

from database import Prisma
from corekinect.http.response import ConcordHttpResponse
from corekinect.utils import Logger

# 3rd party includes
from flask import Blueprint, jsonify

# App includes
from src.middleware.permissions import authMiddleware
from src.services.database.prisma import get_db_client
from src.services.log.logger import get_logger

# Local includes
from .types import FirmwareAppIDResponse

# Flask Route
v2_firmware_appid_get_bp = Blueprint("v2_firmware_appid_get", __name__)


# -------------------------------------------------
#                                           Handler
# -------------------------------------------------
@v2_firmware_appid_get_bp.route("/v2/firmware/appid/<int:appId>", methods=["GET"])
@authMiddleware.check_permissions(["Concord.Firmware.AppID.View"])
def v2_firmware_appid_get_handler(appId: int):
    """
    Get a single firmware appid by ID

    Path Parameters:
        appId: The numeric application ID to retrieve
    """
    logger: Logger = get_logger()
    db_client: Prisma = get_db_client()

    try:
        logger.info(f"Fetching firmware appid: {appId}")

        # Find the appid
        appid = db_client.appid.find_unique(where={"appId": appId})

        if not appid:
            return (
                jsonify(
                    ConcordHttpResponse(data=None, errors=[{"message": f"Application ID {appId} not found"}]).to_dict()
                ),
                404,
            )

        logger.info(f"Successfully retrieved firmware appid: {appid.name} (ID: {appId})")

        # Convert to response format
        response_data = FirmwareAppIDResponse.from_appid(appid).to_dict()

        # Create success response
        return jsonify(ConcordHttpResponse.new_get_response(response_data).to_dict()), 200

    except Exception as e:
        logger.error(f"An error occurred while retrieving firmware appid {appId}: {str(e)}")
        return (
            jsonify(
                ConcordHttpResponse(data=None, errors=[{"message": f"Internal server error: {str(e)}"}]).to_dict()
            ),
            500,
        )
