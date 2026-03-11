"""Bitbucket webhook + manual CI trigger endpoints."""

import hashlib
import hmac
import logging
import os

from database import Json
from flask import g, jsonify, request

from src.lib.audit import log_audit
from src.lib.decorators import require_permissions
from src.lib.errors import bad_request, internal_error, unauthorized
from src.lib.permissions import Permissions
from src.lib.types import ApiResponse
from src.services.database.prisma import get_db_client

from .builds import _serialize_build_job
from .types import (
    BitbucketWebhookPayload,
    CI_TRIGGER_BRANCHES,
    CiTriggerRequest,
    REPO_PRODUCT_MAP,
)


def _resolve_product_by_repo(db, repo_slug: str):
    """Resolve a Product record by repo slug (main or mfg).

    Returns the Product DB record or None.
    """
    return db.product.find_first(
        where={"OR": [{"repoSlug": repo_slug}, {"mfgRepoSlug": repo_slug}]}
    )


def _product_to_build_config(product, repo_slug: str) -> dict:
    """Convert a Product record into the build config dict used by webhook/trigger.

    This replaces the static REPO_PRODUCT_MAP entries with live DB data.
    """
    is_mfg = product.mfgRepoSlug == repo_slug
    metadata = product.metadata if isinstance(product.metadata, dict) else {}

    # Determine targets from metadata or default to dual-chip
    targets = metadata.get("targets", ["app", "comms"])

    return {
        "product_name": product.name,
        "firmware_type": repo_slug,
        "board": product.buildBoard or "alpha_b0",
        "targets": targets,
        "default_variant": "release" if is_mfg else "debug",
        "ncs_version": metadata.get("ncsVersion", ""),
        "ssh_url": product.mfgRepoSshUrl if is_mfg else (product.repoSshUrl or ""),
        "build_script": metadata.get("buildScript", "scripts/build.sh"),
        "product_id": product.id,
    }

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
            "productId": product_config.get("product_id"),
            "board": product_config.get("board", "alpha_b0"),
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
        return unauthorized("Invalid webhook signature")

    # Parse payload
    payload, error = BitbucketWebhookPayload.from_json(request.get_json(silent=True))
    if error:
        return bad_request(error)

    # Check if branch triggers CI
    if payload.branch not in CI_TRIGGER_BRANCHES:
        logger.info("Ignoring webhook for non-CI branch: %s", payload.branch)
        return jsonify(ApiResponse.ok({"ignored": True, "reason": "non-CI branch"}).to_dict()), 200

    try:
        db = get_db_client()

        # Resolve product from DB by repo slug (preferred), fall back to static map
        product_record = _resolve_product_by_repo(db, payload.repo_slug)
        if product_record:
            product_config = _product_to_build_config(product_record, payload.repo_slug)
            logger.info("Resolved product '%s' (id=%s) from DB for repo %s",
                        product_record.name, product_record.id, payload.repo_slug)
        else:
            # Legacy fallback to static map
            product_config = REPO_PRODUCT_MAP.get(payload.repo_slug)
            if not product_config:
                logger.info("Ignoring webhook for unmapped repo: %s", payload.repo_slug)
                return jsonify(ApiResponse.ok({"ignored": True, "reason": "unmapped repo"}).to_dict()), 200
            logger.info("Using legacy REPO_PRODUCT_MAP for repo %s", payload.repo_slug)

        # Create build job(s) — one per target in the product config
        builds = []
        board = product_config.get("board", "alpha_b0")
        product_id = product_config.get("product_id")
        for target in product_config.get("targets", ["app"]):
            build = db.buildjob.create(
                data={
                    "product": product_config["product_name"].lower().replace(" ", "_"),
                    "productId": product_id,
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


@require_permissions(Permissions.BUILDS_TRIGGER)
def trigger_pipeline():
    """POST /v2/ci/trigger — Manual CI pipeline trigger."""
    data, error = CiTriggerRequest.from_json(request.get_json())
    if error:
        return bad_request(error)

    db = get_db_client()

    # Look up product from DB
    product = db.product.find_unique(where={"id": data.product_id})
    if not product:
        return bad_request("Product not found")

    # Get build config from Product model, fall back to static map
    product_config = _product_to_build_config(product, data.repo_slug)

    try:
        # Create build job with board from Product model
        board = product.buildBoard or product_config.get("board", "alpha_b0")
        build = db.buildjob.create(
            data={
                "product": data.repo_slug,
                "productId": product.id,
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


@require_permissions(Permissions.BUILDS_VIEW)
def list_ci_repos():
    """GET /v2/ci/settings/repos — List configured CI repositories.

    Used by build workers to get repo configs (ssh_url, build_script).
    Pulls from Product model in DB, with legacy REPO_PRODUCT_MAP as fallback.
    """
    base_url = os.environ.get("CONCORD_API_URL", "https://staging.concord.local")
    db = get_db_client()

    repos = []
    seen_slugs = set()

    # Primary source: Product model from DB
    products = db.product.find_many(where={"active": True})
    for product in products:
        metadata = product.metadata if isinstance(product.metadata, dict) else {}
        targets = metadata.get("targets", ["app", "comms"])

        # Main firmware repo
        if product.repoSlug:
            seen_slugs.add(product.repoSlug)
            repos.append({
                "id": product.repoSlug,
                "name": product.repoSlug,
                "productId": product.id,
                "productName": product.name,
                "firmwareType": product.repoSlug,
                "board": product.buildBoard or "",
                "targets": targets,
                "defaultVariant": "debug",
                "ncsVersion": metadata.get("ncsVersion", ""),
                "webhookUrl": f"{base_url}/v2/ci/webhooks/bitbucket",
                "connected": True,
                "branches": list(CI_TRIGGER_BRANCHES),
                "variants": ["debug", "release"],
                "mtibRev": "1.2",
                "lastEventAt": None,
                "sshUrl": product.repoSshUrl or "",
                "buildScript": metadata.get("buildScript", "scripts/build.sh"),
                "buildWestDir": product.buildWestDir or "",
            })

        # Manufacturing firmware repo
        if product.mfgRepoSlug:
            seen_slugs.add(product.mfgRepoSlug)
            repos.append({
                "id": product.mfgRepoSlug,
                "name": product.mfgRepoSlug,
                "productId": product.id,
                "productName": product.name,
                "firmwareType": product.mfgRepoSlug,
                "board": product.buildBoard or "",
                "targets": targets,
                "defaultVariant": "release",
                "ncsVersion": metadata.get("ncsVersion", ""),
                "webhookUrl": f"{base_url}/v2/ci/webhooks/bitbucket",
                "connected": True,
                "branches": list(CI_TRIGGER_BRANCHES),
                "variants": ["release"],
                "mtibRev": "1.2",
                "lastEventAt": None,
                "sshUrl": product.mfgRepoSshUrl or "",
                "buildScript": metadata.get("buildScript", "scripts/build.sh"),
                "buildMfgDir": product.buildMfgDir or "",
            })

    # Legacy fallback: include any static map entries not already covered by DB
    for slug, config in REPO_PRODUCT_MAP.items():
        if slug in seen_slugs:
            continue
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
            "connected": True,
            "branches": list(CI_TRIGGER_BRANCHES),
            "variants": ["debug", "release"] if "mfg" not in slug else ["release"],
            "mtibRev": "1.2",
            "lastEventAt": None,
            "sshUrl": config.get("ssh_url", ""),
            "buildScript": config.get("build_script", "scripts/build.sh"),
        })

    return jsonify(ApiResponse.ok(repos).to_dict()), 200
