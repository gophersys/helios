# Phase 2 — Backend: Service Modules for All Resource Types

## Objective

Create service modules for pods, deployments, services, jobs, and configmaps/secrets. Each module wraps the K8s API and returns serialized dicts. Mutating actions (delete, scale, restart) are also in the relevant service module.

---

## 1. Create `src/services/kubernetes/pods.py`

```python
from .client import get_core_v1_api
from .serializers import serialize_pod, serialize_pod_detail, serialize_event


def list_pods(namespace: str | None = None) -> list[dict]:
    core = get_core_v1_api()

    if namespace:
        pod_list = core.list_namespaced_pod(namespace)
    else:
        pod_list = core.list_pod_for_all_namespaces()

    return [serialize_pod(p) for p in pod_list.items]


def get_pod(namespace: str, name: str) -> dict | None:
    core = get_core_v1_api()
    try:
        pod = core.read_namespaced_pod(name, namespace)
    except Exception:
        return None

    serialized = serialize_pod_detail(pod)

    # Fetch events for this pod
    try:
        field = f"involvedObject.name={name},involvedObject.namespace={namespace},involvedObject.kind=Pod"
        events = core.list_namespaced_event(namespace, field_selector=field)
        serialized["events"] = [serialize_event(e) for e in events.items]
    except Exception:
        serialized["events"] = []

    return serialized


def delete_pod(namespace: str, name: str) -> bool:
    core = get_core_v1_api()
    try:
        core.delete_namespaced_pod(name, namespace)
        return True
    except Exception:
        return False
```

---

## 2. Create `src/services/kubernetes/deployments.py`

```python
from datetime import datetime, timezone

from .client import get_apps_v1_api, get_core_v1_api
from .serializers import serialize_deployment


def list_deployments(namespace: str | None = None) -> list[dict]:
    apps = get_apps_v1_api()

    if namespace:
        dep_list = apps.list_namespaced_deployment(namespace)
    else:
        dep_list = apps.list_deployment_for_all_namespaces()

    return [serialize_deployment(d) for d in dep_list.items]


def get_deployment(namespace: str, name: str) -> dict | None:
    apps = get_apps_v1_api()
    try:
        dep = apps.read_namespaced_deployment(name, namespace)
    except Exception:
        return None

    serialized = serialize_deployment(dep)

    # Include pods for this deployment via label selector
    try:
        core = get_core_v1_api()
        selector = dep.spec.selector.match_labels or {}
        label_selector = ",".join(f"{k}={v}" for k, v in selector.items())
        if label_selector:
            pods = core.list_namespaced_pod(namespace, label_selector=label_selector)
            serialized["pods"] = [
                {
                    "name": p.metadata.name,
                    "status": p.status.phase if p.status else "Unknown",
                    "ready": all(
                        (cs.ready or False)
                        for cs in (p.status.container_statuses or [])
                    ) if p.status and p.status.container_statuses else False,
                    "restarts": sum(
                        (cs.restart_count or 0)
                        for cs in (p.status.container_statuses or [])
                    ),
                    "nodeName": p.spec.node_name if p.spec else "",
                }
                for p in pods.items
            ]
    except Exception:
        serialized["pods"] = []

    return serialized


def scale_deployment(namespace: str, name: str, replicas: int) -> bool:
    apps = get_apps_v1_api()
    try:
        apps.patch_namespaced_deployment_scale(
            name, namespace,
            body={"spec": {"replicas": replicas}}
        )
        return True
    except Exception:
        return False


def restart_deployment(namespace: str, name: str) -> bool:
    """Trigger a rolling restart by patching the template annotation."""
    apps = get_apps_v1_api()
    try:
        now = datetime.now(timezone.utc).isoformat()
        body = {
            "spec": {
                "template": {
                    "metadata": {
                        "annotations": {
                            "kubectl.kubernetes.io/restartedAt": now
                        }
                    }
                }
            }
        }
        apps.patch_namespaced_deployment(name, namespace, body=body)
        return True
    except Exception:
        return False
```

---

## 3. Create `src/services/kubernetes/services_k8s.py`

Named `services_k8s.py` to avoid collision with the `services/` directory name.

```python
from .client import get_core_v1_api
from .serializers import serialize_service


def list_services(namespace: str | None = None) -> list[dict]:
    core = get_core_v1_api()

    if namespace:
        svc_list = core.list_namespaced_service(namespace)
    else:
        svc_list = core.list_service_for_all_namespaces()

    return [serialize_service(s) for s in svc_list.items]


def get_service(namespace: str, name: str) -> dict | None:
    core = get_core_v1_api()
    try:
        svc = core.read_namespaced_service(name, namespace)
    except Exception:
        return None

    serialized = serialize_service(svc)

    # Get endpoints for this service
    try:
        endpoints = core.read_namespaced_endpoints(name, namespace)
        ep_list = []
        if endpoints.subsets:
            for subset in endpoints.subsets:
                addresses = [a.ip for a in (subset.addresses or [])]
                ports = [
                    {"port": p.port, "protocol": p.protocol or "TCP"}
                    for p in (subset.ports or [])
                ]
                ep_list.append({"addresses": addresses, "ports": ports})
        serialized["endpoints"] = ep_list
    except Exception:
        serialized["endpoints"] = []

    return serialized
```

---

## 4. Create `src/services/kubernetes/jobs.py`

```python
from .client import get_batch_v1_api, get_core_v1_api
from .serializers import serialize_job


def list_jobs(namespace: str | None = None) -> list[dict]:
    batch = get_batch_v1_api()

    if namespace:
        job_list = batch.list_namespaced_job(namespace)
    else:
        job_list = batch.list_job_for_all_namespaces()

    return [serialize_job(j) for j in job_list.items]


def get_job(namespace: str, name: str) -> dict | None:
    batch = get_batch_v1_api()
    try:
        job = batch.read_namespaced_job(name, namespace)
    except Exception:
        return None

    serialized = serialize_job(job)

    # Get pods created by this job
    try:
        core = get_core_v1_api()
        label_selector = f"job-name={name}"
        pods = core.list_namespaced_pod(namespace, label_selector=label_selector)
        serialized["pods"] = [
            {
                "name": p.metadata.name,
                "status": p.status.phase if p.status else "Unknown",
                "restarts": sum(
                    (cs.restart_count or 0)
                    for cs in (p.status.container_statuses or [])
                ),
            }
            for p in pods.items
        ]
    except Exception:
        serialized["pods"] = []

    return serialized


def delete_job(namespace: str, name: str) -> bool:
    """Delete a job and its pods."""
    from kubernetes.client import V1DeleteOptions
    batch = get_batch_v1_api()
    try:
        batch.delete_namespaced_job(
            name, namespace,
            body=V1DeleteOptions(propagation_policy="Background")
        )
        return True
    except Exception:
        return False
```

---

## 5. Create `src/services/kubernetes/configmaps.py`

Handles both ConfigMaps and Secrets.

```python
from .client import get_core_v1_api
from .serializers import serialize_configmap, serialize_secret


def list_configmaps(namespace: str | None = None) -> list[dict]:
    core = get_core_v1_api()

    if namespace:
        cm_list = core.list_namespaced_config_map(namespace)
    else:
        cm_list = core.list_config_map_for_all_namespaces()

    return [serialize_configmap(cm) for cm in cm_list.items]


def get_configmap(namespace: str, name: str) -> dict | None:
    core = get_core_v1_api()
    try:
        cm = core.read_namespaced_config_map(name, namespace)
    except Exception:
        return None

    return serialize_configmap(cm, include_data=True)


def list_secrets(namespace: str | None = None) -> list[dict]:
    core = get_core_v1_api()

    if namespace:
        secret_list = core.list_namespaced_secret(namespace)
    else:
        secret_list = core.list_secret_for_all_namespaces()

    return [serialize_secret(s) for s in secret_list.items]


def get_secret(namespace: str, name: str) -> dict | None:
    core = get_core_v1_api()
    try:
        secret = core.read_namespaced_secret(name, namespace)
    except Exception:
        return None

    return serialize_secret(secret, include_data=True)
```

---

## Verification

1. `python3 -m py_compile src/services/kubernetes/pods.py`
2. `python3 -m py_compile src/services/kubernetes/deployments.py`
3. `python3 -m py_compile src/services/kubernetes/services_k8s.py`
4. `python3 -m py_compile src/services/kubernetes/jobs.py`
5. `python3 -m py_compile src/services/kubernetes/configmaps.py`
6. All five import without error when K8s client is initialized.

---

## Overview Update

```
- [x] Phase 2 — Backend: service modules for all resource types
```
