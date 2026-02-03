# Standard includes
import logging
from typing import List

from corekinect.http.response import ConcordHttpResponse
from corekinect.utils import Logger

# 3rd party includes
from flask import Blueprint, jsonify

# App includes
from src.middleware.permissions import authMiddleware
from src.services.database.prisma import get_db_client
from src.services.log.logger import get_logger

# Flask Route
v2_mtib_list_bp = Blueprint("mtib_list", __name__)


# -------------------------------------------------
#                                           Handler
# -------------------------------------------------
@v2_mtib_list_bp.route("/v2/mtib/list", methods=["GET"])
@authMiddleware.check_permissions(["Concord.Cluster.Read"])
def mtib_list_handler():
    """
    List all MTIB nodes with basic information (hostname and type)
    """
    logger: Logger = get_logger()

    try:
        logger.info("Listing all MTIB nodes")

        # Get all MTIBs from database
        mtibs = get_db_client().mtib.find_many(include={"appIdMappings": {"include": {"app": True}}})

        # Format response data
        response_data = []
        for mtib in mtibs:
            response_data.append(
                {
                    "hostname": mtib.id,
                    "name": mtib.name,
                    "type": mtib.type.lower(),  # Convert VALIDATION/MANUFACTURING to lowercase
                    "features": [feature.lower() for feature in mtib.features],  # Convert to lowercase
                    "appIdCount": len(mtib.appIdMappings),
                    "createdAt": mtib.createdAt.isoformat(),
                    "updatedAt": mtib.updatedAt.isoformat(),
                }
            )

        logger.info(f"Found {len(response_data)} MTIB nodes")

        return jsonify(ConcordHttpResponse.new_get_response(response_data).to_dict()), 200

    except Exception as e:
        logger.error(f"An error occurred while listing MTIB nodes: {str(e)}")
        return (
            jsonify(
                ConcordHttpResponse(data=None, errors=[{"message": f"Internal server error: {str(e)}"}]).to_dict()
            ),
            500,
        )
