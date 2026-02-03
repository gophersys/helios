from flask import jsonify

from src.lib.decorators import require_permissions
from src.lib.errors import internal_error
from src.lib.permissions import Permissions
from src.lib.types import ApiResponse
from src.services.database.prisma import get_db_client
from src.services.log.logger import get_logger


@require_permissions(Permissions.MTIB_READ)
def list_mtibs():
    """List all MTIB nodes with basic information."""
    logger = get_logger()

    try:
        logger.info("Listing all MTIB nodes")

        # Get all MTIBs from database
        mtibs = get_db_client().mtib.find_many(include={"appIdMappings": {"include": {"app": True}}})

        response_data = []
        for mtib in mtibs:
            response_data.append(
                {
                    "hostname": mtib.id,
                    "name": mtib.name,
                    "type": mtib.type.lower(),
                    "features": [feature.lower() for feature in mtib.features],
                    "appIdCount": len(mtib.appIdMappings),
                    "createdAt": mtib.createdAt.isoformat(),
                    "updatedAt": mtib.updatedAt.isoformat(),
                }
            )

        logger.info(f"Found {len(response_data)} MTIB nodes")

        return jsonify(ApiResponse.ok(response_data).to_dict()), 200

    except Exception as e:
        logger.error(f"An error occurred while listing MTIB nodes: {str(e)}")
        return internal_error(f"Internal server error: {str(e)}")
