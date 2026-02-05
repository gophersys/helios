import math

from flask import jsonify, request

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

        db = get_db_client()

        page = max(1, request.args.get("page", 1, type=int))
        limit = min(max(1, request.args.get("limit", 50, type=int)), 100)
        skip = (page - 1) * limit

        total = db.mtib.count()
        mtibs = db.mtib.find_many(
            skip=skip,
            take=limit,
            include={"appIdMappings": {"include": {"app": True}}},
        )

        data = []
        for mtib in mtibs:
            data.append(
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

        logger.info(f"Found {total} MTIB nodes")

        return jsonify(ApiResponse.ok({
            "data": data,
            "pagination": {
                "page": page,
                "limit": limit,
                "total": total,
                "pages": math.ceil(total / limit) if limit > 0 else 0,
            },
        }).to_dict()), 200

    except Exception as e:
        logger.error(f"An error occurred while listing MTIB nodes: {str(e)}")
        return internal_error("Internal server error")
