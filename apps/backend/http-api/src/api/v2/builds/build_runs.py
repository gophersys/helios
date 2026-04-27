"""CI Build Run route handlers — thin wrappers around build_run_service."""

import io
import logging
import re
import zipfile
from datetime import datetime, timezone
from typing import Any, Dict

from flask import Response, jsonify, request

from src.lib.audit import log_audit
from src.lib.decorators import require_permissions
from src.lib.errors import bad_request, internal_error, not_found
from src.lib.permissions import Permissions
from src.lib.types import ApiResponse
from src.services.database.prisma import get_db_client
from src.services.builds.artifact_validator import validate_build_run_artifacts as _validate_artifacts
from src.services.builds.run_service import (
    check_build_run_completion,
    create_build_run_record,
    resolve_build_run_context,
    serialize_build_run,
    serialize_build_run_summary,
    trigger_build_run_validation,
)
from src.services.builds.trigger import trigger_stage_build
from src.services.storage.client import get_storage_client

from .builds import _sanitize_filename
from .types import BuildRunCreateRequest

logger = logging.getLogger(__name__)


def _build_zip_root_folder(build_run) -> str:
    """Derive a human-readable root folder name for artifact ZIP archives."""
    commit_short = build_run.commitSha[:7] if build_run.commitSha else "build"
    branch_safe = re.sub(r'[^\w\-]', '_', build_run.branch or "main")
    return f"{build_run.product}_{branch_safe}_{commit_short}"


def _artifact_zip_path(root_folder: str, product: str, variant_folder: str, name: str) -> str:
    """Build the path within a ZIP for an artifact, routing to subfolders by extension."""
    clean = re.sub(r'^\d+\.\d+\.\d+_(debug|no_debug|release)_', '', name)
    if clean.endswith('.hex') or clean.endswith('.bin'):
        return f"{root_folder}/{product}/{variant_folder}/firmware/{clean}"
    if clean.endswith('.cfw'):
        return f"{root_folder}/{product}/{variant_folder}/cfw/{clean}"
    return f"{root_folder}/{product}/{variant_folder}/{clean}"


def _collect_artifacts_zip(storage, build_run, root_folder: str) -> bytes:
    """Download all build artifacts and pack them into a ZIP archive."""
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for build in build_run.builds:
            if not build.artifacts:
                continue
            variant = build.variant or "release"
            variant_folder = "release" if variant == "no_debug" else variant
            for artifact in build.artifacts:
                try:
                    response = storage.get_object("concord", artifact.storageKey)
                    content = response.read()
                    response.close()
                    response.release_conn()
                    zip_path = _artifact_zip_path(root_folder, build.product, variant_folder, artifact.name)
                    zf.writestr(zip_path, content)
                except Exception as e:
                    logger.warning("Failed to add %s to ZIP: %s", artifact.name, e)
    zip_buffer.seek(0)
    return zip_buffer.getvalue()


@require_permissions(Permissions.BUILDS_VIEW)
def list_build_runs():
    """GET /v2/builds/runs — List build runs."""
    db = get_db_client()

    page = max(1, request.args.get("page", 1, type=int))
    limit = min(max(1, request.args.get("limit", 20, type=int)), 100)
    skip = (page - 1) * limit

    product = request.args.get("product")
    product_id = request.args.get("productId")
    branch = request.args.get("branch")
    status = request.args.get("status")
    stage = request.args.get("stage", type=int)
    pr_number = request.args.get("prNumber", type=int)
    trigger_type = request.args.get("triggerType")
    created_after = request.args.get("createdAfter")
    created_before = request.args.get("createdBefore")
    # Legacy compat: matrixMode still accepted but stage is preferred
    matrix_mode = request.args.get("matrixMode")

    where: Dict[str, Any] = {}
    if product_id:
        where["productId"] = product_id
    elif product:
        where["product"] = {"is": {"OR": [{"name": product}, {"slug": product}]}}
    if branch:
        where["branch"] = {"contains": branch}
    if status:
        where["status"] = status
    if stage:
        where["stage"] = stage
    elif matrix_mode:
        where["matrixMode"] = matrix_mode
    if pr_number:
        where["prNumber"] = pr_number
    if trigger_type:
        where["triggerType"] = trigger_type
    if created_after or created_before:
        date_filter = {}
        if created_after:
            try:
                date_filter["gte"] = datetime.fromisoformat(created_after.replace("Z", "+00:00"))
            except ValueError:
                pass
        if created_before:
            try:
                date_filter["lte"] = datetime.fromisoformat(created_before.replace("Z", "+00:00"))
            except ValueError:
                pass
        if date_filter:
            where["createdAt"] = date_filter

    try:
        total = db.buildrun.count(where=where)
        build_runs = db.buildrun.find_many(
            where=where,
            skip=skip,
            take=limit,
            order={"createdAt": "desc"},
            include={"builds": {"include": {"product": True}}, "product": True},
        )

        pages = (total + limit - 1) // limit if limit > 0 else 0

        return jsonify(ApiResponse.ok({
            "data": [serialize_build_run_summary(p) for p in build_runs],
            "pagination": {
                "page": page,
                "limit": limit,
                "total": total,
                "pages": pages,
            },
        }).to_dict()), 200

    except Exception as e:
        logger.exception("Failed to list build runs: %s", e)
        return internal_error("Failed to list build runs")


@require_permissions(Permissions.BUILDS_VIEW)
def get_build_run(run_id: str):
    """GET /v2/builds/runs/<id> — Get build run details with builds."""
    db = get_db_client()

    try:
        build_run = db.buildrun.find_unique(
            where={"id": run_id},
            include={"builds": {"include": {"artifacts": True, "product": True}}, "product": True},
        )
        if not build_run:
            return not_found(f"Build run not found: {run_id}")

        return jsonify(ApiResponse.ok(serialize_build_run(build_run)).to_dict()), 200

    except Exception as e:
        logger.error("Failed to get build run %s: %s", run_id, e)
        return internal_error("Failed to get build run")


@require_permissions(Permissions.BUILDS_VIEW)
def download_build_run_artifacts(run_id: str):
    """GET /v2/builds/runs/<id>/artifacts/download — Download all artifacts as ZIP."""
    db = get_db_client()

    build_run = db.buildrun.find_unique(
        where={"id": run_id},
        include={"builds": {"include": {"artifacts": True, "product": True}}, "product": True},
    )
    if not build_run:
        return not_found(f"Build run not found: {run_id}")

    if not build_run.builds:
        return not_found("No builds found for this build run")

    try:
        storage = get_storage_client()
        root_folder = _build_zip_root_folder(build_run)
        zip_buffer = _collect_artifacts_zip(storage, build_run, root_folder)

        zip_filename = f"{root_folder}.zip"
        return Response(
            zip_buffer,
            mimetype="application/zip",
            headers={
                "Content-Disposition": f'attachment; filename="{_sanitize_filename(zip_filename)}"',
                "Content-Length": str(len(zip_buffer)),
            },
        )

    except Exception as e:
        logger.error("Failed to create ZIP for build run %s: %s", run_id, e)
        return internal_error("Failed to create artifact ZIP")


@require_permissions(Permissions.BUILDS_TRIGGER)
def create_build_run():
    """POST /v2/builds/runs — Create a new build run (triggers builds)."""
    data, error = BuildRunCreateRequest.from_json(request.get_json())
    if error:
        return bad_request(error)

    db = get_db_client()

    try:
        ctx = resolve_build_run_context(db, data)
        build_run, builds = create_build_run_record(db, data, ctx)
        return jsonify(ApiResponse.created(serialize_build_run(build_run)).to_dict()), 201

    except Exception as e:
        logger.error("Failed to create build run: %s", e)
        return internal_error("Failed to create build run")


@require_permissions(Permissions.BUILDS_MANAGE)
def cancel_build_run(run_id: str):
    """POST /v2/builds/runs/<id>/cancel — Cancel a build run."""
    db = get_db_client()

    try:
        build_run = db.buildrun.find_unique(where={"id": run_id})
        if not build_run:
            return not_found(f"Build run not found: {run_id}")

        if build_run.status in ("SUCCESS", "FAILED", "CANCELLED"):
            return bad_request(f"Build run already in terminal state: {build_run.status}")

        db.buildjob.update_many(
            where={
                "buildRunId": run_id,
                "status": {"in": ["QUEUED", "CLONING", "BUILDING"]},
            },
            data={"status": "CANCELLED"},
        )

        build_run = db.buildrun.update(
            where={"id": run_id},
            data={"status": "CANCELLED", "finishedAt": datetime.now(timezone.utc)},
            include={"builds": {"include": {"product": True}}, "product": True},
        )

        log_audit("ci.build_run.cancel", "BuildRun", run_id, {})

        return jsonify(ApiResponse.ok(serialize_build_run(build_run)).to_dict()), 200

    except Exception as e:
        logger.error("Failed to cancel build run %s: %s", run_id, e)
        return internal_error("Failed to cancel build run")


@require_permissions(Permissions.BUILDS_MANAGE)
def retrigger_build_run(run_id: str):
    """POST /v2/builds/runs/<id>/retrigger — Re-trigger a build run with the same config."""
    db = get_db_client()

    build_run = db.buildrun.find_unique(
        where={"id": run_id},
        include={"product": True},
    )
    if not build_run:
        return not_found(f"Build run not found: {run_id}")

    if not build_run.stageConfigId:
        return bad_request("Cannot retrigger: no stage config associated with this run")

    # Reconstruct event metadata from the original run
    event_metadata = {
        "source": "retrigger",
        "source_commit": build_run.commitSha,
        "pr_id": build_run.prNumber,
        "pr_title": build_run.prTitle,
        "pr_author": build_run.prAuthor,
        "source_branch": build_run.sourceBranch,
        "target_branch": build_run.targetBranch,
        "pr_url": build_run.prUrl,
    }

    try:
        result = trigger_stage_build(
            product_id=build_run.productId,
            stage_config_id=build_run.stageConfigId,
            event_metadata=event_metadata,
        )
        if not result:
            return internal_error("Failed to trigger build — check product config")

        log_audit("ci.build_run.retrigger", "BuildRun", result["buildRunId"], {
            "originalRunId": run_id,
            "jobCount": result["jobCount"],
        })

        return jsonify(ApiResponse.ok(result).to_dict()), 201
    except Exception as e:
        logger.exception("Failed to retrigger build run %s", run_id)
        return internal_error("Failed to retrigger build run")


@require_permissions(Permissions.BUILDS_VIEW)
def list_build_run_sessions(run_id: str):
    """GET /v2/builds/runs/<id>/sessions — List sessions triggered by this build run."""
    db = get_db_client()

    page = max(1, request.args.get("page", 1, type=int))
    limit = min(max(1, request.args.get("limit", 20, type=int)), 100)
    skip = (page - 1) * limit

    try:
        build_run = db.buildrun.find_unique(where={"id": run_id})
        if not build_run:
            return not_found(f"Build run not found: {run_id}")

        where = {"buildRunId": run_id}
        total = db.testrun.count(where=where)
        runs = db.testrun.find_many(
            where=where,
            skip=skip,
            take=limit,
            order={"createdAt": "desc"},
            include={"product": True},
        )

        pages = (total + limit - 1) // limit if limit > 0 else 0

        data = []
        for r in runs:
            entry = {
                "id": r.id,
                "name": r.name,
                "type": r.type if hasattr(r, "type") else "VALIDATION",
                "productId": r.productId,
                "status": r.status,
                "targetCount": r.targetCount,
                "completedCount": r.completedCount,
                "passedCount": r.passedCount,
                "failedCount": r.failedCount,
                "startedAt": r.startedAt.isoformat() if r.startedAt else None,
                "completedAt": r.completedAt.isoformat() if r.completedAt else None,
                "createdAt": r.createdAt.isoformat(),
            }
            if hasattr(r, "product") and r.product is not None:
                entry["product"] = {"id": r.product.id, "name": r.product.name}
            data.append(entry)

        return jsonify(ApiResponse.ok({
            "data": data,
            "pagination": {
                "page": page,
                "limit": limit,
                "total": total,
                "pages": pages,
            },
        }).to_dict()), 200

    except Exception as e:
        logger.error("Failed to list build run sessions %s: %s", run_id, e)
        return internal_error("Failed to list build run sessions")


@require_permissions(Permissions.BUILDS_MANAGE)
def validate_build_run(run_id: str):
    """POST /v2/builds/runs/<id>/validate — Manually trigger validation for a completed build run."""
    db = get_db_client()

    try:
        build_run = db.buildrun.find_unique(
            where={"id": run_id},
            include={"builds": {"include": {"product": True}}, "product": True},
        )
        if not build_run:
            return not_found(f"Build run not found: {run_id}")

        if build_run.status not in ("SUCCESS", "FAILED", "BUILD_FAILED", "VALIDATING"):
            return bad_request(f"Cannot trigger validation for build run in {build_run.status} state")

        builds = build_run.builds or []
        succeeded = [b for b in builds if b.status in ("SUCCESS", "CACHED")]
        if not succeeded:
            return bad_request("No successful builds — cannot trigger validation")

        if build_run.validationRunId:
            prior_run = db.testrun.find_unique(where={"id": build_run.validationRunId})
            if prior_run and prior_run.status in ("ACTIVE", "RUNNING"):
                logger.info("Prior run %s still active, queuing new validation", build_run.validationRunId[:8])
                result = {"queued": True, "entryId": None, "reason": "Prior run still active"}
                try:
                    entry = db.validationqueueentry.create(data={
                        "buildRunId": run_id,
                        "stage": 4,
                        "priority": 0,
                        "status": "QUEUED",
                        "stageConfigId": getattr(build_run, "stageConfigId", None),
                        "reason": f"Prior run {build_run.validationRunId[:8]} still active",
                        "requestedAt": datetime.now(timezone.utc),
                    })
                    result["entryId"] = entry.id
                except Exception as e:
                    logger.warning("Failed to create queue entry: %s", e)
                    return bad_request("Prior validation still running. Try again after it completes.")

                log_audit("ci.build_run.validate_queued", "BuildRun", run_id, {
                    "queueEntryId": result["entryId"],
                    "reason": result.get("reason"),
                })
                return jsonify(ApiResponse.ok({
                    "buildRunId": run_id,
                    "queued": True,
                    "queueEntryId": result["entryId"],
                    "reason": result.get("reason"),
                    "status": "QUEUED",
                }).to_dict()), 202
            elif prior_run and prior_run.status not in ("ACTIVE", "RUNNING"):
                if prior_run.fixtureId:
                    db.fixture.update(where={"id": prior_run.fixtureId}, data={
                        "status": "AVAILABLE", "lockedBy": None, "lockedAt": None,
                    })
                logger.info("Prior run %s finished (%s), unlocked fixture", build_run.validationRunId[:8], prior_run.status)

        result = trigger_build_run_validation(run_id, build_run, builds)
        if result is None:
            return internal_error("Failed to create validation run (no fixtures available)")

        if result.get("queued"):
            log_audit("ci.build_run.validate_queued", "BuildRun", run_id, {
                "queueEntryId": result["entryId"],
                "reason": result.get("reason"),
            })
            return jsonify(ApiResponse.ok({
                "buildRunId": run_id,
                "queued": True,
                "queueEntryId": result["entryId"],
                "reason": result.get("reason"),
                "status": "QUEUED",
            }).to_dict()), 202

        validation_run_id = result["sessionId"]
        db.buildrun.update(
            where={"id": run_id},
            data={"status": "VALIDATING", "validationRunId": validation_run_id},
        )

        log_audit("ci.build_run.validate_manual", "BuildRun", run_id, {
            "validationRunId": validation_run_id,
        })

        return jsonify(ApiResponse.ok({
            "buildRunId": run_id,
            "validationRunId": validation_run_id,
            "status": "VALIDATING",
        }).to_dict()), 200

    except Exception as e:
        logger.error("Failed to trigger validation for build run %s: %s", run_id, e)
        return internal_error("Failed to trigger validation")


@require_permissions(Permissions.BUILDS_VIEW)
def validate_build_run_artifacts_endpoint(run_id: str):
    """POST /v2/builds/runs/<id>/validate-artifacts

    Returns a structured report of artifact completeness for a build run.
    Does not mutate build run state — read-only validation check.
    """
    db = get_db_client()

    try:
        build_run = db.buildrun.find_unique(where={"id": run_id})
        if not build_run:
            return not_found(f"Build run not found: {run_id}")

        result = _validate_artifacts(db, run_id)

        return jsonify(ApiResponse.ok(result).to_dict()), 200

    except Exception as e:
        logger.error("Failed to validate artifacts for build run %s: %s", run_id, e)
        return internal_error("Failed to validate build run artifacts")


# ---------------------------------------------------------------------------
#  POST /v2/builds/runs/batch — batch action on multiple build runs
# ---------------------------------------------------------------------------


@require_permissions(Permissions.BUILDS_MANAGE)
def batch_build_runs_action():
    """Apply an action to multiple build runs at once."""
    db = get_db_client()
    body = request.get_json()
    if not body:
        return bad_request("Request body required")

    action = (body.get("action") or "").strip().lower()
    ids = body.get("ids", [])

    if action not in ("cancel",):
        return bad_request("action must be 'cancel'")
    if not isinstance(ids, list) or not ids:
        return bad_request("ids must be a non-empty array")

    succeeded = []
    failed = []

    for rid in ids:
        build_run = db.buildrun.find_unique(where={"id": rid})
        if not build_run:
            failed.append({"id": rid, "reason": "Not found"})
            continue

        if build_run.status in ("SUCCESS", "FAILED", "CANCELLED"):
            failed.append({"id": rid, "reason": f"Build run already in terminal state: {build_run.status}"})
            continue

        db.buildrun.update(
            where={"id": rid},
            data={"status": "CANCELLED", "finishedAt": datetime.now(timezone.utc)},
        )
        log_audit("ci.build_run.cancel", "BuildRun", rid, {"batch": True})
        succeeded.append(rid)

    return jsonify(ApiResponse.ok({
        "action": action,
        "succeeded": succeeded,
        "failed": failed,
    }).to_dict()), 200
