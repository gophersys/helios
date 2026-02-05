from flask import jsonify, request

from src.lib.audit import log_audit
from src.lib.decorators import require_permissions
from src.lib.errors import bad_request, internal_error, not_found
from src.lib.permissions import Permissions
from src.lib.types import ApiResponse
from src.services.database.prisma import get_db_client
from src.services.log.logger import get_logger

from .types import MtibUnregisterRequest


@require_permissions(Permissions.MTIB_MANAGE)
def unregister_mtib():
    """Unregister an MTIB node."""
    logger = get_logger()

    try:
        # Parse input data
        data, error = MtibUnregisterRequest.from_json(request.get_json())
        if error:
            return bad_request(error)

        logger.info(f"Unregistering MTIB: {data.hostname}")

        # Check if MTIB exists
        existing_mtib = get_db_client().mtib.find_unique(where={"id": data.hostname})
        if not existing_mtib:
            return not_found(f"MTIB with hostname '{data.hostname}' not found")

        # Delete MTIB (cascade will handle appId mappings)
        get_db_client().mtib.delete(where={"id": data.hostname})

        logger.info(f"Successfully unregistered MTIB: {data.hostname}")
        log_audit("node.unregister", "Node", data.hostname, {"name": existing_mtib.name, "hostname": data.hostname})

        response_data = {
            "hostname": data.hostname,
            "status": "unregistered",
            "message": f"MTIB {data.hostname} unregistered successfully",
        }

        return jsonify(ApiResponse.ok(response_data).to_dict()), 200

    except Exception as e:
        logger.error(f"An error occurred while unregistering MTIB: {str(e)}")
        return internal_error("Internal server error")
