"""Build the env block passed to the test-runner container.

Manufacturing (persistent K8s Deployment) and validation (ephemeral
K8s Job) share the runner image, the storage layout, and most of the
env contract — only their lifecycle and a few mode-specific fields
diverge. This module is the single source of truth for the values
both paths inject; their YAML templates still own the K8s-shape
specifics (kind, restartPolicy, etc).

The output is a plain ``dict[str, str]`` that the caller substitutes
into its ``{{VAR}}`` template placeholders. Storage URLs are FQDN-
qualified so a pod in a different namespace (validation/manufacturing
worker namespaces vs. the http-api namespace) can resolve the MinIO
service.
"""

from __future__ import annotations

import os
from typing import Optional
from urllib.parse import urlparse, urlunparse

from config.env import env_config


def _qualify_storage_url(url: str, namespace: str) -> str:
    """Expand a short K8s service hostname to a cross-namespace FQDN.

    The runner pod is placed on a worker node and may live in a
    different namespace than the MinIO service. ``concord-minio`` resolves
    locally inside ``staging`` but not from another namespace; the FQDN
    form ``concord-minio.staging.svc.cluster.local`` resolves everywhere.
    """
    if "://" not in url or ".svc" in url:
        return url
    parsed = urlparse(url)
    if not parsed.hostname:
        return url
    host_parts = parsed.hostname.split(".")
    if len(host_parts) > 1:
        return url
    fqdn = f"{parsed.hostname}.{namespace}.svc.cluster.local"
    new_netloc = f"{fqdn}:{parsed.port}" if parsed.port else fqdn
    return urlunparse(parsed._replace(netloc=new_netloc))


def build_common_runner_env(
    *,
    product_slug: str,
    test_package_version: str,
    api_key: str,
    api_url: Optional[str] = None,
) -> dict[str, str]:
    """Return the env vars shared by validation jobs and manufacturing runners.

    Args:
        product_slug: Concord product slug (e.g. "alpha"). Drives the
            storage key that the entrypoint downloads.
        test_package_version: Exact version string from the resolved
            TestPackage. The runner refuses to start with this unset
            (no more "latest" fallback).
        api_key: API key for the runner's reporter callbacks.
        api_url: Override for the Concord API URL. Defaults to the
            environment's configured URL.

    Returns:
        Flat ``{key: value}`` dict — the caller injects these into its
        K8s YAML template via simple string replacement.
    """
    namespace = env_config.ENVIRONMENT
    storage_url = _qualify_storage_url(env_config.STORAGE_URL, namespace)
    resolved_api_url = api_url or os.environ.get("CONCORD_API_URL", env_config.CONCORD_API_URL)

    return {
        "ENVIRONMENT": env_config.ENVIRONMENT,
        "PRODUCT_SLUG": product_slug,
        "TEST_PACKAGE_VERSION": test_package_version,
        "CONCORD_API_URL": resolved_api_url,
        "CONCORD_API_KEY": api_key,
        "CONCORD_API_HOST": env_config.CONCORD_API_HOST,
        "STORAGE_URL": storage_url,
        "STORAGE_ACCESS_KEY": env_config.STORAGE_ACCESS_KEY,
        "STORAGE_SECRET_ACCESS_KEY": env_config.STORAGE_SECRET_ACCESS_KEY,
        "STORAGE_BUCKET_NAME": env_config.STORAGE_BUCKET_NAME,
        "MTIB_PORT": str(env_config.MTIB_PORT),
        "LOG_LEVEL": "4",
        "ARTIFACTS_DIR": "/var/log/validation",
    }
