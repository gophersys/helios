"""Service for managing MTIB server K8s deployments."""
import logging
import os
import socket
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

import requests
import yaml  # type: ignore[import-untyped]

from config.env import env_config
from kubernetes.client.exceptions import ApiException
from src.services.kubernetes.client import get_apps_v1_api, get_core_v1_api


class MtibImageUnavailable(Exception):
    """Raised when the requested mtib-server image cannot be resolved
    in the container registry. Surfaces a structured error code so the
    route layer can return ``MTIB_IMAGE_UNAVAILABLE`` to callers
    instead of letting the cluster fall into ``ImagePullBackOff``.
    """

    code = "MTIB_IMAGE_UNAVAILABLE"


# Per-request HEAD timeout — keeps the create call fast when the
# registry is slow. Three seconds covers warm DNS + one TLS RTT on a
# healthy in-cluster registry; longer than that and we'd rather skip
# the digest pin than block the API thread.
_REGISTRY_HEAD_TIMEOUT_S = 3


def _split_image_ref(image_ref: str) -> tuple[str, str]:
    """Split ``registry/repo:tag`` into ``(registry/repo, tag)``.

    Already-digested images (``...@sha256:...``) are returned with an
    empty tag — the caller treats that as "no resolution needed".
    """
    if "@sha256:" in image_ref:
        return image_ref, ""
    # Tags are split at the last colon, but only if the colon comes
    # after the last slash — registry ports (``host:5000/repo``) and
    # tagged refs (``repo:tag``) must not collide.
    last_slash = image_ref.rfind("/")
    last_colon = image_ref.rfind(":")
    if last_colon > last_slash:
        return image_ref[:last_colon], image_ref[last_colon + 1:]
    return image_ref, "latest"


def _head_image_manifest(image_ref: str) -> "requests.Response":
    """HEAD the OCI manifest endpoint for ``image_ref``.

    Returns the raw ``requests.Response``. The caller inspects
    ``status_code`` (404 = unavailable) and the ``Docker-Content-Digest``
    header. Connection errors are propagated as the underlying
    ``requests`` exceptions so a transient network issue doesn't get
    misclassified as MTIB_IMAGE_UNAVAILABLE.
    """
    repo, tag = _split_image_ref(image_ref)
    # The OCI Distribution spec maps to ``/v2/<repo>/manifests/<ref>``.
    # We assume the registry is reachable as ``https://<host>``; this
    # is true for the in-cluster ``containers.ad.corekinect.com`` host
    # and for any standard registry.
    host_sep = repo.find("/")
    if host_sep <= 0:
        # No registry host means we can't build a URL — return a fake
        # 200 with no digest so the caller silently falls back to the
        # bare tag. This is the docker-hub library shorthand case.
        resp = requests.Response()
        resp.status_code = 200
        return resp
    host, repo_path = repo[:host_sep], repo[host_sep + 1:]
    url = f"https://{host}/v2/{repo_path}/manifests/{tag}"
    headers = {
        "Accept": (
            "application/vnd.docker.distribution.manifest.v2+json,"
            "application/vnd.oci.image.manifest.v1+json,"
            "application/vnd.docker.distribution.manifest.list.v2+json"
        ),
    }
    return requests.head(url, headers=headers, timeout=_REGISTRY_HEAD_TIMEOUT_S)


def _resolve_image_digest(image_ref: str) -> str:
    """Resolve ``image_ref`` to ``registry/repo@sha256:...`` when possible.

    A 404 from the registry → :class:`MtibImageUnavailable`.
    Any other failure (timeout, missing header, DNS) → return the
    original ref so the cluster pulls by tag like before.
    """
    if "@sha256:" in image_ref:
        return image_ref  # already pinned
    try:
        resp = _head_image_manifest(image_ref)
    except requests.RequestException as e:
        logger.warning(
            "Registry HEAD for %s failed (%s) — proceeding with tag",
            image_ref, e,
        )
        return image_ref
    if resp.status_code == 404:
        raise MtibImageUnavailable(
            f"mtib-server image not found in registry: {image_ref}"
        )
    if resp.status_code >= 400:
        logger.warning(
            "Registry HEAD for %s returned %s — proceeding with tag",
            image_ref, resp.status_code,
        )
        return image_ref
    digest = (resp.headers.get("Docker-Content-Digest") or "").strip()
    if not digest.startswith("sha256:"):
        return image_ref
    repo, _tag = _split_image_ref(image_ref)
    return f"{repo}@{digest}"

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

    # Generate RFC 1123-compliant name. Claim-mode deployments need a
    # distinct name so they don't collide with the fixture-bound
    # deployment that owns the same node (and the same hostPort 50053).
    # Without the ``claim-<id>`` prefix the create call 409s and the
    # caller silently reuses the fixture deployment — which then
    # ignores the claim's MOTION_ENABLED / IMAGE config and never gets
    # tagged with the claim-id label, so teardown_claim_mtibs no-ops.
    if claim_id:
        claim_short = claim_id[:8]
        deploy_name = f"mtib-claim-{claim_short}-{node_hostname}-s{slot_index}"
    else:
        deploy_name = f"mtib-{node_hostname}-s{slot_index}"
    if len(deploy_name) > 63:
        deploy_name = deploy_name[:63].rstrip("-")

    image = config.get("image", "containers.ad.corekinect.com/concord-mtib-server:latest")

    # Resolve the tag to an immutable digest. A 404 here raises
    # MtibImageUnavailable BEFORE any cluster mutation so the operator
    # gets a clean error instead of an ImagePullBackOff that takes
    # minutes to surface. Network errors fall through with a warning.
    image = _resolve_image_digest(image)

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

        # Claim-mode pods must NOT bind hostPort 50053 — that port is
        # owned by the fixture-bound MTIB on the same node. Strip the
        # hostPort while keeping the containerPort, and create a
        # ClusterIP Service so runner pods can still reach the MTIB
        # via DNS (``<deploy_name>.<ns>.svc.cluster.local:50053``).
        if claim_id:
            try:
                containers = spec["spec"]["template"]["spec"]["containers"]
                for c in containers:
                    for p in (c.get("ports") or []):
                        if p.get("hostPort") == 50053:
                            p.pop("hostPort", None)
            except (KeyError, TypeError):
                pass

        namespace = _get_mtib_namespace()
        apps_v1 = get_apps_v1_api()
        apps_v1.create_namespaced_deployment(namespace=namespace, body=spec)
        logger.info("Created K8s deployment: %s", deploy_name)

        if claim_id:
            _ensure_claim_mtib_service(deploy_name, namespace, claim_id)

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


def _ensure_claim_mtib_service(deploy_name: str, namespace: str, claim_id: str) -> None:
    """Create the ClusterIP Service that fronts a claim-mode MTIB pod.

    Runner pods inside the cluster reach the MTIB via
    ``{deploy_name}.{namespace}.svc.cluster.local:50053``. We create
    the Service idempotently — a 409 means the previous create already
    landed it, so the reuse path is safe.
    """
    service_body = {
        "apiVersion": "v1",
        "kind": "Service",
        "metadata": {
            "name": deploy_name,
            "labels": {
                "app": deploy_name,
                "corekinect.com/managed-by": "concord",
                "corekinect.com/claim-id": claim_id,
            },
        },
        "spec": {
            "type": "ClusterIP",
            "selector": {"app": deploy_name},
            "ports": [{
                "name": "mtib-grpc",
                "port": 50053,
                "targetPort": 50053,
                "protocol": "TCP",
            }],
        },
    }
    try:
        core_v1 = get_core_v1_api()
        core_v1.create_namespaced_service(namespace=namespace, body=service_body)
        logger.info("Created K8s service for claim MTIB: %s", deploy_name)
    except ApiException as e:
        if e.status == 409:
            logger.debug("K8s service %s already exists", deploy_name)
            return
        logger.warning("Failed to create K8s service %s: %s", deploy_name, e.reason)
    except Exception as e:
        logger.warning("Failed to create K8s service %s: %s", deploy_name, e)


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

    # Companion ClusterIP Services live under the same name and
    # ``claim-id`` label. Best-effort cleanup — a missing Service is
    # not a teardown failure.
    try:
        core_v1 = get_core_v1_api()
        services = core_v1.list_namespaced_service(
            namespace=_get_mtib_namespace(),
            label_selector=f"corekinect.com/claim-id={claim_id}",
        )
        for svc in (services.items or []):
            try:
                core_v1.delete_namespaced_service(
                    name=svc.metadata.name, namespace=_get_mtib_namespace(),
                )
            except ApiException as e:
                if e.status != 404:
                    logger.warning(
                        "Failed to delete claim MTIB service %s: %s",
                        svc.metadata.name, e.reason,
                    )
    except Exception as e:
        logger.debug("Service-cleanup pass for claim %s skipped: %s", claim_id, e)

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
