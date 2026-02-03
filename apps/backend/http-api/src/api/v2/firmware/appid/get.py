from flask import jsonify

from src.lib.decorators import require_permissions
from src.lib.errors import internal_error, not_found
from src.lib.permissions import Permissions
from src.lib.types import ApiResponse
from src.services.database.prisma import get_db_client
from src.services.log.logger import get_logger

from .types import FirmwareAppIDResponse


@require_permissions(Permissions.FIRMWARE_APPID_VIEW)
def get_appid(appId: int):
    """Get a single firmware appid by ID."""
    logger = get_logger()

    try:
        logger.info(f"Fetching firmware appid: {appId}")

        appid = get_db_client().appid.find_unique(where={"appId": appId})

        if not appid:
            return not_found(f"Application ID {appId} not found")

        logger.info(f"Successfully retrieved firmware appid: {appid.name} (ID: {appId})")

        response_data = FirmwareAppIDResponse.from_appid(appid).to_dict()
        return jsonify(ApiResponse.ok(response_data).to_dict()), 200

    except Exception as e:
        logger.error(f"An error occurred while retrieving firmware appid {appId}: {str(e)}")
        return internal_error(f"Internal server error: {str(e)}")
