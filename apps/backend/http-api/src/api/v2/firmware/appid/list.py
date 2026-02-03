# Standard includes
import logging

from database import Prisma
from corekinect.http.response import ConcordHttpResponse
from corekinect.utils import Logger

# 3rd party includes
from flask import Blueprint, jsonify

# App includes
from src.middleware.permissions import authMiddleware
from src.services.database.prisma import get_db_client
from src.services.log.logger import get_logger

# Local includes
from .types import FirmwareAppIDListQuery, FirmwareAppIDResponse, build_where_clause

# Flask Route
v2_firmware_appid_list_bp = Blueprint("v2_firmware_appid_list", __name__)


# -------------------------------------------------
#                                           Handler
# -------------------------------------------------
@v2_firmware_appid_list_bp.route("/v2/firmware/appid", methods=["GET"])
@authMiddleware.check_permissions(["Concord.Firmware.AppID.View"])
def v2_firmware_appid_list_handler():
    """
    List all firmware appids with optional filtering

    Query Parameters:
        chipset: Filter by chipset (optional)
        target: Filter by target microcontroller (optional)
        limit: Maximum number of results (optional)
        offset: Number of results to skip (optional)
    """
    logger: Logger = get_logger()
    db_client: Prisma = get_db_client()

    try:
        # Parse query parameters using shared type
        query = FirmwareAppIDListQuery.from_request()

        # Build where clause using helper function
        where_clause = build_where_clause(query)

        logger.info(f"Fetching firmware appids with filters: {where_clause}")

        # Get total count for pagination
        total_count = db_client.appid.count(where=where_clause)

        # Fetch appids with pagination
        appids = db_client.appid.find_many(
            where=where_clause, skip=query.offset, take=query.limit, order={"appId": "asc"}  # Order by appId ascending
        )

        logger.info(f"Retrieved {len(appids)} firmware appids out of {total_count} total")

        # Convert to response format
        response_data = [FirmwareAppIDResponse.from_appid(appid).to_dict() for appid in appids]

        # Calculate pagination info
        total_pages = (total_count + (query.limit - 1)) // query.limit if query.limit else 1
        current_page = (query.offset // query.limit) + 1 if query.limit else 1

        # Create list response with pagination
        response = ConcordHttpResponse.new_list_response(
            data=response_data,
            page=current_page if query.limit else None,
            total_pages=total_pages if query.limit else None,
            total_results=total_count,
            results_per_page=query.limit,
        )

        return jsonify(response.to_dict()), 200

    except Exception as e:
        logger.error(f"An error occurred while listing firmware appids: {str(e)}")
        return (
            jsonify(
                ConcordHttpResponse(data=None, errors=[{"message": f"Internal server error: {str(e)}"}]).to_dict()
            ),
            500,
        )
