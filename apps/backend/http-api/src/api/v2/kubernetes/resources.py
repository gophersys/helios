import logging

from flask import jsonify, request
from kubernetes.client.exceptions import ApiException

from src.lib.audit import log_audit
from src.lib.decorators import require_permissions
from src.lib.errors import bad_request, internal_error, not_found
from src.lib.permissions import Permissions
from src.lib.types import ApiResponse
from src.lib.validation import validate_k8s_name, validate_resource_kind
from src.services.kubernetes import resources as res_svc

from .types import ApplyResourceYamlRequest

logger = logging.getLogger(__name__)


@require_permissions(Permissions.KUBERNETES_VIEW)
def get_resource_yaml(kind: str, namespace: str, name: str):
    """Get the YAML representation of a Kubernetes resource.

    Args:
        kind: Resource kind (e.g., 'deployment', 'pod').
        namespace: Kubernetes namespace.
        name: Resource name.

    Returns:
        JSON response with the resource YAML dict.
    """
    err = validate_resource_kind(kind)
    if err: return err
    err = validate_k8s_name(namespace, "namespace")
    if err: return err
    err = validate_k8s_name(name, "name")
    if err: return err
    try:
        data = res_svc.get_resource_yaml(kind, namespace, name)
        if data is None:
            return not_found(f"{kind} not found")
        return jsonify(ApiResponse.ok(data).to_dict()), 200
    except ValueError:
        return bad_request("Invalid resource parameters")
    except ApiException as e:
        if e.status == 404:
            return not_found(f"{kind} not found")
        return internal_error("Kubernetes API error")
    except Exception as e:
        logger.error("Unexpected error: %s", e)
        return internal_error("Failed to get resource")


@require_permissions(Permissions.KUBERNETES_MANAGE)
def apply_resource_yaml(kind: str, namespace: str, name: str):
    """Apply (patch) a Kubernetes resource from a YAML string body.

    Args:
        kind: Resource kind (e.g., 'deployment', 'configmap').
        namespace: Kubernetes namespace.
        name: Resource name.

    Returns:
        JSON response with the updated resource on success.
    """
    err = validate_resource_kind(kind)
    if err: return err
    err = validate_k8s_name(namespace, "namespace")
    if err: return err
    err = validate_k8s_name(name, "name")
    if err: return err
    req, error = ApplyResourceYamlRequest.from_json(request.get_json())
    if error:
        return bad_request(error)

    try:
        data = res_svc.apply_resource_yaml(kind, namespace, name, req.yaml)
        log_audit("system.resource.apply", kind, f"{namespace}/{name}")
        return jsonify(ApiResponse.ok(data).to_dict()), 200
    except ValueError:
        return bad_request("Invalid resource parameters")
    except RuntimeError:
        return bad_request("Failed to apply resource configuration")
    except ApiException as e:
        if e.status == 404:
            return not_found(f"{kind} not found")
        return internal_error("Kubernetes API error")
    except Exception as e:
        logger.error("Unexpected error: %s", e)
        return internal_error("Failed to apply resource")


@require_permissions(Permissions.KUBERNETES_MANAGE)
def delete_resource(kind: str, namespace: str, name: str):
    """Delete a Kubernetes resource by kind, namespace, and name.

    Args:
        kind: Resource kind (e.g., 'deployment', 'pod').
        namespace: Kubernetes namespace.
        name: Resource name.

    Returns:
        JSON response with deleted=True on success.
    """
    err = validate_resource_kind(kind)
    if err: return err
    err = validate_k8s_name(namespace, "namespace")
    if err: return err
    err = validate_k8s_name(name, "name")
    if err: return err
    try:
        success = res_svc.delete_resource(kind, namespace, name)
        if not success:
            return internal_error("Failed to delete resource")
        log_audit("system.resource.delete", kind, f"{namespace}/{name}")
        return jsonify(ApiResponse.ok({"deleted": True}).to_dict()), 200
    except ValueError:
        return bad_request("Invalid resource parameters")
    except ApiException as e:
        if e.status == 404:
            return not_found(f"{kind} not found")
        return internal_error("Kubernetes API error")
    except Exception as e:
        logger.error("Unexpected error: %s", e)
        return internal_error("Failed to delete resource")
