import re
from src.lib.errors import bad_request

# RFC 1123 DNS subdomain: lowercase alphanumeric, hyphens, max 253 chars
_K8S_NAME_RE = re.compile(r'^[a-z0-9]([a-z0-9\-]{0,251}[a-z0-9])?$')

ALLOWED_RESOURCE_KINDS = frozenset({
    "Pod", "Deployment", "StatefulSet", "DaemonSet", "ReplicaSet",
    "Service", "ConfigMap", "Secret", "Job", "CronJob", "Ingress",
})


def validate_k8s_name(value: str, field: str = "name"):
    """Return a bad_request response if value is not a valid K8s name, else None."""
    if not value or not isinstance(value, str) or not _K8S_NAME_RE.match(value):
        return bad_request(f"Invalid {field}: must be lowercase alphanumeric with hyphens")
    return None


def validate_resource_kind(kind: str):
    """Return a bad_request response if kind is not in the allowlist, else None."""
    if kind not in ALLOWED_RESOURCE_KINDS:
        return bad_request(f"Resource kind '{kind}' is not supported")
    return None
