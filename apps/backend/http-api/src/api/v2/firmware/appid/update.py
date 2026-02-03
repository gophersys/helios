from flask import jsonify, request

from src.lib.decorators import require_permissions
from src.lib.errors import bad_request, internal_error, not_found
from src.lib.permissions import Permissions
from src.lib.types import ApiResponse
from src.services.database.prisma import get_db_client
from src.services.log.logger import get_logger

from .types import FirmwareAppIDResponse, FirmwareAppIDUpdateRequest, build_update_data


@require_permissions(Permissions.FIRMWARE_APPID_UPDATE)
def update_appid(appId: int):
    """Update a firmware appid by ID."""
    logger = get_logger()

    try:
        # Parse input data
        data, error = FirmwareAppIDUpdateRequest.from_json(request.get_json())
        if error:
            return bad_request(error)

        # Check if appid exists
        existing_appid = get_db_client().appid.find_unique(where={"appId": appId})
        if not existing_appid:
            return not_found(f"Application ID {appId} not found")

        # Build update data using helper function
        update_data_dict = build_update_data(data)

        if not update_data_dict:
            return bad_request("No fields provided for update")

        logger.info(f"Updating firmware appid: {existing_appid.name} (ID: {appId})")

        updated_appid = get_db_client().appid.update(where={"appId": appId}, data=update_data_dict)

        logger.info(f"Successfully updated firmware appid: {updated_appid.appId}")

        response_data = FirmwareAppIDResponse.from_appid(updated_appid).to_dict()
        return jsonify(ApiResponse.ok(response_data).to_dict()), 200

    except Exception as e:
        logger.error(f"An error occurred while updating firmware appid {appId}: {str(e)}")
        return internal_error(f"Internal server error: {str(e)}")
