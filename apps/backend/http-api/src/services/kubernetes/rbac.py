from .client import get_rbac_v1_api, get_core_v1_api
from .serializers import serialize_role, serialize_role_binding, serialize_service_account


def list_roles(namespace: str | None = None) -> list[dict]:
    rbac = get_rbac_v1_api()

    if namespace:
        role_list = rbac.list_namespaced_role(namespace)
    else:
        role_list = rbac.list_role_for_all_namespaces()

    return [serialize_role(r) for r in role_list.items]


def list_cluster_roles() -> list[dict]:
    rbac = get_rbac_v1_api()
    role_list = rbac.list_cluster_role()
    return [serialize_role(r) for r in role_list.items]


def list_role_bindings(namespace: str | None = None) -> list[dict]:
    rbac = get_rbac_v1_api()

    if namespace:
        binding_list = rbac.list_namespaced_role_binding(namespace)
    else:
        binding_list = rbac.list_role_binding_for_all_namespaces()

    return [serialize_role_binding(b) for b in binding_list.items]


def list_cluster_role_bindings() -> list[dict]:
    rbac = get_rbac_v1_api()
    binding_list = rbac.list_cluster_role_binding()
    return [serialize_role_binding(b) for b in binding_list.items]


def list_service_accounts(namespace: str | None = None) -> list[dict]:
    core = get_core_v1_api()

    if namespace:
        sa_list = core.list_namespaced_service_account(namespace)
    else:
        sa_list = core.list_service_account_for_all_namespaces()

    return [serialize_service_account(sa) for sa in sa_list.items]
