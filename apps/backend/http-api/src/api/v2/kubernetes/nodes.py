import logging

from flask import jsonify
from kubernetes.client.exceptions import ApiException

from src.lib.decorators import require_permissions
from src.lib.errors import not_found, internal_error
from src.lib.permissions import Permissions
from src.lib.types import ApiResponse
from src.services.kubernetes import nodes as nodes_svc

logger = logging.getLogger(__name__)


@require_permissions(Permissions.KUBERNETES_VIEW)
def list_nodes():
    """List all Kubernetes nodes with resource allocation summaries.

    Returns:
        JSON response with list of node dicts including CPU, memory, and pod allocation.
    """
    try:
        data = nodes_svc.list_nodes()
        return jsonify(ApiResponse.ok(data).to_dict()), 200
    except ApiException as e:
        if e.status == 404:
            return not_found("Nodes not found")
        return internal_error("Kubernetes API error")
    except Exception as e:
        logger.error("Unexpected error: %s", e)
        return internal_error("Failed to list nodes")


@require_permissions(Permissions.KUBERNETES_VIEW)
def get_node(node_name: str):
    """Get a specific Kubernetes node with pods and resource allocation.

    Args:
        node_name: Hostname of the Kubernetes node.

    Returns:
        JSON response with node data, allocated resources, and running pods.
    """
    try:
        data = nodes_svc.get_node(node_name)
        if data is None:
            return not_found("Node not found")
        return jsonify(ApiResponse.ok(data).to_dict()), 200
    except ApiException as e:
        if e.status == 404:
            return not_found("Node not found")
        return internal_error("Kubernetes API error")
    except Exception as e:
        logger.error("Unexpected error: %s", e)
        return internal_error("Failed to get node")
