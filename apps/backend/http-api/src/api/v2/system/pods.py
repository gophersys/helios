import logging

from flask import jsonify, request
from kubernetes.client.exceptions import ApiException

from src.lib.audit import log_audit
from src.lib.decorators import require_permissions
from src.lib.errors import internal_error, not_found
from src.lib.permissions import Permissions
from src.lib.types import ApiResponse
from src.lib.validation import validate_k8s_name
from src.services.kubernetes import pods as pods_svc

logger = logging.getLogger(__name__)


@require_permissions(Permissions.ADMIN_SYSTEM_VIEW)
def list_pods():
    namespace = request.args.get("namespace", None)
    limit = request.args.get("limit", 500, type=int)
    limit = min(max(limit, 1), 1000)
    try:
        data = pods_svc.list_pods(namespace=namespace)
        return jsonify(ApiResponse.ok(data[:limit]).to_dict()), 200
    except ApiException as e:
        if e.status == 404:
            return not_found("Pods not found")
        return internal_error("Kubernetes API error")
    except Exception as e:
        logger.error("Unexpected error: %s", e)
        return internal_error("Failed to list pods")


@require_permissions(Permissions.ADMIN_SYSTEM_VIEW)
def get_pod(namespace: str, name: str):
    err = validate_k8s_name(namespace, "namespace")
    if err: return err
    err = validate_k8s_name(name, "name")
    if err: return err
    try:
        data = pods_svc.get_pod(namespace, name)
        if data is None:
            return not_found("Pod not found")
        return jsonify(ApiResponse.ok(data).to_dict()), 200
    except ApiException as e:
        if e.status == 404:
            return not_found("Pod not found")
        return internal_error("Kubernetes API error")
    except Exception as e:
        logger.error("Unexpected error: %s", e)
        return internal_error("Failed to get pod")


@require_permissions(Permissions.ADMIN_SYSTEM_MANAGE)
def delete_pod(namespace: str, name: str):
    err = validate_k8s_name(namespace, "namespace")
    if err: return err
    err = validate_k8s_name(name, "name")
    if err: return err
    try:
        success = pods_svc.delete_pod(namespace, name)
        if not success:
            return internal_error("Failed to delete pod")
        log_audit("system.pod.delete", "Pod", f"{namespace}/{name}")
        return jsonify(ApiResponse.ok({"deleted": True}).to_dict()), 200
    except ApiException as e:
        if e.status == 404:
            return not_found("Pod not found")
        return internal_error("Kubernetes API error")
    except Exception as e:
        logger.error("Unexpected error: %s", e)
        return internal_error("Failed to delete pod")
