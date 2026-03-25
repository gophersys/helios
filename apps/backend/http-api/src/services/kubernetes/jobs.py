import logging

from kubernetes.client.exceptions import ApiException

from .client import get_batch_v1_api, get_core_v1_api
from .serializers import serialize_job

logger = logging.getLogger(__name__)


def list_jobs(
    namespace: str | None = None,
    label_selector: str | None = None,
    field_selector: str | None = None,
) -> list[dict]:
    batch = get_batch_v1_api()
    kwargs = {}
    if label_selector:
        kwargs["label_selector"] = label_selector
    if field_selector:
        kwargs["field_selector"] = field_selector

    if namespace:
        job_list = batch.list_namespaced_job(namespace, **kwargs)
    else:
        job_list = batch.list_job_for_all_namespaces(**kwargs)

    return [serialize_job(j) for j in job_list.items]


def get_job(namespace: str, name: str) -> dict | None:
    batch = get_batch_v1_api()
    try:
        job = batch.read_namespaced_job(name, namespace)
    except ApiException as e:
        logger.warning("Failed to read job %s/%s: %s", namespace, name, e.reason)
        return None

    serialized = serialize_job(job)

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
    except ApiException as e:
        logger.warning("Failed to list pods for job %s/%s: %s", namespace, name, e.reason)
        serialized["pods"] = []

    return serialized


def delete_job(namespace: str, name: str) -> bool:
    from kubernetes.client import V1DeleteOptions
    batch = get_batch_v1_api()
    try:
        batch.delete_namespaced_job(
            name, namespace,
            body=V1DeleteOptions(propagation_policy="Background")
        )
        return True
    except ApiException as e:
        logger.warning("Failed to delete job %s/%s: %s", namespace, name, e.reason)
        return False
