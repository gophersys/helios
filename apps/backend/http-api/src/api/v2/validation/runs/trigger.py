"""Trigger endpoint — creates a K8s validation job for an existing run."""
import logging
import os
import secrets
from datetime import datetime, timezone

from config.env import env_config
from database import Json
from flask import jsonify, request

from src.lib.audit import log_audit
from src.lib.decorators import require_permissions
from src.lib.errors import bad_request, internal_error, not_found
from src.lib.permissions import Permissions
from src.lib.types import ApiResponse
from src.services.database.prisma import get_db_client

from .types import RunTriggerRequest

# Reuse K8s job helpers from the legacy run endpoint
from src.api.v2.validation.tests.run import create_kubernetes_job, create_k8s_job_name

logger = logging.getLogger(__name__)


def generate_api_key_for_run(run_id: str) -> str:
    """Generate a short-lived API key for K8s job authentication."""
    return f"run-{run_id}-{secrets.token_urlsafe(24)}"


@require_permissions(Permissions.ADMIN_VALIDATION_MANAGE)
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

        # Get product name
        product_name = session.product.name if hasattr(session, "product") and session.product else "unknown"

        # Generate API key for the K8s job
        api_key = generate_api_key_for_run(run_id)

        api_url = os.environ.get("CONCORD_API_URL", f"http://concord-api.default.svc.cluster.local:{env_config.SERVER_PORT}")

        # Create K8s Job
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
        )

        if not job_name:
            return internal_error("Failed to create Kubernetes job")

        # Update session with trigger metadata
        trigger_meta = {
            "jobName": job_name,
            "firmwareVersion": data.firmware_version,
            "triggeredAt": datetime.now(timezone.utc).isoformat(),
        }

        existing_config = session.config if isinstance(session.config, dict) else {}
        existing_config["trigger"] = trigger_meta
        existing_config["apiKey"] = api_key
        existing_config["apiUrl"] = api_url
        existing_config["concordRunId"] = run_id

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
