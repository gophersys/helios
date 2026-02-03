from flask import jsonify, request

from src.lib.decorators import require_permissions
from src.lib.errors import bad_request, internal_error
from src.lib.permissions import Permissions
from src.lib.types import ApiResponse
from src.services.database.prisma import get_db_client
from src.services.log.logger import get_logger

from .types import FirmwareAppIDCreateRequest, FirmwareAppIDResponse


@require_permissions(Permissions.FIRMWARE_APPID_CREATE)
def create_appid():
    """Create a new firmware appid."""
    logger = get_logger()

    try:
        # Parse input data
        data, error = FirmwareAppIDCreateRequest.from_json(request.get_json())
        if error:
            return bad_request(error)

        # Check if appId already exists
        existing_appid = get_db_client().appid.find_unique(where={"appId": data.appId})
        if existing_appid:
            return bad_request(f"Application ID {data.appId} already exists")

        # Create firmware appid entry in database
        logger.info(f"Creating firmware appid entry in database: {data.name} (ID: {data.appId})")

        new_appid = get_db_client().appid.create(
            data={
                "appId": data.appId,
                "name": data.name,
                "chipset": data.chipset,
                "target": data.target,
                "notes": data.notes,
            }
        )

        logger.info(f"Successfully created firmware appid: {new_appid.appId}")

        response_data = FirmwareAppIDResponse.from_appid(new_appid).to_dict()
        return jsonify(ApiResponse.created(response_data).to_dict()), 201

    except Exception as e:
        logger.error(f"An error occurred while creating firmware appid: {str(e)}")
        return internal_error(f"Internal server error: {str(e)}")
