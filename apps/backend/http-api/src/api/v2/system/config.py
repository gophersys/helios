import logging

from flask import jsonify, request
from kubernetes.client.exceptions import ApiException

from src.lib.audit import log_audit
from src.lib.decorators import require_permissions
from src.lib.errors import internal_error, not_found
from src.lib.permissions import Permissions
from src.lib.types import ApiResponse
from src.lib.validation import validate_k8s_name
from src.services.kubernetes import configmaps as config_svc

logger = logging.getLogger(__name__)


@require_permissions(Permissions.ADMIN_SYSTEM_VIEW)
def list_configmaps():
    namespace = request.args.get("namespace", None)
    limit = request.args.get("limit", 500, type=int)
    limit = min(max(limit, 1), 1000)
    try:
        data = config_svc.list_configmaps(namespace=namespace)
        return jsonify(ApiResponse.ok(data[:limit]).to_dict()), 200
    except ApiException as e:
        if e.status == 404:
            return not_found("ConfigMaps not found")
        return internal_error(f"Kubernetes API error")
    except Exception as e:
        logger.error("Unexpected error: %s", e)
        return internal_error(f"Failed to list configmaps")


@require_permissions(Permissions.ADMIN_SYSTEM_VIEW)
def get_configmap(namespace: str, name: str):
    err = validate_k8s_name(namespace, "namespace")
    if err: return err
    err = validate_k8s_name(name, "name")
    if err: return err
    try:
        data = config_svc.get_configmap(namespace, name)
        if data is None:
            return not_found("ConfigMap not found")
        return jsonify(ApiResponse.ok(data).to_dict()), 200
    except ApiException as e:
        if e.status == 404:
            return not_found("ConfigMap not found")
        return internal_error(f"Kubernetes API error")
    except Exception as e:
        logger.error("Unexpected error: %s", e)
        return internal_error(f"Failed to get configmap")


@require_permissions(Permissions.ADMIN_SYSTEM_VIEW)
def list_secrets():
    namespace = request.args.get("namespace", None)
    limit = request.args.get("limit", 500, type=int)
    limit = min(max(limit, 1), 1000)
    try:
        data = config_svc.list_secrets(namespace=namespace)
        return jsonify(ApiResponse.ok(data[:limit]).to_dict()), 200
    except ApiException as e:
        if e.status == 404:
            return not_found("Secrets not found")
        return internal_error(f"Kubernetes API error")
    except Exception as e:
        logger.error("Unexpected error: %s", e)
        return internal_error(f"Failed to list secrets")


@require_permissions(Permissions.ADMIN_SYSTEM_VIEW)
def get_secret(namespace: str, name: str):
    err = validate_k8s_name(namespace, "namespace")
    if err: return err
    err = validate_k8s_name(name, "name")
    if err: return err
    log_audit("system.secret.view", "Secret", f"{namespace}/{name}")
    try:
        data = config_svc.get_secret(namespace, name)
        if data is None:
            return not_found("Secret not found")
        return jsonify(ApiResponse.ok(data).to_dict()), 200
    except ApiException as e:
        if e.status == 404:
            return not_found("Secret not found")
        return internal_error(f"Kubernetes API error")
    except Exception as e:
        logger.error("Unexpected error: %s", e)
        return internal_error(f"Failed to get secret")
