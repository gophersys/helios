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
    CiTriggerRequest,
)

# Default trigger branches — used when a product has no triggerBranches configured
_DEFAULT_TRIGGER_BRANCHES = {"concord-main", "main", "develop"}


def _resolve_product_by_repo(db, repo_slug: str):
    """Resolve a Product record by repo slug.

    Returns the Product DB record or None.
    """
    return db.product.find_first(
        where={"slug": repo_slug},
        include={"boards": {"include": {"revisions": {"include": {"targets": True}}}}},
    )


def _get_trigger_branches(product) -> set:
    """Get the set of branches that should trigger CI for this product.

    Reads triggerBranches from product metadata, falls back to defaults.
    """
    metadata = product.metadata if isinstance(product.metadata, dict) else {}
    branches = metadata.get("triggerBranches")
    if branches and isinstance(branches, list):
        return set(branches)
    return _DEFAULT_TRIGGER_BRANCHES


def _product_to_build_config(product, repo_slug: str) -> dict:
    """Convert a Product record into the build config dict used by webhook/trigger.

    Uses Product.buildConfig (structured build config) with fallback to metadata.
    """
    build_config = product.buildConfig if isinstance(getattr(product, "buildConfig", None), dict) else {}
    metadata = product.metadata if isinstance(product.metadata, dict) else {}

    # Derive targets from BoardRevision.targets or fallback to metadata
    targets = []
    if hasattr(product, "boards") and product.boards:
        for board in product.boards:
            if hasattr(board, "revisions") and board.revisions:
                for rev in board.revisions:
                    if hasattr(rev, "targets") and rev.targets:
                        targets = [t.role for t in rev.targets]
                        break
            if targets:
                break
    if not targets:
        if build_config.get("targets"):
            targets = list(build_config["targets"].keys())
        else:
            targets = metadata.get("targets", ["app", "comms"])

    # Derive board from Board revision (ckBoardsName is on BoardRevision)
    board_name = build_config.get("board") or "alpha_b0"
    if hasattr(product, "boards") and product.boards:
        b = product.boards[0]
        if hasattr(b, "revisions") and b.revisions:
            board_name = b.revisions[0].ckBoardsName
        else:
            board_name = b.ckBoardsFamily

    return {
        "product_name": product.name,
        "firmware_type": repo_slug,
        "board": board_name,
        "targets": targets,
        "default_variant": "release",
        "ncs_version": build_config.get("ncsVersion") or metadata.get("ncsVersion", ""),
        "ssh_url": "",
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
    """POST /v2/builds/webhooks/bitbucket — Receive Bitbucket Server webhook.

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

    try:
        db = get_db_client()

        # Resolve product from DB by repo slug
        product_record = _resolve_product_by_repo(db, payload.repo_slug)
        if not product_record:
            logger.info("Ignoring webhook for unmapped repo: %s", payload.repo_slug)
            return jsonify(ApiResponse.ok({"ignored": True, "reason": "unmapped repo"}).to_dict()), 200

        # Check if branch triggers CI for this product
        trigger_branches = _get_trigger_branches(product_record)
        if payload.branch not in trigger_branches:
            logger.info("Ignoring webhook for non-CI branch %s (product %s triggers on: %s)",
                        payload.branch, product_record.name, trigger_branches)
            return jsonify(ApiResponse.ok({"ignored": True, "reason": "non-CI branch"}).to_dict()), 200

        product_config = _product_to_build_config(product_record, payload.repo_slug)
        logger.info("Resolved product '%s' (id=%s) from DB for repo %s",
                    product_record.name, product_record.id, payload.repo_slug)

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
def trigger_build_run():
    """POST /v2/builds/trigger — Manual CI pipeline trigger."""
    data, error = CiTriggerRequest.from_json(request.get_json())
    if error:
        return bad_request(error)

    db = get_db_client()

    # Look up product from DB
    product = db.product.find_unique(where={"id": data.product_id})
    if not product:
        return bad_request("Product not found")

    # Get build config from Product model
    product_config = _product_to_build_config(product, data.repo_slug)

    try:
        board = product_config.get("board", "alpha_b0")

        # Store version override in configFlags if provided
        config_flags = {}
        if data.firmware_version:
            config_flags["versionOverride"] = data.firmware_version

        build = db.buildjob.create(
            data={
                "product": data.repo_slug,
                "productId": product.id,
                "board": board,
                "target": "app",
                "variant": data.variant,
                "mtibRev": "1.2",
                "branch": data.branch,
                "commitSha": data.commit_sha,
                "status": "QUEUED",
                "configFlags": Json(config_flags) if config_flags else None,
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
    """GET /v2/builds/settings/repos — List configured CI repositories.

    Used by build workers to get repo configs (ssh_url, build_script).
    Pulls from Product model in DB, with legacy REPO_PRODUCT_MAP as fallback.
    """
    base_url = os.environ.get("CONCORD_API_URL", "https://staging.concord.local")
    db = get_db_client()

    repos = []

    # All repos come from Product model in DB
    products = db.product.find_many(
        where={"active": True},
        include={"boards": {"include": {"revisions": {"include": {"targets": True}}}}},
    )
    for product in products:
        build_config = product.buildConfig if isinstance(getattr(product, "buildConfig", None), dict) else {}
        metadata = product.metadata if isinstance(product.metadata, dict) else {}
        trigger_branches = list(_get_trigger_branches(product))

        # Derive targets from BoardRevision.targets or fallback
        targets = []
        if hasattr(product, "boards") and product.boards:
            for brd in product.boards:
                if hasattr(brd, "revisions") and brd.revisions:
                    for rev in brd.revisions:
                        if hasattr(rev, "targets") and rev.targets:
                            targets = [t.role for t in rev.targets]
                            break
                if targets:
                    break
        if not targets:
            if build_config.get("targets"):
                targets = list(build_config["targets"].keys())
            else:
                targets = metadata.get("targets", ["app", "comms"])

        # Derive board from Board revision (ckBoardsName is on BoardRevision)
        board = build_config.get("board") or ""
        if hasattr(product, "boards") and product.boards:
            b = product.boards[0]
            if hasattr(b, "revisions") and b.revisions:
                board = b.revisions[0].ckBoardsName
            else:
                board = b.ckBoardsFamily
        ncs_version = build_config.get("ncsVersion") or metadata.get("ncsVersion", "")

        product_slug = product.slug or product.name.lower().replace(" ", "_")
        repos.append({
            "id": product_slug,
            "name": product_slug,
            "productId": product.id,
            "productName": product.name,
            "firmwareType": product_slug,
            "board": board,
            "targets": targets,
            "defaultVariant": "release",
            "ncsVersion": ncs_version,
            "webhookUrl": f"{base_url}/v2/builds/webhooks/bitbucket",
            "connected": True,
            "branches": trigger_branches,
            "variants": ["debug", "release"],
            "mtibRev": "1.2",
            "lastEventAt": None,
        })

    return jsonify(ApiResponse.ok(repos).to_dict()), 200
