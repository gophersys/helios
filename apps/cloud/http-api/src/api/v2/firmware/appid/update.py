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

# Local includes
from .types import FirmwareAppIDResponse, FirmwareAppIDUpdateRequest, build_update_data

# Flask Route
v2_firmware_appid_update_bp = Blueprint("v2_firmware_appid_update", __name__)


# -------------------------------------------------
#                                           Handler
# -------------------------------------------------
@v2_firmware_appid_update_bp.route("/v2/firmware/appid/<int:appId>", methods=["PUT"])
@authMiddleware.check_permissions(["Concord.Firmware.AppID.Update"])
def v2_firmware_appid_update_handler(appId: int):
    """
    Update a firmware appid by ID

    Path Parameters:
        appId: The numeric application ID to update

    Payload (all fields optional):
    {
        "name": "string",
        "chipset": "string",
        "target": "string",
        "notes": "string"
    }
    """
    logger: Logger = get_logger()
    db_client: Prisma = get_db_client()

    try:
        # Parse input data
        data, error = FirmwareAppIDUpdateRequest.from_json(request.get_json())
        if error:
            return jsonify(ConcordHttpResponse(data=None, errors=[{"message": error}]).to_dict()), 400

        # Check if appid exists
        existing_appid = db_client.appid.find_unique(where={"appId": appId})
        if not existing_appid:
            return (
                jsonify(
                    ConcordHttpResponse(data=None, errors=[{"message": f"Application ID {appId} not found"}]).to_dict()
                ),
                404,
            )

        # Build update data using helper function
        update_data = build_update_data(data)

        # Check if there's anything to update
        if not update_data:
            return (
                jsonify(
                    ConcordHttpResponse(data=None, errors=[{"message": "No fields provided for update"}]).to_dict()
                ),
                400,
            )

        # Update the firmware appid
        logger.info(f"Updating firmware appid: {existing_appid.name} (ID: {appId})")

        updated_appid = db_client.appid.update(where={"appId": appId}, data=update_data)

        logger.info(f"Successfully updated firmware appid: {updated_appid.appId}")

        # Convert to response format
        response_data = FirmwareAppIDResponse.from_appid(updated_appid).to_dict()

        # Create success response
        return jsonify(ConcordHttpResponse.new_update_response(response_data).to_dict()), 200

    except Exception as e:
        logger.error(f"An error occurred while updating firmware appid {appId}: {str(e)}")
        return (
            jsonify(
                ConcordHttpResponse(data=None, errors=[{"message": f"Internal server error: {str(e)}"}]).to_dict()
            ),
            500,
        )
