from .client import get_rbac_v1_api, get_core_v1_api
from .serializers import serialize_role, serialize_role_binding, serialize_service_account


def list_roles(namespace: str | None = None) -> list[dict]:
    """List Kubernetes Roles within a namespace or across all namespaces.

    Args:
        namespace: Limit results to this namespace. If None, lists cluster-wide.

    Returns:
        List of serialized Role dicts.
    """
    rbac = get_rbac_v1_api()

    if namespace:
        role_list = rbac.list_namespaced_role(namespace)
    else:
        role_list = rbac.list_role_for_all_namespaces()

    return [serialize_role(r) for r in role_list.items]


def list_cluster_roles() -> list[dict]:
    """List all Kubernetes ClusterRoles.

    Returns:
        List of serialized ClusterRole dicts.
    """
    rbac = get_rbac_v1_api()
    role_list = rbac.list_cluster_role()
    return [serialize_role(r) for r in role_list.items]


def list_role_bindings(namespace: str | None = None) -> list[dict]:
    """List RoleBindings within a namespace or across all namespaces.

    Args:
        namespace: Limit results to this namespace. If None, lists cluster-wide.

    Returns:
        List of serialized RoleBinding dicts.
    """
    rbac = get_rbac_v1_api()

    if namespace:
        binding_list = rbac.list_namespaced_role_binding(namespace)
    else:
        binding_list = rbac.list_role_binding_for_all_namespaces()

    return [serialize_role_binding(b) for b in binding_list.items]


def list_cluster_role_bindings() -> list[dict]:
    """List all Kubernetes ClusterRoleBindings.

    Returns:
        List of serialized ClusterRoleBinding dicts.
    """
    rbac = get_rbac_v1_api()
    binding_list = rbac.list_cluster_role_binding()
    return [serialize_role_binding(b) for b in binding_list.items]


def list_service_accounts(namespace: str | None = None) -> list[dict]:
    """List ServiceAccounts within a namespace or across all namespaces.

    Args:
        namespace: Limit results to this namespace. If None, lists cluster-wide.

    Returns:
        List of serialized ServiceAccount dicts.
    """
    core = get_core_v1_api()

    if namespace:
        sa_list = core.list_namespaced_service_account(namespace)
    else:
        sa_list = core.list_service_account_for_all_namespaces()

    return [serialize_service_account(sa) for sa in sa_list.items]
