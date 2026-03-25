# Phase 1 — Backend: Permissions, Cache, Serializers

## Objective

Create the foundational backend infrastructure for the system monitor: new permissions, a TTL cache to avoid hammering the K8s API, and serializer functions that convert raw K8s Python objects into clean dicts.

---

## 1. Modify `src/lib/permissions.py`

Add two new permissions at the end of the permissions class:

```python
# Admin - System
ADMIN_SYSTEM_VIEW = "Concord.Admin.System.View"
ADMIN_SYSTEM_MANAGE = "Concord.Admin.System.Manage"
```

---

## 2. Create `src/services/kubernetes/cache.py`

Simple TTL dictionary cache. Keys are strings, values are any object. Thread-safe via a lock.

```python
import threading
import time
from typing import Any, Optional

_cache: dict[str, tuple[float, Any]] = {}
_lock = threading.Lock()


def cache_get(key: str) -> Optional[Any]:
    with _lock:
        entry = _cache.get(key)
        if entry is None:
            return None
        expires_at, value = entry
        if time.monotonic() > expires_at:
            del _cache[key]
            return None
        return value


def cache_set(key: str, value: Any, ttl_seconds: float = 5.0) -> None:
    with _lock:
        _cache[key] = (time.monotonic() + ttl_seconds, value)


def cache_delete(key: str) -> None:
    with _lock:
        _cache.pop(key, None)


def cache_clear() -> None:
    with _lock:
        _cache.clear()


def cached(key: str, ttl: float = 5.0):
    """Decorator that caches the return value of a function."""
    def decorator(fn):
        def wrapper(*args, **kwargs):
            result = cache_get(key)
            if result is not None:
                return result
            result = fn(*args, **kwargs)
            cache_set(key, result, ttl)
            return result
        return wrapper
    return decorator
```

---

## 3. Create `src/services/kubernetes/serializers.py`

Mapper functions for K8s objects. Each function takes a kubernetes-client Python object and returns a plain dict. These are the ONLY place that touches K8s object internals — everything else works with dicts.

```python
from datetime import datetime, timezone
from typing import Any, Optional


def _isoformat(dt: Optional[datetime]) -> Optional[str]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


def _age(dt: Optional[datetime]) -> str:
    if dt is None:
        return "Unknown"
    now = datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    delta = now - dt
    days = delta.days
    hours = delta.seconds // 3600
    minutes = (delta.seconds % 3600) // 60
    if days > 0:
        return f"{days}d {hours}h"
    if hours > 0:
        return f"{hours}h {minutes}m"
    return f"{minutes}m"


def serialize_namespace(ns) -> dict:
    return {
        "name": ns.metadata.name,
        "status": ns.status.phase if ns.status else "Unknown",
        "createdAt": _isoformat(ns.metadata.creation_timestamp),
        "age": _age(ns.metadata.creation_timestamp),
    }


def serialize_node(node) -> dict:
    status = node.status
    spec = node.spec
    metadata = node.metadata

    # Determine Ready status
    conditions = []
    ready_status = "Unknown"
    if status and status.conditions:
        for c in status.conditions:
            conditions.append({
                "type": c.type,
                "status": c.status,
                "reason": c.reason or "",
                "message": c.message or "",
                "lastTransition": _isoformat(c.last_transition_time),
            })
            if c.type == "Ready":
                ready_status = "Ready" if c.status == "True" else "NotReady"

    # Roles from labels
    roles = []
    labels = metadata.labels or {}
    for key in labels:
        if key.startswith("node-role.kubernetes.io/"):
            roles.append(key.split("/")[1])
    if not roles:
        roles = ["worker"]

    # Node info
    node_info = status.node_info if status else None

    # Capacity and allocatable
    capacity = {}
    allocatable = {}
    if status:
        if status.capacity:
            capacity = {k: str(v) for k, v in status.capacity.items() if k in ("cpu", "memory", "pods", "ephemeral-storage")}
        if status.allocatable:
            allocatable = {k: str(v) for k, v in status.allocatable.items() if k in ("cpu", "memory", "pods", "ephemeral-storage")}

    # Internal IP
    internal_ip = ""
    if status and status.addresses:
        for addr in status.addresses:
            if addr.type == "InternalIP":
                internal_ip = addr.address
                break

    return {
        "name": metadata.name,
        "status": ready_status,
        "roles": roles,
        "internalIp": internal_ip,
        "osImage": node_info.os_image if node_info else "",
        "kubeletVersion": node_info.kubelet_version if node_info else "",
        "containerRuntime": node_info.container_runtime_version if node_info else "",
        "architecture": node_info.architecture if node_info else "",
        "capacity": capacity,
        "allocatable": allocatable,
        "conditions": conditions,
        "labels": dict(labels),
        "annotations": dict(metadata.annotations or {}),
        "taints": [
            {"key": t.key, "value": t.value or "", "effect": t.effect}
            for t in (spec.taints or [])
        ],
        "unschedulable": bool(spec.unschedulable),
        "createdAt": _isoformat(metadata.creation_timestamp),
        "age": _age(metadata.creation_timestamp),
    }


def serialize_event(event) -> dict:
    obj = event.involved_object
    return {
        "type": event.type or "Normal",
        "reason": event.reason or "",
        "message": event.message or "",
        "object": f"{obj.kind.lower()}/{obj.name}" if obj else "",
        "namespace": obj.namespace or "" if obj else "",
        "count": event.count or 1,
        "firstSeen": _isoformat(event.first_timestamp),
        "lastSeen": _isoformat(event.last_timestamp or event.metadata.creation_timestamp),
        "source": event.source.component if event.source else "",
    }
```

---

## 4. Verify `src/services/kubernetes/client.py`

Confirm the following functions already exist (they do — no changes needed):
- `get_k8s_client()` — returns the raw `ApiClient` instance
- `get_core_v1_api()` — returns `CoreV1Api`
- `get_apps_v1_api()` — returns `AppsV1Api`
- `get_batch_v1_api()` — returns `BatchV1Api`
- `get_networking_v1_api()` — returns `NetworkingV1Api`

**Do NOT add a `get_client()` function** — `get_k8s_client()` already serves this purpose.

---

## Verification

1. `python3 -m py_compile src/services/kubernetes/cache.py` — passes
2. `python3 -m py_compile src/services/kubernetes/serializers.py` — passes
3. `python3 -m py_compile src/lib/permissions.py` — passes
4. Backend starts without error: `source .venv/bin/activate && source .env && python3 src/main.py`

---

## Overview Update

After this phase, mark Phase 1 as complete:

```
- [x] Phase 1 — Backend: permissions, cache, serializers
```
