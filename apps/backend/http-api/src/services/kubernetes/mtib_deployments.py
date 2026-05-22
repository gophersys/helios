"""Service for managing MTIB server K8s deployments."""
import logging
import os
import socket
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

import yaml  # type: ignore[import-untyped]

from config.env import env_config
from kubernetes.client.exceptions import ApiException
from src.services.kubernetes.client import get_apps_v1_api, get_core_v1_api

logger = logging.getLogger(__name__)

# Environment → K8s namespace mapping for MTIB deployments
_ENV_NAMESPACE_MAP = {
    "production": "production",
    "staging": "staging",
    "development": "development",
}


def _get_mtib_namespace() -> str:
    """Resolve the K8s namespace for MTIB deployments.

    Priority:
    1. MTIB_NAMESPACE env var (explicit override)
    2. ENVIRONMENT env var mapped to namespace
    3. Default: "development"
    """
    explicit = os.environ.get("MTIB_NAMESPACE", "").strip()
    if explicit:
        return explicit
    environment = os.environ.get("ENVIRONMENT", "development").strip().lower()
    return _ENV_NAMESPACE_MAP.get(environment, "development")


def create_mtib_deployment(
    node_hostname: str,
    fixture_id: str,
    deployment_id: str,
    slot_index: int,
    config: dict,
    claim_id: str = "",
) -> Optional[str]:
    """Create a K8s deployment for an MTIB server on a specific node.

    Returns the K8s deployment name on success, None on failure.

    ``claim_id`` tags the deployment with ``corekinect.com/claim-id`` so a
    DEV_HOLD claim teardown can find and delete only the deployments it
    created. Fixture-bound and standalone-node deployments leave it empty
    and survive ``delete_mtib_deployments_for_claim`` calls.
    """
    template_path = os.path.join(
        env_config.ASSETS_FOLDER, "templates", "mtib_server_deployment.yaml"
    )

    try:
        with open(template_path, "r") as f:
            template = f.read()
    except FileNotFoundError:
        logger.error("MTIB deployment template not found at %s", template_path)
        return None

    # Generate RFC 1123-compliant name
    deploy_name = f"mtib-{node_hostname}-s{slot_index}"
    if len(deploy_name) > 63:
        deploy_name = deploy_name[:63].rstrip("-")

    image = config.get("image", "containers.ad.corekinect.com/concord-mtib-server:latest")

    # Build env vars
    env_vars = config.get("env", {})
    motion_enabled = env_vars.get("MOTION_ENABLED", "false")
    metrics_enabled = env_vars.get("METRICS_ENABLED", "false")
    log_level = env_vars.get("LOG_LEVEL", "4")

    # Resource limits
    resources = config.get("resources", {})
    cpu_req = resources.get("requests", {}).get("cpu", "250m")
    mem_req = resources.get("requests", {}).get("memory", "256Mi")
    cpu_lim = resources.get("limits", {}).get("cpu", "2000m")
    mem_lim = resources.get("limits", {}).get("memory", "1024Mi")

    # Substitute variables
    manifest = template
    manifest = manifest.replace("{{DEPLOYMENT_NAME}}", deploy_name)
    manifest = manifest.replace("{{NODE_HOSTNAME}}", node_hostname)
    manifest = manifest.replace("{{FIXTURE_ID}}", fixture_id)
    manifest = manifest.replace("{{DEPLOYMENT_ID}}", deployment_id)
    manifest = manifest.replace("{{CLAIM_ID}}", claim_id or "")
    manifest = manifest.replace("{{IMAGE}}", image)
    manifest = manifest.replace("{{MOTION_ENABLED}}", motion_enabled)
    manifest = manifest.replace("{{METRICS_ENABLED}}", metrics_enabled)
    manifest = manifest.replace("{{LOG_LEVEL}}", log_level)
    manifest = manifest.replace("{{CPU_REQUEST}}", cpu_req)
    manifest = manifest.replace("{{MEMORY_REQUEST}}", mem_req)
    manifest = manifest.replace("{{CPU_LIMIT}}", cpu_lim)
    manifest = manifest.replace("{{MEMORY_LIMIT}}", mem_lim)

    try:
        spec = yaml.safe_load(manifest)
        namespace = _get_mtib_namespace()
        apps_v1 = get_apps_v1_api()
        apps_v1.create_namespaced_deployment(namespace=namespace, body=spec)
        logger.info("Created K8s deployment: %s", deploy_name)
        return deploy_name
    except ApiException as e:
        if e.status == 409:
            logger.warning("K8s deployment %s already exists", deploy_name)
            return deploy_name
        logger.error("Failed to create K8s deployment %s: %s", deploy_name, e.reason)
        return None
    except Exception as e:
        logger.error("Failed to create K8s deployment: %s", e)
        return None


def delete_mtib_deployment(deploy_name: str) -> bool:
    """Delete a K8s deployment."""
    try:
        namespace = _get_mtib_namespace()
        apps_v1 = get_apps_v1_api()
        apps_v1.delete_namespaced_deployment(name=deploy_name, namespace=namespace)
        logger.info("Deleted K8s deployment: %s", deploy_name)
        return True
    except ApiException as e:
        if e.status == 404:
            logger.warning("K8s deployment %s not found (already deleted)", deploy_name)
            return True
        logger.error("Failed to delete K8s deployment %s: %s", deploy_name, e.reason)
        return False


def delete_mtib_deployments_for_claim(claim_id: str) -> list[str]:
    """Delete every mtib-server Deployment tagged with this claim id.

    Used by the DEV_HOLD claim release/expiry path. Fixture-bound and
    standalone-node deployments have an empty ``claim-id`` label and are
    NOT matched here — only deployments the claim itself spun up come down.

    Returns the list of deploy names actually deleted. Idempotent: a second
    call with the same claim_id is a no-op (returns ``[]``) because the
    list call comes back empty.
    """
    if not claim_id:
        return []
    try:
        namespace = _get_mtib_namespace()
        apps_v1 = get_apps_v1_api()
        selector = f"corekinect.com/claim-id={claim_id}"
        deps = apps_v1.list_namespaced_deployment(
            namespace=namespace, label_selector=selector,
        )
    except ApiException as e:
        logger.error("Failed to list mtib deployments for claim %s: %s", claim_id, e.reason)
        return []
    except Exception as e:
        logger.error("Failed to list mtib deployments for claim %s: %s", claim_id, e)
        return []

    deleted: list[str] = []
    for dep in (deps.items or []):
        name = dep.metadata.name
        if delete_mtib_deployment(name):
            deleted.append(name)
    return deleted


def get_mtib_deployment_status(deploy_name: str) -> Optional[dict]:
    """Get status of a K8s deployment."""
    try:
        namespace = _get_mtib_namespace()
        apps_v1 = get_apps_v1_api()
        dep = apps_v1.read_namespaced_deployment(name=deploy_name, namespace=namespace)

        status: dict = {
            "name": deploy_name,
            "replicas": dep.status.replicas or 0,
            "readyReplicas": dep.status.ready_replicas or 0,
            "availableReplicas": dep.status.available_replicas or 0,
        }

        # Get pods
        core_v1 = get_core_v1_api()
        selector = ",".join(f"{k}={v}" for k, v in (dep.spec.selector.match_labels or {}).items())
        pods = core_v1.list_namespaced_pod(namespace=namespace, label_selector=selector)
        status["pods"] = []
        for p in pods.items:
            pod_info = {
                "name": p.metadata.name,
                "nodeName": p.spec.node_name,
                "status": p.status.phase if p.status else "Unknown",
                "ready": all(cs.ready for cs in (p.status.container_statuses or [])),
                "restarts": sum(cs.restart_count or 0 for cs in (p.status.container_statuses or [])),
            }
            status["pods"].append(pod_info)

        return status
    except ApiException as e:
        if e.status == 404:
            return None
        logger.error("Failed to get deployment status %s: %s", deploy_name, e.reason)
        return None


def get_mtib_pod_image_sha(deploy_name: str) -> str | None:
    """Get the actual running image digest for an MTIB deployment.

    Queries the pod's container_statuses[0].image_id for the resolved SHA.
    Returns the digest string (e.g., 'sha256:abc123...') or None.
    """
    try:
        namespace = _get_mtib_namespace()
        apps_v1 = get_apps_v1_api()
        dep = apps_v1.read_namespaced_deployment(name=deploy_name, namespace=namespace)

        core_v1 = get_core_v1_api()
        selector = ",".join(
            f"{k}={v}" for k, v in (dep.spec.selector.match_labels or {}).items()
        )
        pods = core_v1.list_namespaced_pod(namespace=namespace, label_selector=selector)
        for pod in pods.items:
            for cs in (pod.status.container_statuses or []):
                if cs.image_id:
                    return cs.image_id
        return None
    except (ApiException, Exception) as e:
        logger.warning("Failed to get image SHA for %s: %s", deploy_name, e)
        return None


def wait_for_mtibs_healthy(
    slots: list[dict],
    port: int = 50053,
    timeout_s: int = 30,
) -> dict:
    """Check TCP health of MTIB servers on multiple nodes in parallel.

    Each slot dict must have 'nodeIp'. Returns:
        {"healthy": [...], "unhealthy": [...]}
    """
    def check_one(slot: dict) -> tuple[dict, bool]:
        ip = slot.get("nodeIp")
        if not ip:
            return slot, False
        try:
            sock = socket.create_connection((ip, port), timeout=timeout_s)
            sock.close()
            return slot, True
        except (OSError, socket.timeout):
            return slot, False

    healthy, unhealthy = [], []
    if not slots:
        return {"healthy": healthy, "unhealthy": unhealthy}
    with ThreadPoolExecutor(max_workers=min(len(slots), 8)) as pool:
        futures = {pool.submit(check_one, s): s for s in slots if s.get("nodeIp")}
        for future in as_completed(futures, timeout=timeout_s + 5):
            try:
                slot, ok = future.result()
                (healthy if ok else unhealthy).append(slot)
            except Exception:
                unhealthy.append(futures[future])

    # Slots without nodeIp are unhealthy
    for s in slots:
        if not s.get("nodeIp") and s not in unhealthy:
            unhealthy.append(s)

    return {"healthy": healthy, "unhealthy": unhealthy}


def list_mtib_deployments() -> list:
    """List all MTIB deployments managed by concord-api."""
    try:
        namespace = _get_mtib_namespace()
        apps_v1 = get_apps_v1_api()
        deps = apps_v1.list_namespaced_deployment(
            namespace=namespace,
            label_selector="corekinect.com/managed-by=concord",
        )
        results = []
        for dep in deps.items:
            results.append({
                "name": dep.metadata.name,
                "replicas": dep.status.replicas or 0,
                "readyReplicas": dep.status.ready_replicas or 0,
                "availableReplicas": dep.status.available_replicas or 0,
                "nodeHostname": (dep.spec.template.spec.node_selector or {}).get("kubernetes.io/hostname", ""),
                "labels": dep.metadata.labels or {},
            })
        return results
    except Exception as e:
        logger.error("Failed to list MTIB deployments: %s", e)
        return []
