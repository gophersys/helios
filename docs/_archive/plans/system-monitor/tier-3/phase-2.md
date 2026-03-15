# Phase 2 — Backend: RBAC Service Module

## Objective

Create a service module that queries RBAC resources: Roles, ClusterRoles, RoleBindings, ClusterRoleBindings, and ServiceAccounts. All read-only.

---

## 1. Modify `src/services/kubernetes/client.py`

Add the RBAC API accessor:

```python
def get_rbac_v1_api() -> k8s_client.RbacAuthorizationV1Api:
    """Get RBAC V1 API client using the global Kubernetes client"""
    return k8s_client.RbacAuthorizationV1Api(get_k8s_client())
```

---

## 2. Modify `src/services/kubernetes/serializers.py`

Add RBAC serializer functions at the end of the file.

```python
def serialize_role(role) -> dict:
    metadata = role.metadata
    rules = []
    for r in (role.rules or []):
        rules.append({
            "apiGroups": list(r.api_groups or [""]),
            "resources": list(r.resources or []),
            "verbs": list(r.verbs or []),
            "resourceNames": list(r.resource_names or []),
        })

    return {
        "name": metadata.name,
        "namespace": getattr(metadata, "namespace", None) or "",
        "rules": rules,
        "labels": dict(metadata.labels or {}),
        "createdAt": _isoformat(metadata.creation_timestamp),
        "age": _age(metadata.creation_timestamp),
    }


def serialize_role_binding(binding) -> dict:
    metadata = binding.metadata
    role_ref = binding.role_ref

    subjects = []
    for s in (binding.subjects or []):
        subjects.append({
            "kind": s.kind,
            "name": s.name,
            "namespace": getattr(s, "namespace", None) or "",
        })

    return {
        "name": metadata.name,
        "namespace": getattr(metadata, "namespace", None) or "",
        "roleRef": {
            "kind": role_ref.kind if role_ref else "",
            "name": role_ref.name if role_ref else "",
        },
        "subjects": subjects,
        "createdAt": _isoformat(metadata.creation_timestamp),
        "age": _age(metadata.creation_timestamp),
    }


def serialize_service_account(sa) -> dict:
    metadata = sa.metadata
    secrets = [s.name for s in (sa.secrets or [])] if sa.secrets else []

    return {
        "name": metadata.name,
        "namespace": metadata.namespace,
        "secrets": secrets,
        "labels": dict(metadata.labels or {}),
        "createdAt": _isoformat(metadata.creation_timestamp),
        "age": _age(metadata.creation_timestamp),
    }
```

---

## 3. Create `src/services/kubernetes/rbac.py`

```python
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
```

---

## Verification

1. `python3 -m py_compile src/services/kubernetes/rbac.py`
2. `python3 -m py_compile src/services/kubernetes/serializers.py`
3. `python3 -m py_compile src/services/kubernetes/client.py`
4. All import without error when K8s client is initialized

---

## Overview Update

```
- [x] Phase 2 — Backend: RBAC service module
```
