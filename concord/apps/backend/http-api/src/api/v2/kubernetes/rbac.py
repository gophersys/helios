import logging

from flask import jsonify, request
from kubernetes.client.exceptions import ApiException

from src.lib.decorators import require_permissions
from src.lib.errors import internal_error, not_found
from src.lib.permissions import Permissions
from src.lib.types import ApiResponse
from src.services.kubernetes import rbac as rbac_svc

from .shared import paginate, parse_list_params

logger = logging.getLogger(__name__)


@require_permissions(Permissions.KUBERNETES_VIEW)
def list_roles():
    """List Kubernetes Roles with optional namespace filtering.

    Returns:
        JSON response with paginated list of Role dicts.
    """
    page, limit, namespace, label_selector, field_selector = parse_list_params()
    try:
        data = rbac_svc.list_roles(namespace=namespace)
        return jsonify(ApiResponse.ok(paginate(data, page, limit)).to_dict()), 200
    except ApiException as e:
        if e.status == 404:
            return not_found("Roles not found")
        return internal_error("Kubernetes API error")
    except Exception as e:
        logger.error("Unexpected error: %s", e)
        return internal_error("Failed to list roles")


@require_permissions(Permissions.KUBERNETES_VIEW)
def list_cluster_roles():
    """List all Kubernetes ClusterRoles.

    Returns:
        JSON response with paginated list of ClusterRole dicts.
    """
    page, limit, namespace, label_selector, field_selector = parse_list_params()
    try:
        data = rbac_svc.list_cluster_roles()
        return jsonify(ApiResponse.ok(paginate(data, page, limit)).to_dict()), 200
    except ApiException as e:
        if e.status == 404:
            return not_found("Cluster roles not found")
        return internal_error("Kubernetes API error")
    except Exception as e:
        logger.error("Unexpected error: %s", e)
        return internal_error("Failed to list cluster roles")


@require_permissions(Permissions.KUBERNETES_VIEW)
def list_role_bindings():
    """List Kubernetes RoleBindings with optional namespace filtering.

    Returns:
        JSON response with paginated list of RoleBinding dicts.
    """
    page, limit, namespace, label_selector, field_selector = parse_list_params()
    try:
        data = rbac_svc.list_role_bindings(namespace=namespace)
        return jsonify(ApiResponse.ok(paginate(data, page, limit)).to_dict()), 200
    except ApiException as e:
        if e.status == 404:
            return not_found("Role bindings not found")
        return internal_error("Kubernetes API error")
    except Exception as e:
        logger.error("Unexpected error: %s", e)
        return internal_error("Failed to list role bindings")


@require_permissions(Permissions.KUBERNETES_VIEW)
def list_cluster_role_bindings():
    """List all Kubernetes ClusterRoleBindings.

    Returns:
        JSON response with paginated list of ClusterRoleBinding dicts.
    """
    page, limit, namespace, label_selector, field_selector = parse_list_params()
    try:
        data = rbac_svc.list_cluster_role_bindings()
        return jsonify(ApiResponse.ok(paginate(data, page, limit)).to_dict()), 200
    except ApiException as e:
        if e.status == 404:
            return not_found("Cluster role bindings not found")
        return internal_error("Kubernetes API error")
    except Exception as e:
        logger.error("Unexpected error: %s", e)
        return internal_error("Failed to list cluster role bindings")


@require_permissions(Permissions.KUBERNETES_VIEW)
def list_service_accounts():
    """List Kubernetes ServiceAccounts with optional namespace filtering.

    Returns:
        JSON response with paginated list of ServiceAccount dicts.
    """
    page, limit, namespace, label_selector, field_selector = parse_list_params()
    try:
        data = rbac_svc.list_service_accounts(namespace=namespace)
        return jsonify(ApiResponse.ok(paginate(data, page, limit)).to_dict()), 200
    except ApiException as e:
        if e.status == 404:
            return not_found("Service accounts not found")
        return internal_error("Kubernetes API error")
    except Exception as e:
        logger.error("Unexpected error: %s", e)
        return internal_error("Failed to list service accounts")
