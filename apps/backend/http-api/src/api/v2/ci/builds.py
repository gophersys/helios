"""CI Build endpoints — CRUD for build jobs and artifacts."""

import logging
import math
from typing import Any

from database import Json
from flask import jsonify, request

from src.lib.audit import log_audit
from src.lib.decorators import require_permissions
from src.lib.errors import bad_request, internal_error, not_found
from src.lib.permissions import Permissions
from src.lib.types import ApiResponse
from src.services.database.prisma import get_db_client

from .types import BuildCreateRequest

logger = logging.getLogger(__name__)


# -------------------------------------------------
#                                      Serializers
# -------------------------------------------------

def _serialize_build_job(b: Any) -> dict:
    """Serialize a BuildJob model to a JSON-friendly dict."""
    data = {
        "id": b.id,
        "product": b.product,
        "board": b.board,
        "target": b.target,
        "variant": b.variant,
        "mtibRev": b.mtibRev,
        "branch": b.branch,
        "commitSha": b.commitSha,
        "status": b.status,
        "versionMajor": b.versionMajor,
        "versionMinor": b.versionMinor,
        "buildNum": b.buildNum,
        "versionString": b.versionString,
        "errorMessage": b.errorMessage,
        "startedAt": b.startedAt.isoformat() if b.startedAt else None,
        "finishedAt": b.finishedAt.isoformat() if b.finishedAt else None,
        "durationSeconds": b.durationSeconds,
        "createdAt": b.createdAt.isoformat(),
        "updatedAt": b.updatedAt.isoformat(),
        # Stage 4 build matrix fields
        "matrixLabel": getattr(b, "matrixLabel", None),
        "matrixIndex": getattr(b, "matrixIndex", None),
        "versionBump": getattr(b, "versionBump", False),
        "baseJobId": getattr(b, "baseJobId", None),
    }
    if hasattr(b, "artifacts") and b.artifacts is not None:
        data["artifacts"] = [_serialize_build_artifact(a) for a in b.artifacts]
        data["artifactCount"] = len(b.artifacts)
    return data


def _serialize_build_artifact(a: Any) -> dict:
    """Serialize a BuildJobArtifact model to a JSON-friendly dict."""
    return {
        "id": a.id,
        "buildJobId": a.buildJobId,
        "name": a.name,
        "storageKey": a.storageKey,
        "sizeBytes": int(a.sizeBytes),
        "checksum": a.checksum,
        "createdAt": a.createdAt.isoformat(),
    }


# -------------------------------------------------
#                                 Public Endpoints
# -------------------------------------------------

@require_permissions(Permissions.ADMIN_CI_VIEW)
def list_builds():
    """GET /v2/ci/builds — List build jobs with pagination and filters."""
    db = get_db_client()

    page = max(1, request.args.get("page", 1, type=int))
    limit = min(max(1, request.args.get("limit", 50, type=int)), 100)
    skip = (page - 1) * limit

    # Build filter
    where = {}

    status = request.args.get("status")
    if status:
        where["status"] = status.upper()

    product = request.args.get("product")
    if product:
        where["product"] = product

    branch = request.args.get("branch")
    if branch:
        where["branch"] = branch

    board = request.args.get("board")
    if board:
        where["board"] = board

    total = db.buildjob.count(where=where)
    builds = db.buildjob.find_many(
        where=where,
        skip=skip,
        take=limit,
        order={"createdAt": "desc"},
        include={"artifacts": True},
    )

    pages = math.ceil(total / limit) if limit > 0 else 0

    return jsonify(ApiResponse.paginated(
        data=[_serialize_build_job(b) for b in builds],
        page=page,
        total_pages=pages,
        total_results=total,
        results_per_page=limit,
    ).to_dict()), 200


@require_permissions(Permissions.ADMIN_CI_VIEW)
def get_build(build_id: str):
    """GET /v2/ci/builds/<id> — Build detail with artifacts and log."""
    db = get_db_client()

    build = db.buildjob.find_unique(
        where={"id": build_id},
        include={"artifacts": True},
    )

    if not build:
        return not_found("Build job not found")

    data = _serialize_build_job(build)
    # Include build log in detail view
    data["buildLog"] = build.buildLog

    return jsonify(ApiResponse.ok(data).to_dict()), 200


@require_permissions(Permissions.ADMIN_CI_VIEW)
def list_build_artifacts(build_id: str):
    """GET /v2/ci/builds/<id>/artifacts — List artifacts for a build."""
    db = get_db_client()

    build = db.buildjob.find_unique(where={"id": build_id})
    if not build:
        return not_found("Build job not found")

    artifacts = db.buildjobartifact.find_many(
        where={"buildJobId": build_id},
        order={"createdAt": "asc"},
    )

    return jsonify(ApiResponse.ok(
        [_serialize_build_artifact(a) for a in artifacts]
    ).to_dict()), 200


@require_permissions(Permissions.ADMIN_CI_VIEW)
def get_build_log(build_id: str):
    """GET /v2/ci/builds/<id>/log — Get build log content."""
    db = get_db_client()

    build = db.buildjob.find_unique(where={"id": build_id})
    if not build:
        return not_found("Build job not found")

    return jsonify(ApiResponse.ok({
        "buildId": build_id,
        "status": build.status,
        "log": build.buildLog or "",
    }).to_dict()), 200


@require_permissions(Permissions.ADMIN_CI_MANAGE)
def create_build():
    """POST /v2/ci/builds — Trigger a manual build."""
    data, error = BuildCreateRequest.from_json(request.get_json())
    if error:
        return bad_request(error)

    db = get_db_client()

    try:
        build = db.buildjob.create(
            data={
                "product": data.product,
                "board": data.board,
                "target": data.target,
                "variant": data.variant,
                "mtibRev": data.mtib_rev,
                "branch": data.branch,
                "commitSha": data.commit_sha,
                "status": "QUEUED",
                "webhookData": Json(data.config) if data.config else Json({"source": "manual"}),
            },
            include={"artifacts": True},
        )

        log_audit("ci.build.create", "BuildJob", build.id, {
            "product": data.product,
            "board": data.board,
            "target": data.target,
            "variant": data.variant,
            "branch": data.branch,
        })

        return jsonify(ApiResponse.created(_serialize_build_job(build)).to_dict()), 201

    except Exception as e:
        logger.error("Failed to create build job: %s", e)
        return internal_error("Failed to create build job")


@require_permissions(Permissions.ADMIN_CI_MANAGE)
def update_build(build_id: str):
    """PATCH /v2/ci/builds/<id> — Update build status (used by workers)."""
    db = get_db_client()

    build = db.buildjob.find_unique(where={"id": build_id})
    if not build:
        return not_found("Build job not found")

    data = request.get_json() or {}
    update_data = {}

    # Allowed fields for update
    if "status" in data:
        status = data["status"].upper()
        if status not in ("QUEUED", "BUILDING", "SUCCESS", "FAILED", "CANCELLED"):
            return bad_request("Invalid status")
        update_data["status"] = status

    if "workerId" in data:
        # Store in webhookData for tracking
        webhook_data = build.webhookData or {}
        if isinstance(webhook_data, dict):
            webhook_data["workerId"] = data["workerId"]
            update_data["webhookData"] = Json(webhook_data)

    if "errorMessage" in data:
        update_data["errorMessage"] = data["errorMessage"][:4000] if data["errorMessage"] else None

    if "versionString" in data:
        update_data["versionString"] = data["versionString"]

    if "durationSeconds" in data:
        update_data["durationSeconds"] = int(data["durationSeconds"])

    if "startedAt" in data:
        from datetime import datetime
        try:
            update_data["startedAt"] = datetime.fromisoformat(data["startedAt"].replace("Z", "+00:00"))
        except:
            pass

    if "finishedAt" in data:
        from datetime import datetime
        try:
            update_data["finishedAt"] = datetime.fromisoformat(data["finishedAt"].replace("Z", "+00:00"))
        except:
            pass

    if "buildLog" in data:
        update_data["buildLog"] = data["buildLog"]

    # Support updating version bump config (for matrix fixups)
    if "versionBump" in data:
        update_data["versionBump"] = bool(data["versionBump"])

    if "baseJobId" in data:
        update_data["baseJobId"] = data["baseJobId"]

    if not update_data:
        return bad_request("No valid fields to update")

    try:
        updated = db.buildjob.update(
            where={"id": build_id},
            data=update_data,
            include={"artifacts": True},
        )

        # Check if this build is part of a pipeline and if the pipeline is complete
        if updated.pipelineRunId and update_data.get("status") in ("SUCCESS", "FAILED", "CANCELLED"):
            from .pipelines import check_pipeline_completion
            new_pipeline_status = check_pipeline_completion(updated.pipelineRunId)
            if new_pipeline_status:
                logger.info("Build %s finished, pipeline %s now %s",
                           build_id, updated.pipelineRunId, new_pipeline_status)

        return jsonify(ApiResponse.ok(_serialize_build_job(updated)).to_dict()), 200

    except Exception as e:
        logger.error("Failed to update build job: %s", e)
        return internal_error("Failed to update build job")


@require_permissions(Permissions.ADMIN_CI_MANAGE)
def upload_build_artifact(build_id: str):
    """POST /v2/ci/builds/<id>/artifacts — Upload a build artifact."""
    import hashlib
    from src.services.storage.client import get_storage_client, storage_key, StoragePrefixes

    db = get_db_client()

    build = db.buildjob.find_unique(where={"id": build_id})
    if not build:
        return not_found("Build job not found")

    if "file" not in request.files:
        return bad_request("No file provided")

    file = request.files["file"]
    if not file.filename:
        return bad_request("No filename provided")

    try:
        # Read file content
        content = file.read()
        size_bytes = len(content)
        checksum = hashlib.sha256(content).hexdigest()

        # Generate storage key
        key = storage_key(
            StoragePrefixes.FIRMWARE_BUILDS,
            f"{build.product}/{build.id}/{file.filename}"
        )

        # Upload to MinIO
        storage = get_storage_client()
        from io import BytesIO
        storage.put_object(
            bucket_name="concord",
            object_name=key,
            data=BytesIO(content),
            length=size_bytes,
        )

        # Create artifact record
        artifact = db.buildjobartifact.create(
            data={
                "buildJobId": build_id,
                "name": file.filename,
                "storageKey": key,
                "sizeBytes": size_bytes,
                "checksum": checksum,
            },
        )

        log_audit("ci.artifact.upload", "BuildJobArtifact", artifact.id, {
            "buildJobId": build_id,
            "name": file.filename,
            "sizeBytes": size_bytes,
        })

        return jsonify(ApiResponse.created(_serialize_build_artifact(artifact)).to_dict()), 201

    except Exception as e:
        logger.error("Failed to upload artifact: %s", e)
        return internal_error("Failed to upload artifact")


def _get_clean_artifact_name(artifact_name: str) -> str:
    """Strip version/variant prefix from artifact name (e.g. '0.0.0_debug_app_nrf52840.hex' -> 'app_nrf52840.hex')."""
    import re
    # Match pattern: version_variant_ prefix (e.g. "0.0.0_debug_" or "1.2.3_no_debug_")
    match = re.match(r'^\d+\.\d+\.\d+_(debug|no_debug|release)_(.+)$', artifact_name)
    if match:
        return match.group(2)
    return artifact_name


def _get_artifact_folder(clean_name: str) -> str:
    """Determine which subfolder an artifact should go in."""
    if clean_name.endswith('.hex') or clean_name.endswith('.bin'):
        return "firmware"
    elif clean_name.endswith('.cfw'):
        return "cfw"
    return ""


@require_permissions(Permissions.ADMIN_CI_VIEW)
def download_build_artifacts(build_id: str):
    """GET /v2/ci/builds/<id>/artifacts/download — Download all artifacts as ZIP.

    Creates a structured ZIP:
      <product>_<variant>_<version>/
        firmware/
          app_nrf52840.hex
          comms_nrf9151.hex
        cfw/
          108.x.x.x.cfw
          109.x.x.x.cfw
        build.json
    """
    import io
    import zipfile
    from flask import Response
    from src.services.storage.client import get_storage_client

    db = get_db_client()

    build = db.buildjob.find_unique(where={"id": build_id})
    if not build:
        return not_found("Build job not found")

    artifacts = db.buildjobartifact.find_many(
        where={"buildJobId": build_id},
        order={"createdAt": "asc"},
    )

    if not artifacts:
        return not_found("No artifacts found for this build")

    try:
        storage = get_storage_client()

        # Root folder name for this build
        version_str = build.versionString or "build"
        variant_str = build.variant or "release"
        root_folder = f"{build.product}_{variant_str}_{version_str}"

        # Create ZIP in memory
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            for artifact in artifacts:
                try:
                    # Download file from MinIO
                    response = storage.get_object("concord", artifact.storageKey)
                    content = response.read()
                    response.close()
                    response.release_conn()

                    # Clean the artifact name (strip version/variant prefix)
                    clean_name = _get_clean_artifact_name(artifact.name)

                    # Determine subfolder
                    subfolder = _get_artifact_folder(clean_name)

                    # Build the path in the ZIP
                    if subfolder:
                        zip_path = f"{root_folder}/{subfolder}/{clean_name}"
                    else:
                        zip_path = f"{root_folder}/{clean_name}"

                    zf.writestr(zip_path, content)
                except Exception as e:
                    logger.warning("Failed to add %s to ZIP: %s", artifact.name, e)
                    continue

        zip_buffer.seek(0)

        # Generate filename
        zip_filename = f"{root_folder}.zip"

        return Response(
            zip_buffer.getvalue(),
            mimetype="application/zip",
            headers={
                "Content-Disposition": f'attachment; filename="{zip_filename}"',
                "Content-Length": str(len(zip_buffer.getvalue())),
            },
        )

    except Exception as e:
        logger.error("Failed to create ZIP for build %s: %s", build_id, e)
        return internal_error("Failed to create artifact ZIP")


@require_permissions(Permissions.ADMIN_CI_MANAGE)
def stream_build_log(build_id: str):
    """POST /v2/ci/builds/<id>/log — Receive and broadcast log chunks from build worker.

    Used by build workers to stream real-time build output.
    Appends to buildLog in DB and broadcasts via WebSocket.
    """
    from .webhook import _emit_ci_event

    db = get_db_client()

    build = db.buildjob.find_unique(where={"id": build_id})
    if not build:
        return not_found("Build job not found")

    data = request.get_json() or {}
    chunk = data.get("chunk", "")

    if not chunk:
        return bad_request("No log chunk provided")

    try:
        # Append to buildLog in DB
        current_log = build.buildLog or ""
        # Limit total log size to 10MB to prevent DB bloat
        max_log_size = 10 * 1024 * 1024
        if len(current_log) + len(chunk) > max_log_size:
            # Trim from beginning to make room
            trim_size = len(chunk) + 10000  # Extra buffer
            current_log = current_log[trim_size:]

        new_log = current_log + chunk

        db.buildjob.update(
            where={"id": build_id},
            data={"buildLog": new_log},
        )

        # Broadcast via WebSocket for real-time UI updates
        _emit_ci_event("ci_build_log", {
            "buildId": build_id,
            "pipelineId": build.pipelineRunId,
            "chunk": chunk,
        })

        return jsonify(ApiResponse.ok({"received": len(chunk)}).to_dict()), 200

    except Exception as e:
        logger.error("Failed to stream build log: %s", e)
        return internal_error("Failed to stream build log")
