"""Bitbucket webhook + manual CI trigger endpoints."""

import hashlib
import hmac
import logging
import os

from database import Json
from flask import g, jsonify, request

from src.lib.audit import log_audit
from src.lib.decorators import require_permissions
from src.lib.errors import bad_request, internal_error
from src.lib.permissions import Permissions
from src.lib.types import ApiResponse, ErrorDetail
from src.services.database.prisma import get_db_client

from .builds import _serialize_build_job
from .types import (
    BitbucketWebhookPayload,
    CI_TRIGGER_BRANCHES,
    CiTriggerRequest,
    REPO_PRODUCT_MAP,
)

logger = logging.getLogger(__name__)

_socketio = None


def set_ci_socketio(sio):
    """Store the SocketIO instance for CI event emission."""
    global _socketio
    _socketio = sio


def _emit_ci_event(event: str, data: dict):
    """Emit a CI event via WebSocket if SocketIO is available."""
    if _socketio:
        _socketio.emit(event, data, namespace="/kubernetes")


def _validate_webhook_signature(payload_bytes: bytes, signature: str) -> bool:
    """Validate Bitbucket webhook HMAC-SHA256 signature.

    SECURITY: Fail-closed — rejects webhooks if no secret is configured.
    This prevents accepting unsigned webhooks in misconfigured environments.
    """
    secret = os.environ.get("BITBUCKET_WEBHOOK_SECRET", "")
    if not secret:
        # SECURITY: Fail-closed — do not accept webhooks without a configured secret
        logger.error("BITBUCKET_WEBHOOK_SECRET not set — rejecting webhook (fail-closed)")
        return False

    if not signature:
        return False

    # Bitbucket sends: sha256=<hex>
    prefix = "sha256="
    if signature.startswith(prefix):
        signature = signature[len(prefix):]

    expected = hmac.new(
        secret.encode(), payload_bytes, hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(expected, signature)


def _create_build_job(db, payload: BitbucketWebhookPayload, product_config: dict):
    """Create a BuildJob record from a webhook payload."""
    build = db.buildjob.create(
        data={
            "product": product_config["product_name"].lower().replace(" ", "_"),
            "board": "alpha_b0",
            "target": "app",
            "variant": product_config.get("default_variant", "debug"),
            "mtibRev": "1.2",
            "branch": payload.branch,
            "commitSha": payload.commit_sha,
            "status": "QUEUED",
            "webhookData": Json(payload.raw) if payload.raw else None,
        },
        include={"artifacts": True},
    )
    return build


def webhook_bitbucket():
    """POST /v2/ci/webhooks/bitbucket — Receive Bitbucket Server webhook.

    No auth decorator — validated via HMAC signature instead.
    """
    # Validate HMAC signature
    payload_bytes = request.get_data()
    signature = request.headers.get("X-Hub-Signature", "")

    if not _validate_webhook_signature(payload_bytes, signature):
        return jsonify(ApiResponse.error(ErrorDetail("Invalid webhook signature")).to_dict()), 401

    # Parse payload
    payload, error = BitbucketWebhookPayload.from_json(request.get_json(silent=True))
    if error:
        return bad_request(error)

    # Check if repo is mapped to a product
    product_config = REPO_PRODUCT_MAP.get(payload.repo_slug)
    if not product_config:
        logger.info("Ignoring webhook for unmapped repo: %s", payload.repo_slug)
        return jsonify(ApiResponse.ok({"ignored": True, "reason": "unmapped repo"}).to_dict()), 200

    # Check if branch triggers CI
    if payload.branch not in CI_TRIGGER_BRANCHES:
        logger.info("Ignoring webhook for non-CI branch: %s", payload.branch)
        return jsonify(ApiResponse.ok({"ignored": True, "reason": "non-CI branch"}).to_dict()), 200

    try:
        db = get_db_client()

        # Create build job(s) — one per target in the product config
        builds = []
        board = product_config.get("board", "alpha_b0")
        for target in product_config.get("targets", ["app"]):
            build = db.buildjob.create(
                data={
                    "product": product_config["product_name"].lower().replace(" ", "_"),
                    "board": board,
                    "target": target,
                    "variant": product_config.get("default_variant", "debug"),
                    "mtibRev": "1.2",
                    "branch": payload.branch,
                    "commitSha": payload.commit_sha,
                    "status": "QUEUED",
                    "webhookData": Json(payload.raw) if payload.raw else None,
                },
                include={"artifacts": True},
            )
            builds.append(build)

        log_audit("ci.webhook.received", "BuildJob", builds[0].id if builds else "", {
            "eventKey": payload.event_key,
            "repoSlug": payload.repo_slug,
            "branch": payload.branch,
            "commitSha": payload.commit_sha,
            "buildCount": len(builds),
        })

        _emit_ci_event("ci_pipeline_start", {
            "repoSlug": payload.repo_slug,
            "branch": payload.branch,
            "commitSha": payload.commit_sha,
            "builds": [{"id": b.id, "target": b.target, "status": b.status} for b in builds],
        })

        return jsonify(ApiResponse.created({
            "builds": [_serialize_build_job(b) for b in builds],
        }).to_dict()), 201

    except Exception as e:
        logger.error("Failed to process Bitbucket webhook: %s", e)
        return internal_error("Failed to process webhook")


@require_permissions(Permissions.ADMIN_CI_MANAGE)
def trigger_pipeline():
    """POST /v2/ci/trigger — Manual CI pipeline trigger."""
    data, error = CiTriggerRequest.from_json(request.get_json())
    if error:
        return bad_request(error)

    db = get_db_client()

    # Look up product
    product = db.product.find_unique(where={"id": data.product_id})
    if not product:
        return bad_request("Product not found")

    # Map repo slug to product config
    product_config = REPO_PRODUCT_MAP.get(data.repo_slug)
    if not product_config:
        return bad_request(f"Unknown repository: {data.repo_slug}")

    try:
        # Create build job with board from product config
        # Use repo_slug as product field - build worker maps by repo slug
        board = product_config.get("board", "alpha_b0")
        build = db.buildjob.create(
            data={
                "product": data.repo_slug,
                "board": board,
                "target": "app",
                "variant": data.variant,
                "mtibRev": data.mtib_rev,
                "branch": data.branch,
                "commitSha": data.commit_sha,
                "status": "QUEUED",
            },
            include={"artifacts": True},
        )

        log_audit("ci.trigger.manual", "BuildJob", build.id, {
            "productId": data.product_id,
            "repoSlug": data.repo_slug,
            "branch": data.branch,
            "variant": data.variant,
        })

        _emit_ci_event("ci_build_start", {
            "buildId": build.id,
            "product": build.product,
            "branch": build.branch,
            "variant": build.variant,
        })

        return jsonify(ApiResponse.created(
            _serialize_build_job(build)
        ).to_dict()), 201

    except Exception as e:
        logger.error("Failed to trigger CI pipeline: %s", e)
        return internal_error("Failed to trigger CI pipeline")


@require_permissions(Permissions.ADMIN_CI_VIEW)
def list_ci_repos():
    """GET /v2/ci/settings/repos — List configured CI repositories.

    Used by build workers to get repo configs (ssh_url, build_script).
    """
    base_url = os.environ.get("CONCORD_API_URL", "https://staging.concord.local")
    # SECURITY: webhook secret is intentionally NOT included in response
    # Secrets should never be returned in API responses

    repos = []
    for slug, config in REPO_PRODUCT_MAP.items():
        repos.append({
            "id": slug,
            "name": slug,
            "productName": config["product_name"],
            "firmwareType": config["firmware_type"],
            "board": config.get("board", ""),
            "targets": config.get("targets", []),
            "defaultVariant": config.get("default_variant", "debug"),
            "ncsVersion": config.get("ncs_version", ""),
            "webhookUrl": f"{base_url}/v2/ci/webhooks/bitbucket",
            # SECURITY: webhookSecret removed — secrets must not be exposed in API responses
            "connected": True,  # Assume connected if we have the mapping
            "branches": list(CI_TRIGGER_BRANCHES),
            "variants": ["debug", "release"] if "mfg" not in slug else ["release"],
            "mtibRev": "1.2",
            "lastEventAt": None,  # Would come from DB
            # Worker-needed fields
            "sshUrl": config.get("ssh_url", ""),
            "buildScript": config.get("build_script", "scripts/build.sh"),
        })

    return jsonify(ApiResponse.ok(repos).to_dict()), 200
