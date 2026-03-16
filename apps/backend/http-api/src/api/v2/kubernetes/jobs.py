import logging

from flask import jsonify, request
from kubernetes.client.exceptions import ApiException

from src.lib.audit import log_audit
from src.lib.decorators import require_permissions
from src.lib.errors import internal_error, not_found
from src.lib.permissions import Permissions
from src.lib.types import ApiResponse
from src.lib.validation import validate_k8s_name
from src.services.kubernetes import jobs as jobs_svc

from .shared import paginate, parse_list_params

logger = logging.getLogger(__name__)


@require_permissions(Permissions.KUBERNETES_VIEW)
def list_jobs():
    page, limit, namespace, label_selector, field_selector = parse_list_params()
    try:
        data = jobs_svc.list_jobs(
            namespace=namespace,
            label_selector=label_selector,
            field_selector=field_selector,
        )
        return jsonify(ApiResponse.ok(paginate(data, page, limit)).to_dict()), 200
    except ApiException as e:
        if e.status == 404:
            return not_found("Jobs not found")
        return internal_error("Kubernetes API error")
    except Exception as e:
        logger.error("Unexpected error: %s", e)
        return internal_error("Failed to list jobs")


@require_permissions(Permissions.KUBERNETES_VIEW)
def get_job(namespace: str, name: str):
    err = validate_k8s_name(namespace, "namespace")
    if err: return err
    err = validate_k8s_name(name, "name")
    if err: return err
    try:
        data = jobs_svc.get_job(namespace, name)
        if data is None:
            return not_found("Job not found")
        return jsonify(ApiResponse.ok(data).to_dict()), 200
    except ApiException as e:
        if e.status == 404:
            return not_found("Job not found")
        return internal_error("Kubernetes API error")
    except Exception as e:
        logger.error("Unexpected error: %s", e)
        return internal_error("Failed to get job")


@require_permissions(Permissions.KUBERNETES_MANAGE)
def delete_job(namespace: str, name: str):
    err = validate_k8s_name(namespace, "namespace")
    if err: return err
    err = validate_k8s_name(name, "name")
    if err: return err
    try:
        success = jobs_svc.delete_job(namespace, name)
        if not success:
            return internal_error("Failed to delete job")
        log_audit("cluster.job.delete", "Job", f"{namespace}/{name}")
        return jsonify(ApiResponse.ok({"deleted": True}).to_dict()), 200
    except ApiException as e:
        if e.status == 404:
            return not_found("Job not found")
        return internal_error("Kubernetes API error")
    except Exception as e:
        logger.error("Unexpected error: %s", e)
        return internal_error("Failed to delete job")
