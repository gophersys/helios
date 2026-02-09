import logging

from flask import jsonify, request
from kubernetes.client.exceptions import ApiException

from src.lib.decorators import require_permissions
from src.lib.errors import internal_error, not_found
from src.lib.permissions import Permissions
from src.lib.types import ApiResponse
from src.services.kubernetes.events import list_events

logger = logging.getLogger(__name__)


@require_permissions(Permissions.ADMIN_SYSTEM_VIEW)
def get_events():
    namespace = request.args.get("namespace", None)
    limit = request.args.get("limit", 500, type=int)
    limit = min(max(limit, 1), 1000)

    try:
        data = list_events(namespace=namespace, limit=limit)
        return jsonify(ApiResponse.ok(data).to_dict()), 200
    except ApiException as e:
        if e.status == 404:
            return not_found("Events not found")
        return internal_error("Kubernetes API error")
    except Exception as e:
        logger.error("Unexpected error: %s", e)
        return internal_error("Failed to list events")
