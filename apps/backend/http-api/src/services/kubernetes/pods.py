import logging
from typing import Optional

from kubernetes.client.exceptions import ApiException

from .client import get_core_v1_api
from .serializers import serialize_pod, serialize_pod_detail, serialize_event

logger = logging.getLogger(__name__)


def list_pods(
    namespace: str | None = None,
    label_selector: str | None = None,
    field_selector: str | None = None,
) -> list[dict]:
    core = get_core_v1_api()
    kwargs = {}
    if label_selector:
        kwargs["label_selector"] = label_selector
    if field_selector:
        kwargs["field_selector"] = field_selector

    if namespace:
        pod_list = core.list_namespaced_pod(namespace, **kwargs)
    else:
        pod_list = core.list_pod_for_all_namespaces(**kwargs)

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


def get_pod_logs(
    namespace: str,
    name: str,
    container: str | None = None,
    tail_lines: int = 100,
    previous: bool = False,
    since_seconds: int | None = None,
) -> dict | None:
    """Fetch logs from a pod container.

    Returns dict with container name(s) and log text, or None if pod not found.
    """
    core = get_core_v1_api()

    # Verify pod exists
    try:
        pod = core.read_namespaced_pod(name, namespace)
    except ApiException as e:
        if e.status == 404:
            return None
        raise

    # If no container specified and pod has multiple, return logs for all
    containers = []
    if pod.spec and pod.spec.containers:
        containers = [c.name for c in pod.spec.containers]

    if container:
        target_containers = [container]
    elif len(containers) == 1:
        target_containers = containers
    else:
        target_containers = containers

    kwargs = {
        "tail_lines": tail_lines,
        "previous": previous,
    }
    if since_seconds is not None:
        kwargs["since_seconds"] = since_seconds

    logs = {}
    for c in target_containers:
        try:
            log_text = core.read_namespaced_pod_log(
                name, namespace, container=c, **kwargs
            )
            logs[c] = log_text or ""
        except ApiException as e:
            logs[c] = f"Error: {e.reason}"

    return {
        "podName": name,
        "namespace": namespace,
        "containers": target_containers,
        "logs": logs,
    }


def delete_pod(namespace: str, name: str) -> bool:
    core = get_core_v1_api()
    try:
        core.delete_namespaced_pod(name, namespace)
        return True
    except ApiException as e:
        logger.warning("Failed to delete pod %s/%s: %s", namespace, name, e.reason)
        return False
