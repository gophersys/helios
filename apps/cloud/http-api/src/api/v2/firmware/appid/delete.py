# Standard includes
import logging

from corekinect.database import Prisma
from corekinect.http.response import ConcordHttpResponse
from corekinect.utils import Logger

# 3rd party includes
from flask import Blueprint, jsonify

# App includes
from src.middleware.permissions import authMiddleware
from src.services.database.prisma import get_db_client
from src.services.log.logger import get_logger

# Flask Route
v2_firmware_appid_delete_bp = Blueprint("v2_firmware_appid_delete", __name__)


# -------------------------------------------------
#                                           Handler
# -------------------------------------------------
@v2_firmware_appid_delete_bp.route("/v2/firmware/appid/<int:appId>", methods=["DELETE"])
@authMiddleware.check_permissions(["Concord.Firmware.AppID.Delete"])
def v2_firmware_appid_delete_handler(appId: int):
    """
    Delete a firmware appid by ID

    Path Parameters:
        appId: The numeric application ID to delete
    """
    logger: Logger = get_logger()
    db_client: Prisma = get_db_client()

    try:
        # Check if appid exists
        existing_appid = db_client.appid.find_unique(where={"appId": appId})
        if not existing_appid:
            return (
                jsonify(
                    ConcordHttpResponse(data=None, errors=[{"message": f"Application ID {appId} not found"}]).to_dict()
                ),
                404,
            )

        # Delete the firmware appid
        logger.info(f"Deleting firmware appid: {existing_appid.name} (ID: {appId})")

        deleted_appid = db_client.appid.delete(where={"appId": appId})

        logger.info(f"Successfully deleted firmware appid: {deleted_appid.appId}")

        # Return success response
        return jsonify(ConcordHttpResponse.new_delete_response().to_dict()), 200

    except Exception as e:
        logger.error(f"An error occurred while deleting firmware appid {appId}: {str(e)}")
        return (
            jsonify(
                ConcordHttpResponse(data=None, errors=[{"message": f"Internal server error: {str(e)}"}]).to_dict()
            ),
            500,
        )
