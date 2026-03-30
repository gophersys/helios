"""CI Pipeline route handlers — thin wrappers around pipeline_service."""

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
from src.services.artifact_validator import validate_pipeline_artifacts as _validate_artifacts
from src.services.pipeline_service import (
    check_pipeline_completion,
    create_pipeline_record,
    resolve_pipeline_context,
    serialize_pipeline,
    serialize_pipeline_summary,
    trigger_pipeline_validation,
)

from .builds import _sanitize_filename
from .types import PipelineCreateRequest

logger = logging.getLogger(__name__)


@require_permissions(Permissions.BUILDS_VIEW)
def list_pipelines():
    """GET /v2/builds/pipelines — List pipeline runs."""
    db = get_db_client()

    page = max(1, request.args.get("page", 1, type=int))
    limit = min(max(1, request.args.get("limit", 20, type=int)), 100)
    skip = (page - 1) * limit

    product = request.args.get("product")
    branch = request.args.get("branch")
    status = request.args.get("status")
    matrix_mode = request.args.get("matrixMode")

    where: Dict[str, Any] = {}
    if product:
        where["product"] = product
    if branch:
        where["branch"] = branch
    if status:
        where["status"] = status
    if matrix_mode:
        where["matrixMode"] = matrix_mode

    try:
        total = db.pipelinerun.count(where=where)
        pipelines = db.pipelinerun.find_many(
            where=where,
            skip=skip,
            take=limit,
            order={"createdAt": "desc"},
            include={"builds": {"include": {"product": True}}, "product": True},
        )

        pages = (total + limit - 1) // limit if limit > 0 else 0

        return jsonify(ApiResponse.ok({
            "data": [serialize_pipeline_summary(p) for p in pipelines],
            "pagination": {
                "page": page,
                "limit": limit,
                "total": total,
                "pages": pages,
            },
        }).to_dict()), 200

    except Exception as e:
        logger.error("Failed to list pipelines: %s", e)
        return internal_error("Failed to list pipelines")


@require_permissions(Permissions.BUILDS_VIEW)
def get_pipeline(pipeline_id: str):
    """GET /v2/builds/pipelines/<id> — Get pipeline details with builds."""
    db = get_db_client()

    try:
        pipeline = db.pipelinerun.find_unique(
            where={"id": pipeline_id},
            include={"builds": {"include": {"artifacts": True, "product": True}}, "product": True},
        )
        if not pipeline:
            return not_found(f"Pipeline not found: {pipeline_id}")

        return jsonify(ApiResponse.ok(serialize_pipeline(pipeline)).to_dict()), 200

    except Exception as e:
        logger.error("Failed to get pipeline %s: %s", pipeline_id, e)
        return internal_error("Failed to get pipeline")


@require_permissions(Permissions.BUILDS_VIEW)
def download_pipeline_artifacts(pipeline_id: str):
    """GET /v2/builds/pipelines/<id>/artifacts/download — Download all artifacts as ZIP."""
    from src.services.storage.client import get_storage_client

    db = get_db_client()

    pipeline = db.pipelinerun.find_unique(
        where={"id": pipeline_id},
        include={"builds": {"include": {"artifacts": True, "product": True}}, "product": True},
    )
    if not pipeline:
        return not_found(f"Pipeline not found: {pipeline_id}")

    if not pipeline.builds:
        return not_found("No builds found for this pipeline")

    def get_clean_name(name: str) -> str:
        match = re.match(r'^\d+\.\d+\.\d+_(debug|no_debug|release)_(.+)$', name)
        return match.group(2) if match else name

    def get_folder(name: str) -> str:
        if name.endswith('.hex') or name.endswith('.bin'):
            return "firmware"
        elif name.endswith('.cfw'):
            return "cfw"
        return ""

    try:
        storage = get_storage_client()

        commit_short = pipeline.commitSha[:7] if pipeline.commitSha else "build"
        branch_safe = re.sub(r'[^\w\-]', '_', pipeline.branch or "main")
        root_folder = f"{pipeline.product}_{branch_safe}_{commit_short}"

        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            for build in pipeline.builds:
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

                        clean_name = get_clean_name(artifact.name)
                        subfolder = get_folder(clean_name)

                        if subfolder:
                            zip_path = f"{root_folder}/{build.product}/{variant_folder}/{subfolder}/{clean_name}"
                        else:
                            zip_path = f"{root_folder}/{build.product}/{variant_folder}/{clean_name}"

                        zf.writestr(zip_path, content)
                    except Exception as e:
                        logger.warning("Failed to add %s to ZIP: %s", artifact.name, e)
                        continue

        zip_buffer.seek(0)
        zip_filename = f"{root_folder}.zip"

        return Response(
            zip_buffer.getvalue(),
            mimetype="application/zip",
            headers={
                "Content-Disposition": f'attachment; filename="{_sanitize_filename(zip_filename)}"',
                "Content-Length": str(len(zip_buffer.getvalue())),
            },
        )

    except Exception as e:
        logger.error("Failed to create ZIP for pipeline %s: %s", pipeline_id, e)
        return internal_error("Failed to create artifact ZIP")


@require_permissions(Permissions.BUILDS_TRIGGER)
def create_pipeline():
    """POST /v2/builds/pipelines — Create a new pipeline (triggers builds)."""
    data, error = PipelineCreateRequest.from_json(request.get_json())
    if error:
        return bad_request(error)

    db = get_db_client()

    try:
        ctx = resolve_pipeline_context(db, data)
        pipeline, builds = create_pipeline_record(db, data, ctx)
        return jsonify(ApiResponse.created(serialize_pipeline(pipeline)).to_dict()), 201

    except Exception as e:
        logger.error("Failed to create pipeline: %s", e)
        return internal_error("Failed to create pipeline")


@require_permissions(Permissions.BUILDS_MANAGE)
def cancel_pipeline(pipeline_id: str):
    """POST /v2/builds/pipelines/<id>/cancel — Cancel a pipeline."""
    db = get_db_client()

    try:
        pipeline = db.pipelinerun.find_unique(where={"id": pipeline_id})
        if not pipeline:
            return not_found(f"Pipeline not found: {pipeline_id}")

        if pipeline.status in ("SUCCESS", "FAILED", "CANCELLED"):
            return bad_request(f"Pipeline already in terminal state: {pipeline.status}")

        db.buildjob.update_many(
            where={
                "pipelineRunId": pipeline_id,
                "status": {"in": ["QUEUED", "CLONING", "BUILDING"]},
            },
            data={"status": "CANCELLED"},
        )

        pipeline = db.pipelinerun.update(
            where={"id": pipeline_id},
            data={"status": "CANCELLED", "finishedAt": datetime.now(timezone.utc)},
            include={"builds": {"include": {"product": True}}, "product": True},
        )

        log_audit("ci.pipeline.cancel", "PipelineRun", pipeline_id, {})

        return jsonify(ApiResponse.ok(serialize_pipeline(pipeline)).to_dict()), 200

    except Exception as e:
        logger.error("Failed to cancel pipeline %s: %s", pipeline_id, e)
        return internal_error("Failed to cancel pipeline")


@require_permissions(Permissions.BUILDS_VIEW)
def list_pipeline_sessions(pipeline_id: str):
    """GET /v2/builds/pipelines/<id>/sessions — List sessions triggered by this pipeline."""
    db = get_db_client()

    page = max(1, request.args.get("page", 1, type=int))
    limit = min(max(1, request.args.get("limit", 20, type=int)), 100)
    skip = (page - 1) * limit

    try:
        pipeline = db.pipelinerun.find_unique(where={"id": pipeline_id})
        if not pipeline:
            return not_found(f"Pipeline not found: {pipeline_id}")

        where = {"pipelineRunId": pipeline_id}
        total = db.session.count(where=where)
        sessions = db.session.find_many(
            where=where,
            skip=skip,
            take=limit,
            order={"createdAt": "desc"},
            include={"product": True},
        )

        pages = (total + limit - 1) // limit if limit > 0 else 0

        data = []
        for s in sessions:
            entry = {
                "id": s.id,
                "name": s.name,
                "type": s.type if hasattr(s, "type") else "VALIDATION",
                "productId": s.productId,
                "status": s.status,
                "targetCount": s.targetCount,
                "completedCount": s.completedCount,
                "passedCount": s.passedCount,
                "failedCount": s.failedCount,
                "startedAt": s.startedAt.isoformat() if s.startedAt else None,
                "finishedAt": s.finishedAt.isoformat() if s.finishedAt else None,
                "createdAt": s.createdAt.isoformat(),
            }
            if hasattr(s, "product") and s.product is not None:
                entry["product"] = {"id": s.product.id, "name": s.product.name}
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
        logger.error("Failed to list pipeline sessions %s: %s", pipeline_id, e)
        return internal_error("Failed to list pipeline sessions")


@require_permissions(Permissions.BUILDS_MANAGE)
def validate_pipeline(pipeline_id: str):
    """POST /v2/builds/pipelines/<id>/validate — Manually trigger validation for a completed pipeline."""
    db = get_db_client()

    try:
        pipeline = db.pipelinerun.find_unique(
            where={"id": pipeline_id},
            include={"builds": {"include": {"product": True}}, "product": True},
        )
        if not pipeline:
            return not_found(f"Pipeline not found: {pipeline_id}")

        if pipeline.status not in ("SUCCESS", "FAILED", "BUILD_FAILED", "VALIDATING"):
            return bad_request(f"Cannot trigger validation for pipeline in {pipeline.status} state")

        builds = pipeline.builds or []
        succeeded = [b for b in builds if b.status in ("SUCCESS", "CACHED")]
        if not succeeded:
            return bad_request("No successful builds — cannot trigger validation")

        if pipeline.validationRunId:
            prior_run = db.session.find_unique(where={"id": pipeline.validationRunId})
            if prior_run and prior_run.status in ("ACTIVE", "RUNNING"):
                logger.info("Prior run %s still active, queuing new validation", pipeline.validationRunId[:8])
                result = {"queued": True, "entryId": None, "reason": "Prior run still active"}
                try:
                    entry = db.validationqueueentry.create(data={
                        "pipelineRunId": pipeline_id,
                        "stage": 4,
                        "priority": 0,
                        "status": "QUEUED",
                        "reason": f"Prior run {pipeline.validationRunId[:8]} still active",
                        "requestedAt": datetime.now(timezone.utc),
                    })
                    result["entryId"] = entry.id
                except Exception as e:
                    logger.warning("Failed to create queue entry: %s", e)
                    return bad_request("Prior validation still running. Try again after it completes.")

                log_audit("ci.pipeline.validate_queued", "PipelineRun", pipeline_id, {
                    "queueEntryId": result["entryId"],
                    "reason": result.get("reason"),
                })
                return jsonify(ApiResponse.ok({
                    "pipelineId": pipeline_id,
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
                logger.info("Prior run %s finished (%s), unlocked fixture", pipeline.validationRunId[:8], prior_run.status)

        result = trigger_pipeline_validation(pipeline_id, pipeline, builds)
        if result is None:
            return internal_error("Failed to create validation run (no fixtures available)")

        if result.get("queued"):
            log_audit("ci.pipeline.validate_queued", "PipelineRun", pipeline_id, {
                "queueEntryId": result["entryId"],
                "reason": result.get("reason"),
            })
            return jsonify(ApiResponse.ok({
                "pipelineId": pipeline_id,
                "queued": True,
                "queueEntryId": result["entryId"],
                "reason": result.get("reason"),
                "status": "QUEUED",
            }).to_dict()), 202

        validation_run_id = result["sessionId"]
        db.pipelinerun.update(
            where={"id": pipeline_id},
            data={"status": "VALIDATING", "validationRunId": validation_run_id},
        )

        log_audit("ci.pipeline.validate_manual", "PipelineRun", pipeline_id, {
            "validationRunId": validation_run_id,
        })

        return jsonify(ApiResponse.ok({
            "pipelineId": pipeline_id,
            "validationRunId": validation_run_id,
            "status": "VALIDATING",
        }).to_dict()), 200

    except Exception as e:
        logger.error("Failed to trigger validation for pipeline %s: %s", pipeline_id, e)
        return internal_error("Failed to trigger validation")


@require_permissions(Permissions.BUILDS_VIEW)
def validate_pipeline_artifacts_endpoint(pipeline_id: str):
    """POST /v2/builds/pipelines/<id>/validate-artifacts

    Returns a structured report of artifact completeness for a pipeline.
    Does not mutate pipeline state — read-only validation check.
    """
    db = get_db_client()

    try:
        pipeline = db.pipelinerun.find_unique(where={"id": pipeline_id})
        if not pipeline:
            return not_found(f"Pipeline not found: {pipeline_id}")

        result = _validate_artifacts(db, pipeline_id)

        return jsonify(ApiResponse.ok(result).to_dict()), 200

    except Exception as e:
        logger.error("Failed to validate artifacts for pipeline %s: %s", pipeline_id, e)
        return internal_error("Failed to validate pipeline artifacts")
