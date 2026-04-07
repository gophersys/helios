import logging

from kubernetes.client.exceptions import ApiException

from .client import get_core_v1_api
from .serializers import serialize_service

logger = logging.getLogger(__name__)


def list_services(
    namespace: str | None = None,
    label_selector: str | None = None,
) -> list[dict]:
    """List Kubernetes Services across all namespaces or within a specific namespace.

    Args:
        namespace: Limit results to this namespace. If None, lists cluster-wide.
        label_selector: Optional Kubernetes label selector string.

    Returns:
        List of serialized Service dicts.
    """
    core = get_core_v1_api()
    kwargs = {}
    if label_selector:
        kwargs["label_selector"] = label_selector

    if namespace:
        svc_list = core.list_namespaced_service(namespace, **kwargs)
    else:
        svc_list = core.list_service_for_all_namespaces(**kwargs)

    return [serialize_service(s) for s in svc_list.items]


def get_service(namespace: str, name: str) -> dict | None:
    """Fetch a single Service by namespace and name, including endpoints.

    Args:
        namespace: Kubernetes namespace of the Service.
        name: Name of the Service.

    Returns:
        Serialized Service dict with an 'endpoints' list, or None if not found.
    """
    core = get_core_v1_api()
    try:
        svc = core.read_namespaced_service(name, namespace)
    except ApiException as e:
        logger.warning("Failed to read service %s/%s: %s", namespace, name, e.reason)
        return None

    serialized = serialize_service(svc)

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
    except ApiException as e:
        logger.warning("Failed to read endpoints for %s/%s: %s", namespace, name, e.reason)
        serialized["endpoints"] = []

    return serialized
