# Standard includes
import logging

from corekinect.http.response import ConcordHttpResponse
from corekinect.utils import Logger

# 3rd party includes
from flask import Blueprint, jsonify, request

# App includes
from src.middleware.permissions import authMiddleware
from src.services.database.prisma import get_db_client
from src.services.log.logger import get_logger

# Flask Route
v2_mtib_get_bp = Blueprint("mtib_get", __name__)


# -------------------------------------------------
#                                           Handler
# -------------------------------------------------
@v2_mtib_get_bp.route("/v2/mtib/get", methods=["GET"])
@authMiddleware.check_permissions(["Concord.Cluster.Read"])
def mtib_get_handler():
    """
    Get detailed information for a specific MTIB node

    Query Parameters:
    - hostname: The hostname of the MTIB to retrieve
    """
    logger: Logger = get_logger()

    try:
        # Get hostname from query parameters
        hostname = request.args.get("hostname")
        if not hostname:
            return (
                jsonify(
                    ConcordHttpResponse(
                        data=None, errors=[{"message": "Query parameter 'hostname' is required"}]
                    ).to_dict()
                ),
                400,
            )

        logger.info(f"Getting MTIB details for: {hostname}")

        # Get MTIB from database with all related data
        mtib = get_db_client().mtib.find_unique(
            where={"id": hostname}, include={"appIdMappings": {"include": {"app": True}}}
        )

        if not mtib:
            return (
                jsonify(
                    ConcordHttpResponse(
                        data=None, errors=[{"message": f"MTIB with hostname '{hostname}' not found"}]
                    ).to_dict()
                ),
                404,
            )

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

        # Format response data
        response_data = {
            "hostname": mtib.id,
            "name": mtib.name,
            "type": mtib.type.lower(),  # Convert VALIDATION/MANUFACTURING to lowercase
            "features": [feature.lower() for feature in mtib.features],  # Convert to lowercase
            "appIds": app_id_mappings,
            "createdAt": mtib.createdAt.isoformat(),
            "updatedAt": mtib.updatedAt.isoformat(),
        }

        logger.info(f"Retrieved MTIB details for: {hostname}")

        return jsonify(ConcordHttpResponse.new_get_response(response_data).to_dict()), 200

    except Exception as e:
        logger.error(f"An error occurred while getting MTIB details: {str(e)}")
        return (
            jsonify(
                ConcordHttpResponse(data=None, errors=[{"message": f"Internal server error: {str(e)}"}]).to_dict()
            ),
            500,
        )
