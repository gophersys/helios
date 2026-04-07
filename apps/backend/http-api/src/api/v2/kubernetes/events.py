import logging

from flask import jsonify, request
from kubernetes.client.exceptions import ApiException

from src.lib.decorators import require_permissions
from src.lib.errors import internal_error, not_found
from src.lib.permissions import Permissions
from src.lib.types import ApiResponse
from src.services.kubernetes.events import list_events

from .shared import paginate, parse_list_params

logger = logging.getLogger(__name__)


@require_permissions(Permissions.KUBERNETES_VIEW)
def get_events():
    """List Kubernetes events with optional type filtering."""
    page, limit, namespace, label_selector, field_selector = parse_list_params()
    event_type = request.args.get("type", None)  # Normal or Warning

    try:
        data = list_events(
            namespace=namespace,
            limit=limit * page,  # fetch enough for pagination
            field_selector=field_selector,
        )
        # Client-side type filter (K8s field_selector doesn't support type filtering)
        if event_type:
            data = [e for e in data if e.get("type") == event_type]
        return jsonify(ApiResponse.ok(paginate(data, page, limit)).to_dict()), 200
    except ApiException as e:
        if e.status == 404:
            return not_found("Events not found")
        return internal_error("Kubernetes API error")
    except Exception as e:
        logger.error("Unexpected error: %s", e)
        return internal_error("Failed to list events")
