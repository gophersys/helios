# Standard includes
import logging
from dataclasses import dataclass
from typing import Optional, Tuple

from corekinect.http.response import ConcordHttpResponse
from corekinect.utils import Logger

# 3rd party includes
from flask import Blueprint, jsonify, request

# App includes
from src.middleware.permissions import authMiddleware
from src.services.database.prisma import get_db_client
from src.services.log.logger import get_logger

# Flask Route
v2_mtib_unregister_bp = Blueprint("mtib_unregister", __name__)


# -------------------------------------------------
#                                             Input
# -------------------------------------------------


@dataclass
class MtibUnregisterRequest:
    """Request structure for unregistering a MTIB"""

    hostname: str

    @classmethod
    def from_json(cls, data: dict) -> Tuple["MtibUnregisterRequest", Optional[str]]:
        """Parse JSON data into request object with validation"""
        if not data:
            return None, "Request body must contain JSON data"

        hostname = data.get("hostname")
        if not hostname:
            return None, "Field 'hostname' is required"

        return cls(hostname=hostname), None


# -------------------------------------------------
#                                           Handler
# -------------------------------------------------
@v2_mtib_unregister_bp.route("/v2/mtib/unregister", methods=["POST"])
@authMiddleware.check_permissions(["Concord.Cluster.Manage"])
def mtib_unregister_handler():
    """
    Unregister an MTIB node

    Payload:
    {
        "hostname": "string"
    }
    """
    logger: Logger = get_logger()

    try:
        # Parse input data
        data, error = MtibUnregisterRequest.from_json(request.get_json())
        if error:
            return jsonify(ConcordHttpResponse(data=None, errors=[{"message": error}]).to_dict()), 400

        logger.info(f"Unregistering MTIB: {data.hostname}")

        # Check if MTIB exists
        existing_mtib = get_db_client().mtib.find_unique(where={"id": data.hostname})
        if not existing_mtib:
            return (
                jsonify(
                    ConcordHttpResponse(
                        data=None, errors=[{"message": f"MTIB with hostname '{data.hostname}' not found"}]
                    ).to_dict()
                ),
                404,
            )

        # Delete MTIB (cascade will handle appId mappings)
        get_db_client().mtib.delete(where={"id": data.hostname})

        logger.info(f"Successfully unregistered MTIB: {data.hostname}")

        # Create success response
        response_data = {
            "hostname": data.hostname,
            "status": "unregistered",
            "message": f"MTIB {data.hostname} unregistered successfully",
        }

        return jsonify(ConcordHttpResponse.new_create_response(response_data).to_dict()), 200

    except Exception as e:
        logger.error(f"An error occurred while unregistering MTIB: {str(e)}")
        return (
            jsonify(
                ConcordHttpResponse(data=None, errors=[{"message": f"Internal server error: {str(e)}"}]).to_dict()
            ),
            500,
        )
