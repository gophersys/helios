import logging

from kubernetes.client.exceptions import ApiException

from .client import get_core_v1_api
from .serializers import serialize_configmap, serialize_secret

logger = logging.getLogger(__name__)


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
    except ApiException as e:
        logger.warning("Failed to read configmap %s/%s: %s", namespace, name, e.reason)
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
    except ApiException as e:
        logger.warning("Failed to read secret %s/%s: %s", namespace, name, e.reason)
        return None

    return serialize_secret(secret, include_data=True)
