import logging

from kubernetes.client.exceptions import ApiException

from .client import get_core_v1_api
from .serializers import serialize_pod, serialize_pod_detail, serialize_event

logger = logging.getLogger(__name__)


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
    except ApiException as e:
        logger.warning("Failed to read pod %s/%s: %s", namespace, name, e.reason)
        return None

    serialized = serialize_pod_detail(pod)

    try:
        field = f"involvedObject.name={name},involvedObject.namespace={namespace},involvedObject.kind=Pod"
        events = core.list_namespaced_event(namespace, field_selector=field)
        serialized["events"] = [serialize_event(e) for e in events.items]
    except ApiException as e:
        logger.warning("Failed to list events for pod %s/%s: %s", namespace, name, e.reason)
        serialized["events"] = []

    return serialized


def delete_pod(namespace: str, name: str) -> bool:
    core = get_core_v1_api()
    try:
        core.delete_namespaced_pod(name, namespace)
        return True
    except ApiException as e:
        logger.warning("Failed to delete pod %s/%s: %s", namespace, name, e.reason)
        return False
