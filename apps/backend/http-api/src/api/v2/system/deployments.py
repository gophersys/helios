import logging

from flask import jsonify, request
from kubernetes.client.exceptions import ApiException

from src.lib.audit import log_audit
from src.lib.decorators import require_permissions
from src.lib.errors import bad_request, internal_error, not_found
from src.lib.permissions import Permissions
from src.lib.types import ApiResponse
from src.lib.validation import validate_k8s_name
from src.services.kubernetes import deployments as dep_svc

from .types import ScaleDeploymentRequest

logger = logging.getLogger(__name__)


@require_permissions(Permissions.ADMIN_SYSTEM_VIEW)
def list_deployments():
    namespace = request.args.get("namespace", None)
    limit = request.args.get("limit", 500, type=int)
    limit = min(max(limit, 1), 1000)
    try:
        data = dep_svc.list_deployments(namespace=namespace)
        return jsonify(ApiResponse.ok(data[:limit]).to_dict()), 200
    except ApiException as e:
        if e.status == 404:
            return not_found("Deployments not found")
        return internal_error("Kubernetes API error")
    except Exception as e:
        logger.error("Unexpected error: %s", e)
        return internal_error("Failed to list deployments")


@require_permissions(Permissions.ADMIN_SYSTEM_VIEW)
def get_deployment(namespace: str, name: str):
    err = validate_k8s_name(namespace, "namespace")
    if err: return err
    err = validate_k8s_name(name, "name")
    if err: return err
    try:
        data = dep_svc.get_deployment(namespace, name)
        if data is None:
            return not_found("Deployment not found")
        return jsonify(ApiResponse.ok(data).to_dict()), 200
    except ApiException as e:
        if e.status == 404:
            return not_found("Deployment not found")
        return internal_error("Kubernetes API error")
    except Exception as e:
        logger.error("Unexpected error: %s", e)
        return internal_error("Failed to get deployment")


@require_permissions(Permissions.ADMIN_SYSTEM_MANAGE)
def scale_deployment(namespace: str, name: str):
    err = validate_k8s_name(namespace, "namespace")
    if err: return err
    err = validate_k8s_name(name, "name")
    if err: return err
    data, error = ScaleDeploymentRequest.from_json(request.get_json())
    if error:
        return bad_request(error)

    try:
        success = dep_svc.scale_deployment(namespace, name, data.replicas)
        if not success:
            return internal_error("Failed to scale deployment")
        log_audit("system.deployment.scale", "Deployment", f"{namespace}/{name}", {"replicas": data.replicas})
        return jsonify(ApiResponse.ok({"scaled": True, "replicas": data.replicas}).to_dict()), 200
    except ApiException as e:
        if e.status == 404:
            return not_found("Deployment not found")
        return internal_error("Kubernetes API error")
    except Exception as e:
        logger.error("Unexpected error: %s", e)
        return internal_error("Failed to scale deployment")


@require_permissions(Permissions.ADMIN_SYSTEM_MANAGE)
def restart_deployment(namespace: str, name: str):
    err = validate_k8s_name(namespace, "namespace")
    if err: return err
    err = validate_k8s_name(name, "name")
    if err: return err
    try:
        success = dep_svc.restart_deployment(namespace, name)
        if not success:
            return internal_error("Failed to restart deployment")
        log_audit("system.deployment.restart", "Deployment", f"{namespace}/{name}")
        return jsonify(ApiResponse.ok({"restarted": True}).to_dict()), 200
    except ApiException as e:
        if e.status == 404:
            return not_found("Deployment not found")
        return internal_error("Kubernetes API error")
    except Exception as e:
        logger.error("Unexpected error: %s", e)
        return internal_error("Failed to restart deployment")
