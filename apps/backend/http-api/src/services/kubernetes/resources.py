import yaml

from kubernetes.client import ApiException

from .client import get_core_v1_api, get_apps_v1_api, get_batch_v1_api, get_networking_v1_api, get_k8s_client


# Map of supported resource kinds to their API methods
RESOURCE_MAP = {
    "pod": {
        "api": "core",
        "read": "read_namespaced_pod",
        "patch": "patch_namespaced_pod",
        "delete": "delete_namespaced_pod",
    },
    "deployment": {
        "api": "apps",
        "read": "read_namespaced_deployment",
        "patch": "patch_namespaced_deployment",
        "delete": "delete_namespaced_deployment",
    },
    "service": {
        "api": "core",
        "read": "read_namespaced_service",
        "patch": "patch_namespaced_service",
        "delete": "delete_namespaced_service",
    },
    "job": {
        "api": "batch",
        "read": "read_namespaced_job",
        "patch": "patch_namespaced_job",
        "delete": "delete_namespaced_job",
    },
    "configmap": {
        "api": "core",
        "read": "read_namespaced_config_map",
        "patch": "patch_namespaced_config_map",
        "delete": "delete_namespaced_config_map",
    },
    "secret": {
        "api": "core",
        "read": "read_namespaced_secret",
        "patch": "patch_namespaced_secret",
        "delete": "delete_namespaced_secret",
    },
    "daemonset": {
        "api": "apps",
        "read": "read_namespaced_daemon_set",
        "patch": "patch_namespaced_daemon_set",
        "delete": "delete_namespaced_daemon_set",
    },
    "statefulset": {
        "api": "apps",
        "read": "read_namespaced_stateful_set",
        "patch": "patch_namespaced_stateful_set",
        "delete": "delete_namespaced_stateful_set",
    },
    "ingress": {
        "api": "networking",
        "read": "read_namespaced_ingress",
        "patch": "patch_namespaced_ingress",
        "delete": "delete_namespaced_ingress",
    },
}

API_VERSION_MAP = {
    "pod": "v1",
    "service": "v1",
    "configmap": "v1",
    "secret": "v1",
    "deployment": "apps/v1",
    "daemonset": "apps/v1",
    "statefulset": "apps/v1",
    "job": "batch/v1",
    "ingress": "networking.k8s.io/v1",
}

KIND_DISPLAY = {
    "pod": "Pod",
    "deployment": "Deployment",
    "service": "Service",
    "job": "Job",
    "configmap": "ConfigMap",
    "secret": "Secret",
    "daemonset": "DaemonSet",
    "statefulset": "StatefulSet",
    "ingress": "Ingress",
}


def _get_api_client(api_name: str):
    """Get the appropriate K8s API client by name."""
    if api_name == "core":
        return get_core_v1_api()
    elif api_name == "apps":
        return get_apps_v1_api()
    elif api_name == "batch":
        return get_batch_v1_api()
    elif api_name == "networking":
        return get_networking_v1_api()
    raise ValueError(f"Unknown API: {api_name}")


def get_resource_yaml(kind: str, namespace: str, name: str) -> dict | None:
    """
    Fetch a resource and return it as a YAML string.
    Returns { kind, apiVersion, yaml } or None if not found.
    """
    kind_lower = kind.lower()
    if kind_lower not in RESOURCE_MAP:
        raise ValueError(f"Unsupported resource kind: {kind}")

    config = RESOURCE_MAP[kind_lower]
    api_client = _get_api_client(config["api"])
    read_fn = getattr(api_client, config["read"])

    try:
        resource = read_fn(name, namespace)
    except ApiException as e:
        if e.status == 404:
            return None
        raise

    # Convert to dict using the K8s client serializer
    api = get_k8s_client()
    resource_dict = api.sanitize_for_serialization(resource)

    # Clean up managed fields and other noise
    metadata = resource_dict.get("metadata", {})
    metadata.pop("managedFields", None)
    metadata.pop("resourceVersion", None)
    metadata.pop("uid", None)
    metadata.pop("selfLink", None)
    metadata.pop("generation", None)

    # Remove status for apply (status is server-managed)
    clean_dict = {k: v for k, v in resource_dict.items() if k != "status"}

    yaml_str = yaml.dump(clean_dict, default_flow_style=False, sort_keys=False)

    return {
        "kind": KIND_DISPLAY.get(kind_lower, kind),
        "apiVersion": API_VERSION_MAP.get(kind_lower, "v1"),
        "yaml": yaml_str,
    }


def apply_resource_yaml(kind: str, namespace: str, name: str, yaml_str: str) -> dict:
    """
    Apply a YAML string to update a resource.
    Uses strategic merge patch.
    Returns the updated resource as YAML.
    """
    kind_lower = kind.lower()
    if kind_lower not in RESOURCE_MAP:
        raise ValueError(f"Unsupported resource kind: {kind}")

    config = RESOURCE_MAP[kind_lower]
    api_client = _get_api_client(config["api"])
    patch_fn = getattr(api_client, config["patch"])

    try:
        body = yaml.safe_load(yaml_str)
    except yaml.YAMLError as e:
        raise ValueError(f"Invalid YAML: {str(e)}")

    if not isinstance(body, dict):
        raise ValueError("YAML must be a mapping")

    # Remove fields that shouldn't be patched
    body.pop("status", None)
    metadata = body.get("metadata", {})
    metadata.pop("resourceVersion", None)
    metadata.pop("uid", None)
    metadata.pop("creationTimestamp", None)
    metadata.pop("managedFields", None)

    try:
        patch_fn(name, namespace, body=body)
    except ApiException as e:
        raise RuntimeError(f"Failed to apply: {e.reason} — {e.body}")

    # Return updated YAML
    return get_resource_yaml(kind, namespace, name)


def delete_resource(kind: str, namespace: str, name: str) -> bool:
    """Delete a resource by kind, namespace, name."""
    kind_lower = kind.lower()
    if kind_lower not in RESOURCE_MAP:
        raise ValueError(f"Unsupported resource kind: {kind}")

    config = RESOURCE_MAP[kind_lower]
    api_client = _get_api_client(config["api"])
    delete_fn = getattr(api_client, config["delete"])

    try:
        delete_fn(name, namespace)
        return True
    except ApiException:
        return False
