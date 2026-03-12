"""Trigger endpoint — creates a K8s validation job for an existing run."""
import hashlib
import logging
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Any

from config.env import env_config
from database import Json
from flask import g, jsonify, request

from src.lib.audit import log_audit
from src.lib.decorators import require_permissions
from src.lib.errors import bad_request, internal_error, not_found
from src.lib.permissions import Permissions
from src.lib.types import ApiResponse
from src.services.database.prisma import get_db_client

from .types import RunTriggerRequest
from ..benches.benches import find_available_bench

# Reuse K8s job helpers from the legacy run endpoint
from src.api.v2.validation.tests.run import create_kubernetes_job, create_k8s_job_name

logger = logging.getLogger(__name__)


def _create_run_api_key(db, user_id: str, run_id: str) -> str:
    """Create a database-backed API key for a validation K8s job.

    Returns the raw key string (to be injected into the K8s Job env).
    The key expires after 24 hours.
    """
    raw_key = f"ck_run_{secrets.token_urlsafe(32)}"
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()

    db.apikey.create(
        data={
            "name": f"Validation run {run_id}",
            "keyHash": key_hash,
            "keyPrefix": raw_key[:12],
            "userId": user_id,
            "expiresAt": datetime.now(timezone.utc) + timedelta(hours=24),
        },
    )

    return raw_key


@require_permissions(Permissions.VALIDATION_RUN)
def trigger_run(run_id: str):
    """POST /v2/validation/runs/<run_id>/trigger — Create a K8s Job for this run."""
    data, error = RunTriggerRequest.from_json(request.get_json())
    if error:
        return bad_request(error)

    db = get_db_client()

    # Fetch session
    session = db.session.find_unique(
        where={"id": run_id},
        include={"product": True},
    )
    if not session:
        return not_found("Validation run not found")

    # Must be ACTIVE to trigger
    if session.status != "ACTIVE":
        return bad_request(f"Cannot trigger a run with status {session.status}")

    try:
        # Determine firmware path
        firmware_path = data.firmware_path or ""

        # Build test enable flags from session config or request config
        run_config = data.config or (session.config if isinstance(session.config, dict) else {}) or {}
        test_enable = run_config.get("testEnable", {
            "electrical": True,
            "app_post": True,
            "comm_post": True,
        })

        # Get product name and revision
        product_name = session.product.name if hasattr(session, "product") and session.product else "unknown"
        product_revision = run_config.get("revision", "b0")  # Default to b0

        # Required capabilities from config (optional)
        # Stage-specific defaults: fuota/gate/smoke need jlink for firmware flashing
        stage_capability_defaults = {
            "fuota": ["button", "jlink"],
            "gate": ["button", "jlink"],
            "smoke": ["button", "jlink"],
            "nightly": ["button", "jlink"],
            "integration": ["button"],
        }
        default_caps = stage_capability_defaults.get(data.stage, ["button"])
        required_capabilities = run_config.get("requiredCapabilities", default_caps)

        # Find an available test bench for this product
        bench = find_available_bench(
            product=product_name,
            revision=product_revision,
            capabilities=required_capabilities,
        )

        if not bench:
            return bad_request(
                f"No available test bench for product '{product_name}' "
                f"with capabilities: {required_capabilities}"
            )

        # Lock the bench for this run
        db.testbench.update(
            where={"id": bench["id"]},
            data={
                "status": "LOCKED",
                "lockedBy": f"run:{run_id}",
                "lockedAt": datetime.now(timezone.utc),
            },
        )

        log_audit("validation.bench.lock", "TestBench", bench["id"], {
            "lockedBy": f"run:{run_id}",
            "runId": run_id,
        })

        logger.info(f"Locked bench {bench['stationId']} for run {run_id}")

        # Create a real database-backed API key for the K8s job
        user_id = g.current_user["sub"]
        api_key = _create_run_api_key(db, user_id, run_id)

        # Use internal K8s service for reporter - avoids TLS/ingress issues
        # concord-http-api.staging.svc.cluster.local:9001 is the internal service endpoint
        api_url = os.environ.get("CONCORD_API_URL", "http://concord-http-api.staging.svc.cluster.local:9001")

        # Extract just the IP from mtibAddress (which may include port like "10.4.45.33:50053")
        mtib_addr_full = bench.get("mtibAddress") or ""
        mtib_host = mtib_addr_full.split(":")[0] if mtib_addr_full else ""

        # Derive product slug for catalog API lookup
        product_slug = None
        if hasattr(session, "product") and session.product:
            product_slug = session.product.slug

        # Create K8s Job with bench info
        job_name = create_kubernetes_job(
            product=product_name,
            job_id=run_id,
            firmware_path=firmware_path,
            test_type="validation",
            test_enable=test_enable if isinstance(test_enable, dict) else {},
            firmware_version=data.firmware_version,
            run_id=run_id,
            api_key=api_key,
            api_url=api_url,
            # Bench-related params
            mtib_address=mtib_host,
            bench_id=bench.get("id"),
            device_id=bench.get("dutDeviceId"),
            device_snr=bench.get("dutSnr"),
            fixture_profile_path=bench.get("profilePath"),
            # Stage 4: Pipeline-based firmware
            pipeline_id=data.pipeline_id,
            # Product context
            product_slug=product_slug,
            # Validation stage
            stage=data.stage,
        )

        if not job_name:
            return internal_error("Failed to create Kubernetes job")

        # Update session with trigger metadata (key hash only, never store raw key)
        trigger_meta = {
            "jobName": job_name,
            "firmwareVersion": data.firmware_version,
            "triggeredAt": datetime.now(timezone.utc).isoformat(),
        }

        existing_config = session.config if isinstance(session.config, dict) else {}
        existing_config["trigger"] = trigger_meta
        existing_config["apiUrl"] = api_url
        existing_config["concordRunId"] = run_id

        # Store bench info for unlock on finish and debugging
        existing_config["benchId"] = bench["id"]
        existing_config["benchStationId"] = bench["stationId"]
        existing_config["mtibAddress"] = bench.get("mtibAddress")

        db.session.update(
            where={"id": run_id},
            data={"config": Json(existing_config)},
        )

        log_audit("validation.run.trigger", "Session", run_id, {
            "jobName": job_name,
            "firmwareVersion": data.firmware_version,
            "firmwarePath": firmware_path,
        })

        return jsonify(ApiResponse.ok({
            "jobName": job_name,
            "runId": run_id,
        }).to_dict()), 200

    except Exception as e:
        logger.error(f"Failed to trigger validation run {run_id}: {e}")
        return internal_error("Failed to trigger validation run")
