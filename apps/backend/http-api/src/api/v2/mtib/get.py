from flask import jsonify, request

from src.lib.decorators import require_permissions
from src.lib.errors import bad_request, internal_error, not_found
from src.lib.permissions import Permissions
from src.lib.types import ApiResponse
from src.services.database.prisma import get_db_client
from src.services.log.logger import get_logger


@require_permissions(Permissions.DEVICES_VIEW)
def get_mtib():
    """Get detailed information for a specific MTIB node."""
    logger = get_logger()

    try:
        # Get hostname from query parameters
        hostname = request.args.get("hostname")
        if not hostname:
            return bad_request("Query parameter 'hostname' is required")

        logger.info(f"Getting MTIB details for: {hostname}")

        # Get MTIB from database with all related data
        mtib = get_db_client().mtib.find_unique(
            where={"id": hostname}, include={"appIdMappings": {"include": {"app": True}}}
        )

        if not mtib:
            return not_found(f"MTIB with hostname '{hostname}' not found")

        # Format appId mappings
        app_id_mappings = []
        for mapping in mtib.appIdMappings:
            app_id_mappings.append(
                {
                    "jlink": mapping.jlink,
                    "appId": mapping.appId,
                    "appName": mapping.app.name,
                    "chipset": mapping.app.chipset,
                    "target": mapping.app.target,
                    "notes": mapping.app.notes,
                }
            )

        response_data = {
            "hostname": mtib.id,
            "name": mtib.name,
            "type": mtib.type.lower(),
            "features": [feature.lower() for feature in mtib.features],
            "appIds": app_id_mappings,
            "createdAt": mtib.createdAt.isoformat(),
            "updatedAt": mtib.updatedAt.isoformat(),
        }

        logger.info(f"Retrieved MTIB details for: {hostname}")

        return jsonify(ApiResponse.ok(response_data).to_dict()), 200

    except Exception as e:
        logger.error(f"An error occurred while getting MTIB details: {str(e)}")
        return internal_error("Internal server error")
