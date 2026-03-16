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

from .shared import paginate, parse_list_params

logger = logging.getLogger(__name__)


@require_permissions(Permissions.KUBERNETES_VIEW)
def list_configmaps():
    page, limit, namespace, label_selector, field_selector = parse_list_params()
    try:
        data = config_svc.list_configmaps(
            namespace=namespace,
            label_selector=label_selector,
        )
        return jsonify(ApiResponse.ok(paginate(data, page, limit)).to_dict()), 200
    except ApiException as e:
        if e.status == 404:
            return not_found("ConfigMaps not found")
        return internal_error("Kubernetes API error")
    except Exception as e:
        logger.error("Unexpected error: %s", e)
        return internal_error("Failed to list configmaps")


@require_permissions(Permissions.KUBERNETES_VIEW)
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
        return internal_error("Kubernetes API error")
    except Exception as e:
        logger.error("Unexpected error: %s", e)
        return internal_error("Failed to get configmap")


@require_permissions(Permissions.KUBERNETES_VIEW)
def list_secrets():
    page, limit, namespace, label_selector, field_selector = parse_list_params()
    try:
        data = config_svc.list_secrets(
            namespace=namespace,
            label_selector=label_selector,
        )
        return jsonify(ApiResponse.ok(paginate(data, page, limit)).to_dict()), 200
    except ApiException as e:
        if e.status == 404:
            return not_found("Secrets not found")
        return internal_error("Kubernetes API error")
    except Exception as e:
        logger.error("Unexpected error: %s", e)
        return internal_error("Failed to list secrets")


@require_permissions(Permissions.KUBERNETES_VIEW)
def get_secret(namespace: str, name: str):
    err = validate_k8s_name(namespace, "namespace")
    if err: return err
    err = validate_k8s_name(name, "name")
    if err: return err
    try:
        log_audit("cluster.secret.view", "Secret", f"{namespace}/{name}")
        data = config_svc.get_secret(namespace, name)
        if data is None:
            return not_found("Secret not found")
        return jsonify(ApiResponse.ok(data).to_dict()), 200
    except ApiException as e:
        if e.status == 404:
            return not_found("Secret not found")
        return internal_error("Kubernetes API error")
    except Exception as e:
        logger.error("Unexpected error: %s", e)
        return internal_error("Failed to get secret")
