from flask import jsonify

from src.lib.decorators import require_permissions
from src.lib.errors import internal_error, not_found
from src.lib.permissions import Permissions
from src.lib.types import ApiResponse
from src.services.database.prisma import get_db_client
from src.services.log.logger import get_logger


@require_permissions(Permissions.FIRMWARE_APPID_DELETE)
def delete_appid(appId: int):
    """Delete a firmware appid by ID."""
    logger = get_logger()

    try:
        # Check if appid exists
        existing_appid = get_db_client().appid.find_unique(where={"appId": appId})
        if not existing_appid:
            return not_found(f"Application ID {appId} not found")

        logger.info(f"Deleting firmware appid: {existing_appid.name} (ID: {appId})")

        get_db_client().appid.delete(where={"appId": appId})

        logger.info(f"Successfully deleted firmware appid: {appId}")

        return jsonify(ApiResponse.deleted().to_dict()), 200

    except Exception as e:
        logger.error(f"An error occurred while deleting firmware appid {appId}: {str(e)}")
        return internal_error(f"Internal server error: {str(e)}")
