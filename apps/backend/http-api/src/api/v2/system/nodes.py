import logging

from flask import jsonify
from kubernetes.client.exceptions import ApiException

from src.lib.decorators import require_permissions
from src.lib.errors import not_found, internal_error
from src.lib.permissions import Permissions
from src.lib.types import ApiResponse
from src.services.kubernetes import nodes as nodes_svc

logger = logging.getLogger(__name__)


@require_permissions(Permissions.ADMIN_SYSTEM_VIEW)
def list_nodes():
    try:
        data = nodes_svc.list_nodes()
        return jsonify(ApiResponse.ok(data).to_dict()), 200
    except ApiException as e:
        if e.status == 404:
            return not_found("Nodes not found")
        return internal_error(f"Kubernetes API error")
    except Exception as e:
        logger.error("Unexpected error: %s", e)
        return internal_error(f"Failed to list nodes")


@require_permissions(Permissions.ADMIN_SYSTEM_VIEW)
def get_node(node_name: str):
    try:
        data = nodes_svc.get_node(node_name)
        if data is None:
            return not_found("Node not found")
        return jsonify(ApiResponse.ok(data).to_dict()), 200
    except ApiException as e:
        if e.status == 404:
            return not_found("Node not found")
        return internal_error(f"Kubernetes API error")
    except Exception as e:
        logger.error("Unexpected error: %s", e)
        return internal_error(f"Failed to get node")
