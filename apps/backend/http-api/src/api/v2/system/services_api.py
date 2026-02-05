import logging

from flask import jsonify, request
from kubernetes.client.exceptions import ApiException

from src.lib.decorators import require_permissions
from src.lib.errors import internal_error, not_found
from src.lib.permissions import Permissions
from src.lib.types import ApiResponse
from src.lib.validation import validate_k8s_name
from src.services.kubernetes import services_k8s as svc_svc

logger = logging.getLogger(__name__)


@require_permissions(Permissions.ADMIN_SYSTEM_VIEW)
def list_services():
    namespace = request.args.get("namespace", None)
    limit = request.args.get("limit", 500, type=int)
    limit = min(max(limit, 1), 1000)
    try:
        data = svc_svc.list_services(namespace=namespace)
        return jsonify(ApiResponse.ok(data[:limit]).to_dict()), 200
    except ApiException as e:
        if e.status == 404:
            return not_found("Services not found")
        return internal_error(f"Kubernetes API error")
    except Exception as e:
        logger.error("Unexpected error: %s", e)
        return internal_error(f"Failed to list services")


@require_permissions(Permissions.ADMIN_SYSTEM_VIEW)
def get_service(namespace: str, name: str):
    err = validate_k8s_name(namespace, "namespace")
    if err: return err
    err = validate_k8s_name(name, "name")
    if err: return err
    try:
        data = svc_svc.get_service(namespace, name)
        if data is None:
            return not_found("Service not found")
        return jsonify(ApiResponse.ok(data).to_dict()), 200
    except ApiException as e:
        if e.status == 404:
            return not_found("Service not found")
        return internal_error(f"Kubernetes API error")
    except Exception as e:
        logger.error("Unexpected error: %s", e)
        return internal_error(f"Failed to get service")
