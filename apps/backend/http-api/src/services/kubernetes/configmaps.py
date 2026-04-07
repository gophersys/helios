import logging

from kubernetes.client.exceptions import ApiException

from .client import get_core_v1_api
from .serializers import serialize_configmap, serialize_secret

logger = logging.getLogger(__name__)


def list_configmaps(
    namespace: str | None = None,
    label_selector: str | None = None,
) -> list[dict]:
    """List ConfigMaps across all namespaces or within a specific namespace.

    Args:
        namespace: Limit results to this namespace. If None, lists cluster-wide.
        label_selector: Optional Kubernetes label selector string to filter results.

    Returns:
        List of serialized ConfigMap dicts.
    """
    core = get_core_v1_api()
    kwargs = {}
    if label_selector:
        kwargs["label_selector"] = label_selector

    if namespace:
        cm_list = core.list_namespaced_config_map(namespace, **kwargs)
    else:
        cm_list = core.list_config_map_for_all_namespaces(**kwargs)

    return [serialize_configmap(cm) for cm in cm_list.items]


def get_configmap(namespace: str, name: str) -> dict | None:
    """Fetch a single ConfigMap by namespace and name, including its data.

    Args:
        namespace: Kubernetes namespace of the ConfigMap.
        name: Name of the ConfigMap.

    Returns:
        Serialized ConfigMap dict with data included, or None if not found.
    """
    core = get_core_v1_api()
    try:
        cm = core.read_namespaced_config_map(name, namespace)
    except ApiException as e:
        logger.warning("Failed to read configmap %s/%s: %s", namespace, name, e.reason)
        return None

    return serialize_configmap(cm, include_data=True)


def list_secrets(
    namespace: str | None = None,
    label_selector: str | None = None,
) -> list[dict]:
    """List Secrets across all namespaces or within a specific namespace.

    Args:
        namespace: Limit results to this namespace. If None, lists cluster-wide.
        label_selector: Optional Kubernetes label selector string to filter results.

    Returns:
        List of serialized Secret dicts (without secret values).
    """
    core = get_core_v1_api()
    kwargs = {}
    if label_selector:
        kwargs["label_selector"] = label_selector

    if namespace:
        secret_list = core.list_namespaced_secret(namespace, **kwargs)
    else:
        secret_list = core.list_secret_for_all_namespaces(**kwargs)

    return [serialize_secret(s) for s in secret_list.items]


def get_secret(namespace: str, name: str) -> dict | None:
    """Fetch a single Secret by namespace and name, with masked value preview.

    Args:
        namespace: Kubernetes namespace of the Secret.
        name: Name of the Secret.

    Returns:
        Serialized Secret dict with masked data included, or None if not found.
    """
    core = get_core_v1_api()
    try:
        secret = core.read_namespaced_secret(name, namespace)
    except ApiException as e:
        logger.warning("Failed to read secret %s/%s: %s", namespace, name, e.reason)
        return None

    return serialize_secret(secret, include_data=True)
