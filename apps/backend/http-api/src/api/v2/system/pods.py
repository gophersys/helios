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

from .shared import paginate, parse_list_params

logger = logging.getLogger(__name__)


@require_permissions(Permissions.CLUSTER_VIEW)
def list_pods():
    page, limit, namespace, label_selector, field_selector = parse_list_params()
    try:
        data = pods_svc.list_pods(
            namespace=namespace,
            label_selector=label_selector,
            field_selector=field_selector,
        )
        return jsonify(ApiResponse.ok(paginate(data, page, limit)).to_dict()), 200
    except ApiException as e:
        if e.status == 404:
            return not_found("Pods not found")
        return internal_error("Kubernetes API error")
    except Exception as e:
        logger.error("Unexpected error: %s", e)
        return internal_error("Failed to list pods")


@require_permissions(Permissions.CLUSTER_VIEW)
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


@require_permissions(Permissions.CLUSTER_VIEW)
def get_pod_logs(namespace: str, name: str):
    err = validate_k8s_name(namespace, "namespace")
    if err: return err
    err = validate_k8s_name(name, "name")
    if err: return err

    container = request.args.get("container", None)
    tail_lines = request.args.get("tailLines", 100, type=int)
    tail_lines = min(max(1, tail_lines), 10000)
    previous = request.args.get("previous", "false").lower() == "true"
    since_seconds = request.args.get("sinceSeconds", None, type=int)

    try:
        data = pods_svc.get_pod_logs(
            namespace, name,
            container=container,
            tail_lines=tail_lines,
            previous=previous,
            since_seconds=since_seconds,
        )
        if data is None:
            return not_found("Pod not found")
        return jsonify(ApiResponse.ok(data).to_dict()), 200
    except ApiException as e:
        if e.status == 404:
            return not_found("Pod not found")
        return internal_error("Kubernetes API error")
    except Exception as e:
        logger.error("Unexpected error: %s", e)
        return internal_error("Failed to get pod logs")


@require_permissions(Permissions.CLUSTER_MANAGE)
def delete_pod(namespace: str, name: str):
    err = validate_k8s_name(namespace, "namespace")
    if err: return err
    err = validate_k8s_name(name, "name")
    if err: return err
    try:
        success = pods_svc.delete_pod(namespace, name)
        if not success:
            return internal_error("Failed to delete pod")
        log_audit("cluster.pod.delete", "Pod", f"{namespace}/{name}")
        return jsonify(ApiResponse.ok({"deleted": True}).to_dict()), 200
    except ApiException as e:
        if e.status == 404:
            return not_found("Pod not found")
        return internal_error("Kubernetes API error")
    except Exception as e:
        logger.error("Unexpected error: %s", e)
        return internal_error("Failed to delete pod")
