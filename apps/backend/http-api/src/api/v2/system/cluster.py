import logging

from flask import jsonify
from kubernetes.client.exceptions import ApiException

from src.lib.decorators import require_permissions
from src.lib.errors import internal_error, not_found
from src.lib.permissions import Permissions
from src.lib.types import ApiResponse
from src.services.kubernetes.cluster import get_cluster_info, list_namespaces

logger = logging.getLogger(__name__)


@require_permissions(Permissions.ADMIN_SYSTEM_VIEW)
def get_cluster():
    try:
        data = get_cluster_info()
        return jsonify(ApiResponse.ok(data).to_dict()), 200
    except ApiException as e:
        if e.status == 404:
            return not_found("Cluster info not found")
        return internal_error("Kubernetes API error")
    except Exception as e:
        logger.error("Unexpected error: %s", e)
        return internal_error("Failed to get cluster info")


@require_permissions(Permissions.ADMIN_SYSTEM_VIEW)
def get_namespaces():
    try:
        data = list_namespaces()
        return jsonify(ApiResponse.ok(data).to_dict()), 200
    except ApiException as e:
        if e.status == 404:
            return not_found("Namespaces not found")
        return internal_error("Kubernetes API error")
    except Exception as e:
        logger.error("Unexpected error: %s", e)
        return internal_error("Failed to list namespaces")
