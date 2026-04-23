"""Manufacturing runner lifecycle — deploy, teardown, heartbeat.

Manages the persistent runner container/deployment that executes
manufacturing tests for a session. The runner connects to MTIB hardware,
subscribes to WebSocket events for panel assignments, and reports results
back via the standard reporter callbacks.

- Development: Docker container via DockerExecutor
- Staging/Production: K8s Deployment via apps/v1 API
"""

import hashlib
import logging
import os
import re
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional
from urllib.parse import urlparse, urlunparse

import yaml  # type: ignore[import-untyped]
from database import Json
from flask import g, jsonify, request

from config.env import env_config
from src.lib.audit import log_audit
from src.lib.decorators import require_auth
from src.lib.types import ApiResponse
from src.services.database.prisma import get_db_client

logger = logging.getLogger(__name__)

# SocketIO instance — set by register_run_routes() via set_runner_socketio()
_socketio = None


def set_runner_socketio(sio):
    """Assign the SocketIO instance for real-time events."""
    global _socketio
    _socketio = sio


def _emit(event: str, data: dict, room: str | None = None):
    """Emit an event on the /runs namespace."""
    if not _socketio:
        return
    kwargs = {"namespace": "/runs"}
    if room:
        kwargs["room"] = room
    _socketio.emit(event, data, **kwargs)


# ---------------------------------------------------------------------------
# Slot resolution
# ---------------------------------------------------------------------------


def _resolve_slot_info(fixture) -> list[dict]:
    """Extract DUT info and node addresses from active fixture slots.

    Node IPs are resolved from the K8s API at call time — never uses stored IPs.
    Returns a list of slot dicts with keys:
        slotIndex, slotId, dutSnr, dutDeviceId, nodeIp, nodeHostname
    """
    slots = fixture.slots if hasattr(fixture, "slots") and fixture.slots else []

    # Collect hostnames for K8s IP resolution
    hostnames = []
    for slot in slots:
        if slot.active:
            node = slot.node if hasattr(slot, "node") and slot.node else None
            if node:
                hostnames.append(node.hostname)

    # Resolve IPs from K8s (live, not cached)
    ip_map: dict[str, str] = {}
    if hostnames:
        try:
            from src.services.kubernetes.client import resolve_node_ips
            ip_map = resolve_node_ips(hostnames)
        except Exception:
            logger.warning("K8s IP resolution failed — falling back to stored IPs")
            for slot in slots:
                node = slot.node if hasattr(slot, "node") and slot.node else None
                if node and node.ipAddress:
                    ip_map[node.hostname] = node.ipAddress

    result = []
    for slot in slots:
        if not slot.active:
            continue
        node = slot.node if hasattr(slot, "node") and slot.node else None
        hostname = getattr(node, "hostname", None) if node else None
        result.append({
            "slotIndex": slot.slotIndex,
            "slotId": slot.id,
            "dutSnr": slot.dutSnr if hasattr(slot, "dutSnr") else None,
            "dutDeviceId": slot.dutDeviceId if hasattr(slot, "dutDeviceId") else None,
            "nodeIp": ip_map.get(hostname) if hostname else None,
            "nodeHostname": hostname,
        })
    return result


# ---------------------------------------------------------------------------
# API key for runner auth
# ---------------------------------------------------------------------------


def _create_runner_api_key(db, session_id: str) -> str:
    """Create a database-backed API key for the manufacturing runner.

    Returns the raw key string to inject into the container env.
    Key expires after 24 hours.
    """
    raw_key = f"ck_mfg_{secrets.token_urlsafe(32)}"
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()

    system_user = db.user.find_first(where={"email": "system@concord.local"})
    if not system_user:
        system_user = db.user.find_first()
    user_id = system_user.id if system_user else None

    db.apikey.create(
        data={
            "name": f"Manufacturing session {session_id}",
            "keyHash": key_hash,
            "keyPrefix": raw_key[:14],
            "userId": user_id,
            "expiresAt": datetime.now(timezone.utc) + timedelta(hours=24),
        },
    )

    return raw_key


# ---------------------------------------------------------------------------
# Storage URL resolution (K8s FQDN)
# ---------------------------------------------------------------------------


def _resolve_storage_url() -> str:
    """Qualify short MinIO service names with namespace FQDN for K8s pods."""
    storage_url = env_config.STORAGE_URL
    namespace = env_config.ENVIRONMENT
    if "://" in storage_url and ".svc" not in storage_url:
        parsed = urlparse(storage_url)
        host_parts = parsed.hostname.split(".") if parsed.hostname else []
        if len(host_parts) == 1:
            fqdn = f"{parsed.hostname}.{namespace}.svc.cluster.local"
            new_netloc = f"{fqdn}:{parsed.port}" if parsed.port else fqdn
            storage_url = urlunparse(parsed._replace(netloc=new_netloc))
    return storage_url


# ---------------------------------------------------------------------------
# Deploy
# ---------------------------------------------------------------------------


def deploy_manufacturing_runner(db, session, fixture, product) -> Optional[str]:
    """Spawn a persistent manufacturing runner for the given session.

    - Development: Docker container via DockerExecutor
    - Staging/Production: K8s Deployment via apps/v1 API

    Returns the deployment/container name on success, None on failure.
    """
    session_id = session.id

    # 1. Resolve fixture slots → MTIB hosts, SNRs, device IDs
    slot_infos = _resolve_slot_info(fixture)
    if not slot_infos:
        logger.warning("No active slots with nodes for fixture %s", fixture.id)

    mtib_port = str(env_config.MTIB_PORT)
    mtib_hosts = ",".join(
        f"{s['nodeIp']}:{mtib_port}"
        for s in slot_infos
        if s["nodeIp"]
    )
    slot_snrs = ",".join(s["dutSnr"] or f"slot-{s['slotIndex']}" for s in slot_infos)
    # Only build SLOT_DEVICE_IDS if at least one slot has a real device ID
    device_id_values = [s.get("dutDeviceId") or "" for s in slot_infos]
    slot_device_ids = ",".join(device_id_values) if any(device_id_values) else ""

    # 2. Resolve test package
    from src.api.v2.manufacturing.sessions import _resolve_test_package
    tp, _ = _resolve_test_package(db, product.id)
    test_package_version = tp.version if tp else "latest"

    # 3. Create temporary API key
    api_key = _create_runner_api_key(db, session_id)

    # 4. Resolve API URL for container callbacks
    api_url = os.environ.get(
        "CONCORD_API_URL",
        env_config.CONCORD_API_URL,
    )

    # 5. Build common env vars
    product_slug = product.slug if hasattr(product, "slug") else product.name.lower().replace(" ", "_")
    product_k8s = re.sub(r"[^a-z0-9-]", "-", product_slug.lower()).strip("-")

    env = {
        "RUNNER_MODE": "persistent",
        "ENVIRONMENT": env_config.ENVIRONMENT,
        "STAGE": "manufacturing",
        "TEST_PACKAGE_TYPE": "MANUFACTURING",
        "LOG_LEVEL": "4",
        "CONCORD_SESSION_ID": session_id,
        "CONCORD_API_URL": api_url,
        "CONCORD_API_KEY": api_key,
        "CONCORD_API_HOST": env_config.CONCORD_API_HOST,
        "PRODUCT": product_k8s,
        "PRODUCT_SLUG": product_slug,
        "TEST_PACKAGE_VERSION": test_package_version,
        "STORAGE_URL": _resolve_storage_url(),
        "STORAGE_ACCESS_KEY": env_config.STORAGE_ACCESS_KEY,
        "STORAGE_SECRET_ACCESS_KEY": env_config.STORAGE_SECRET_ACCESS_KEY,
        "STORAGE_BUCKET_NAME": env_config.STORAGE_BUCKET_NAME,
        "MTIB_HOSTS": mtib_hosts,
        "MTIB_PORT": mtib_port,
        "SLOT_SNRS": slot_snrs,
        "SLOT_DEVICE_IDS": slot_device_ids,
        "FIXTURE_ID": fixture.id,
        "FIXTURE_CONFIG_PATH": "",
        "ASSET_SET_ID": session.assetSetId or "",
        "ARTIFACTS_DIR": "/var/log/validation",
        # CoreOps credentials — needed for device personalization during POST tests.
        # Passed from the backend's environment so the runner can call CoreOps directly.
        "COREOPS_SERVER_URL": os.environ.get("COREOPS_SERVER_URL", ""),
        "COREOPS_API_KEY": os.environ.get("COREOPS_API_KEY", ""),
        "COREOPS_AUTH_SERVER_URL": os.environ.get("COREOPS_AUTH_SERVER_URL", ""),
        "COREOPS_AUTH_USER": os.environ.get("COREOPS_AUTH_USER", ""),
        "COREOPS_AUTH_PASS": os.environ.get("COREOPS_AUTH_PASS", ""),
        "COREOPS_VERIFY_SSL": os.environ.get("COREOPS_VERIFY_SSL", "false"),
    }

    # ASSET_SET_ID is already set above — the test framework downloads
    # firmware directly from the asset set API. No BUILD_RUN_ID needed;
    # manufacturing is independent of the build system.

    # 6. Development overrides — host network, local URLs
    is_dev = env_config.ENVIRONMENT == "development"
    if is_dev:
        env["CONCORD_API_URL"] = "http://localhost:9001"
        env["CONCORD_API_HOST"] = "localhost:9001"
        env["STORAGE_URL"] = "http://localhost:8675"
        env["TLS_VERIFY"] = "false"
        # MOCK_MODE only if explicitly set in the host environment
        if os.environ.get("MOCK_MODE"):
            env["MOCK_MODE"] = os.environ["MOCK_MODE"]

    # 7. Dispatch to executor
    deployment_name = None

    try:
        if is_dev:
            deployment_name = _deploy_docker(session_id, product_k8s, env)
        else:
            deployment_name = _deploy_k8s(session_id, product_k8s, env)
    except Exception:
        logger.exception("Failed to deploy manufacturing runner for session %s", session_id)

    # 7. Update session with runner info + store test package version in config
    runner_status = "DEPLOYING" if deployment_name else "ERROR"
    existing_config = session.config if isinstance(session.config, dict) else {}
    existing_config["testPackageVersion"] = test_package_version
    if tp:
        existing_config["testPackageId"] = tp.id

    db.manufacturingsession.update(
        where={"id": session_id},
        data={
            "runnerStatus": runner_status,
            "runnerDeploymentName": deployment_name,
            "config": Json(existing_config),
        },
    )

    log_audit("manufacturing_runner.deploy", "ManufacturingSession", session_id, {
        "deploymentName": deployment_name,
        "status": runner_status,
        "environment": env_config.ENVIRONMENT,
        "mtibHosts": mtib_hosts,
        "testPackageVersion": test_package_version,
    })

    return deployment_name


def _deploy_docker(session_id: str, product_k8s: str, env: dict) -> Optional[str]:
    """Spawn a persistent runner via DockerExecutor (development)."""
    from src.services.executors.factory import get_executor

    executor = get_executor("manufacturing")
    mfg_timeout = getattr(env_config, "MANUFACTURING_TIMEOUT_MINUTES", 120) * 60

    result = executor.submit(
        image=f"concord/test-runner:{env_config.ENVIRONMENT}",
        job_id=session_id,
        env=env,
        command=["/app/entrypoint.sh"],
        labels={"app": f"manufacturing-{product_k8s}"},
        timeout_seconds=mfg_timeout,
    )

    if not result.success:
        logger.error("Docker runner failed: %s", result.error)
        return None

    logger.info("Spawned Docker manufacturing runner: %s", result.job_name)
    return result.job_name


def _deploy_k8s(session_id: str, product_k8s: str, env: dict) -> Optional[str]:
    """Create a K8s Deployment for the persistent runner (staging/prod)."""
    try:
        from kubernetes.client.exceptions import ApiException
        from src.services.kubernetes.client import get_apps_v1_api
    except ImportError:
        logger.error("Kubernetes client not available")
        return None

    template_path = os.path.join(
        env_config.ASSETS_FOLDER, "templates", "manufacturing_deployment.yaml"
    )

    try:
        with open(template_path, "r") as f:
            template = f.read()
    except FileNotFoundError:
        logger.error("Manufacturing deployment template not found at %s", template_path)
        return None

    # Generate RFC 1123-compliant deployment name
    short_id = re.sub(r"[^a-z0-9]", "", session_id.lower())[:12]
    deploy_name = f"mfg-{product_k8s}-{short_id}"
    if len(deploy_name) > 63:
        deploy_name = deploy_name[:63].rstrip("-")

    image_tag = env_config.ENVIRONMENT

    # Substitute template placeholders
    manifest = template
    manifest = manifest.replace("{{DEPLOYMENT_NAME}}", deploy_name)
    manifest = manifest.replace("{{SESSION_ID}}", session_id)
    manifest = manifest.replace("{{PRODUCT}}", product_k8s)
    manifest = manifest.replace("{{PRODUCT_SLUG}}", env.get("PRODUCT_SLUG", ""))
    manifest = manifest.replace("{{IMAGE_TAG}}", image_tag)
    manifest = manifest.replace("{{ENVIRONMENT}}", env.get("ENVIRONMENT", ""))
    manifest = manifest.replace("{{CONCORD_API_URL}}", env.get("CONCORD_API_URL", ""))
    manifest = manifest.replace("{{CONCORD_API_KEY}}", env.get("CONCORD_API_KEY", ""))
    manifest = manifest.replace("{{CONCORD_API_HOST}}", env.get("CONCORD_API_HOST", ""))
    manifest = manifest.replace("{{TEST_PACKAGE_VERSION}}", env.get("TEST_PACKAGE_VERSION", "latest"))
    manifest = manifest.replace("{{STORAGE_URL}}", env.get("STORAGE_URL", ""))
    manifest = manifest.replace("{{STORAGE_ACCESS_KEY}}", env.get("STORAGE_ACCESS_KEY", ""))
    manifest = manifest.replace("{{STORAGE_SECRET_ACCESS_KEY}}", env.get("STORAGE_SECRET_ACCESS_KEY", ""))
    manifest = manifest.replace("{{STORAGE_BUCKET_NAME}}", env.get("STORAGE_BUCKET_NAME", ""))
    manifest = manifest.replace("{{MTIB_HOSTS}}", env.get("MTIB_HOSTS", ""))
    manifest = manifest.replace("{{MTIB_PORT}}", env.get("MTIB_PORT", "50053"))
    manifest = manifest.replace("{{SLOT_SNRS}}", env.get("SLOT_SNRS", ""))
    manifest = manifest.replace("{{SLOT_DEVICE_IDS}}", env.get("SLOT_DEVICE_IDS", ""))
    manifest = manifest.replace("{{FIXTURE_ID}}", env.get("FIXTURE_ID", ""))
    manifest = manifest.replace("{{FIXTURE_CONFIG_PATH}}", env.get("FIXTURE_CONFIG_PATH", ""))
    manifest = manifest.replace("{{ASSET_SET_ID}}", env.get("ASSET_SET_ID", ""))

    try:
        spec = yaml.safe_load(manifest)
        namespace = env_config.VALIDATION_NAMESPACE
        apps_v1 = get_apps_v1_api()
        apps_v1.create_namespaced_deployment(namespace=namespace, body=spec)
        logger.info("Created K8s manufacturing deployment: %s in %s", deploy_name, namespace)
        return deploy_name
    except ApiException as e:
        if e.status == 409:
            logger.warning("K8s deployment %s already exists", deploy_name)
            return deploy_name
        logger.error("Failed to create K8s deployment %s: %s", deploy_name, e.reason)
        return None
    except Exception as e:
        logger.error("Failed to create K8s manufacturing deployment: %s", e)
        return None


# ---------------------------------------------------------------------------
# Teardown
# ---------------------------------------------------------------------------


def teardown_manufacturing_runner(db, session) -> bool:
    """Stop and delete the runner container/deployment for a session.

    Returns True on success (or if there was nothing to teardown).
    """
    deployment_name = session.runnerDeploymentName if hasattr(session, "runnerDeploymentName") else None
    if not deployment_name:
        return True

    session_id = session.id
    is_dev = env_config.ENVIRONMENT == "development"
    success = False

    try:
        if is_dev:
            success = _teardown_docker(deployment_name)
        else:
            success = _teardown_k8s(deployment_name)
    except Exception:
        logger.exception("Failed to teardown manufacturing runner %s", deployment_name)

    # Clear runner fields regardless — the container may be gone already
    db.manufacturingsession.update(
        where={"id": session_id},
        data={
            "runnerStatus": None,
            "runnerDeploymentName": None,
        },
    )

    log_audit("manufacturing_runner.teardown", "ManufacturingSession", session_id, {
        "deploymentName": deployment_name,
        "success": success,
    })

    return success


def _teardown_docker(container_name: str) -> bool:
    """Kill a Docker manufacturing runner container."""
    from src.services.executors.factory import get_executor
    executor = get_executor("manufacturing")
    return executor.cancel(container_name)


def _teardown_k8s(deploy_name: str) -> bool:
    """Delete a K8s manufacturing runner Deployment."""
    try:
        from kubernetes.client.exceptions import ApiException
        from src.services.kubernetes.client import get_apps_v1_api
    except ImportError:
        return False

    try:
        namespace = env_config.VALIDATION_NAMESPACE
        apps_v1 = get_apps_v1_api()
        apps_v1.delete_namespaced_deployment(name=deploy_name, namespace=namespace)
        logger.info("Deleted K8s manufacturing deployment: %s", deploy_name)
        return True
    except ApiException as e:
        if e.status == 404:
            logger.warning("K8s deployment %s not found (already deleted?)", deploy_name)
            return True
        logger.error("Failed to delete K8s deployment %s: %s", deploy_name, e.reason)
        return False
    except Exception as e:
        logger.error("Failed to delete K8s manufacturing deployment: %s", e)
        return False


# ---------------------------------------------------------------------------
# Heartbeat endpoint
# ---------------------------------------------------------------------------


@require_auth
def runner_heartbeat(session_id: str):
    """POST /v2/manufacturing/sessions/<id>/runner-heartbeat

    Called by the persistent manufacturing runner to report its status.
    Updates the session's runner fields and emits a WebSocket event.
    """
    db = get_db_client()
    body = request.get_json()
    if not body:
        return jsonify(ApiResponse.error("Request body required").to_dict()), 400

    status = body.get("status", "READY")
    if status not in ("DEPLOYING", "READY", "RUNNING", "ERROR", "WAITING"):
        return jsonify(ApiResponse.error("Invalid status").to_dict()), 400

    now = datetime.now(timezone.utc)

    try:
        db.manufacturingsession.update(
            where={"id": session_id},
            data={
                "runnerStatus": status,
                "runnerLastHeartbeat": now,
            },
        )
    except Exception:
        logger.exception("Failed to update runner heartbeat for session %s", session_id)
        return jsonify(ApiResponse.error("Session not found").to_dict()), 404

    _emit(
        "manufacturing_runner_status",
        {
            "sessionId": session_id,
            "runnerStatus": status,
            "timestamp": now.isoformat(),
        },
        f"mfg-session:{session_id}",
    )

    return jsonify(ApiResponse.ok({"status": status}).to_dict()), 200
