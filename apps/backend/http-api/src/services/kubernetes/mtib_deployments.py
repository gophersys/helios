"""Service for managing MTIB server K8s deployments."""
import logging
import os
from typing import Optional

import yaml

logger = logging.getLogger(__name__)


def create_mtib_deployment(
    node_hostname: str,
    fixture_id: str,
    deployment_id: str,
    slot_index: int,
    config: dict,
) -> Optional[str]:
    """Create a K8s deployment for an MTIB server on a specific node.

    Returns the K8s deployment name on success, None on failure.
    """
    try:
        from src.services.kubernetes.client import get_apps_v1_api
        from kubernetes.client.exceptions import ApiException
    except ImportError:
        logger.error("Kubernetes client not available")
        return None

    template_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        "assets", "templates", "mtib_server_deployment.yaml"
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
    env_config = config.get("env", {})
    motion_enabled = env_config.get("MOTION_ENABLED", "false")
    metrics_enabled = env_config.get("METRICS_ENABLED", "false")
    log_level = env_config.get("LOG_LEVEL", "4")

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
        apps_v1 = get_apps_v1_api()
        apps_v1.create_namespaced_deployment(namespace="default", body=spec)
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
        from src.services.kubernetes.client import get_apps_v1_api
        from kubernetes.client.exceptions import ApiException
    except ImportError:
        return False

    try:
        apps_v1 = get_apps_v1_api()
        apps_v1.delete_namespaced_deployment(name=deploy_name, namespace="default")
        logger.info("Deleted K8s deployment: %s", deploy_name)
        return True
    except ApiException as e:
        if e.status == 404:
            logger.warning("K8s deployment %s not found (already deleted)", deploy_name)
            return True
        logger.error("Failed to delete K8s deployment %s: %s", deploy_name, e.reason)
        return False


def get_mtib_deployment_status(deploy_name: str) -> Optional[dict]:
    """Get status of a K8s deployment."""
    try:
        from src.services.kubernetes.client import get_apps_v1_api, get_core_v1_api
        from kubernetes.client.exceptions import ApiException
    except ImportError:
        return None

    try:
        apps_v1 = get_apps_v1_api()
        dep = apps_v1.read_namespaced_deployment(name=deploy_name, namespace="default")

        status = {
            "name": deploy_name,
            "replicas": dep.status.replicas or 0,
            "readyReplicas": dep.status.ready_replicas or 0,
            "availableReplicas": dep.status.available_replicas or 0,
        }

        # Get pods
        core_v1 = get_core_v1_api()
        selector = ",".join(f"{k}={v}" for k, v in (dep.spec.selector.match_labels or {}).items())
        pods = core_v1.list_namespaced_pod(namespace="default", label_selector=selector)
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


def list_mtib_deployments() -> list:
    """List all MTIB deployments managed by concord-api."""
    try:
        from src.services.kubernetes.client import get_apps_v1_api
    except ImportError:
        return []

    try:
        apps_v1 = get_apps_v1_api()
        deps = apps_v1.list_namespaced_deployment(
            namespace="default",
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
