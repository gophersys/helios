import logging
from datetime import datetime, timezone

from kubernetes.client.exceptions import ApiException

from .client import get_apps_v1_api, get_core_v1_api
from .serializers import serialize_deployment

logger = logging.getLogger(__name__)


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
    except ApiException as e:
        logger.warning("Failed to read deployment %s/%s: %s", namespace, name, e.reason)
        return None

    serialized = serialize_deployment(dep)

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
    except ApiException as e:
        logger.warning("Failed to list pods for deployment %s/%s: %s", namespace, name, e.reason)
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
    except ApiException as e:
        logger.warning("Failed to scale deployment %s/%s: %s", namespace, name, e.reason)
        return False


def restart_deployment(namespace: str, name: str) -> bool:
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
    except ApiException as e:
        logger.warning("Failed to restart deployment %s/%s: %s", namespace, name, e.reason)
        return False
