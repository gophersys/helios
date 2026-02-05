import logging

from kubernetes.client.exceptions import ApiException

from .client import get_core_v1_api
from .serializers import serialize_service

logger = logging.getLogger(__name__)


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
