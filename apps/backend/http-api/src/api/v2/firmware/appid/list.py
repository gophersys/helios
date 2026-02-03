from flask import jsonify

from src.lib.decorators import require_permissions
from src.lib.errors import internal_error
from src.lib.permissions import Permissions
from src.lib.types import ApiResponse
from src.services.database.prisma import get_db_client
from src.services.log.logger import get_logger

from .types import FirmwareAppIDListQuery, FirmwareAppIDResponse, build_where_clause


@require_permissions(Permissions.FIRMWARE_APPID_VIEW)
def list_appids():
    """List all firmware appids with optional filtering."""
    logger = get_logger()

    try:
        # Parse query parameters using shared type
        query = FirmwareAppIDListQuery.from_request()

        # Build where clause using helper function
        where_clause = build_where_clause(query)

        logger.info(f"Fetching firmware appids with filters: {where_clause}")

        # Get total count for pagination
        total_count = get_db_client().appid.count(where=where_clause)

        # Fetch appids with pagination
        appids = get_db_client().appid.find_many(
            where=where_clause, skip=query.offset, take=query.limit, order={"appId": "asc"}
        )

        logger.info(f"Retrieved {len(appids)} firmware appids out of {total_count} total")

        response_data = [FirmwareAppIDResponse.from_appid(appid).to_dict() for appid in appids]

        # Calculate pagination info
        total_pages = (total_count + (query.limit - 1)) // query.limit if query.limit else 1
        current_page = (query.offset // query.limit) + 1 if query.limit else 1

        response = ApiResponse.paginated(
            data=response_data,
            page=current_page if query.limit else None,
            total_pages=total_pages if query.limit else None,
            total_results=total_count,
            results_per_page=query.limit,
        )

        return jsonify(response.to_dict()), 200

    except Exception as e:
        logger.error(f"An error occurred while listing firmware appids: {str(e)}")
        return internal_error(f"Internal server error: {str(e)}")
