"""CI Build endpoints — CRUD for build jobs and artifacts."""

import logging
import math
from typing import Any

from database import Json
from flask import jsonify, request

from src.lib.audit import log_audit
from src.lib.decorators import require_permissions
from src.lib.errors import bad_request, conflict, internal_error, not_found
from src.lib.permissions import Permissions
from src.lib.types import ApiResponse
from src.services.database.prisma import get_db_client

from .build_cache import compute_build_fingerprint, find_cached_build
from .types import BuildCreateRequest

logger = logging.getLogger(__name__)


def _sanitize_filename(filename: str) -> str:
    """Sanitize a filename for use in Content-Disposition header.

    Removes characters that could cause header injection or parsing issues.
    """
    # Remove or replace problematic characters
    sanitized = filename.replace('"', "'").replace("\r", "").replace("\n", "").replace("\\", "_")
    # Ensure it's not empty
    return sanitized if sanitized else "download"


# -------------------------------------------------
#                                      Serializers
# -------------------------------------------------

def _derive_product_slug(b: Any) -> str | None:
    """Derive the product slug from build + product relation."""
    product = getattr(b, "product", None)

    if isinstance(product, str):
        return product

    if not product or not hasattr(product, "slug"):
        return getattr(b, "productId", None)

    return product.slug or product.name


def _serialize_build_job(b: Any) -> dict:
    """Serialize a BuildJob model to a JSON-friendly dict."""
    data = {
        "id": b.id,
        "product": _derive_product_slug(b),
        "productId": getattr(b, "productId", None),
        "productName": b.product.name if hasattr(b, "product") and b.product and hasattr(b.product, "name") else None,
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
        "workerId": getattr(b, "workerId", None) or (b.webhookData.get("workerId") if isinstance(getattr(b, "webhookData", None), dict) else None),
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
        "configFlags": getattr(b, "configFlags", None),
        "reusedFromId": getattr(b, "reusedFromId", None),
        "buildFingerprint": getattr(b, "buildFingerprint", None),
        "triggerType": getattr(b, "triggerType", "worker"),
        "notes": getattr(b, "notes", None),
    }
    if hasattr(b, "artifacts") and b.artifacts is not None:
        data["artifacts"] = [_serialize_build_artifact(a) for a in b.artifacts]
        data["artifactCount"] = len(b.artifacts)
    return data


def _serialize_build_artifact(a: Any) -> dict:
    """Serialize a BuildArtifact model to a JSON-friendly dict."""
    return {
        "id": a.id,
        "buildJobId": a.buildJobId,
        "name": a.name,
        "storageKey": a.storageKey,
        "sizeBytes": int(a.sizeBytes),
        "checksum": a.checksum,
        "role": getattr(a, "role", None),
        "processor": getattr(a, "processor", None),
        "artifactType": getattr(a, "artifactType", None),
        "contentType": getattr(a, "contentType", None),
        "createdAt": a.createdAt.isoformat(),
    }


# -------------------------------------------------
#                                 Public Endpoints
# -------------------------------------------------

@require_permissions(Permissions.BUILDS_VIEW)
def list_builds():
    """GET /v2/builds — List build jobs with pagination and filters."""
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

    trigger_type = request.args.get("triggerType")
    if trigger_type:
        where["triggerType"] = trigger_type

    product_id = request.args.get("productId")
    if product_id:
        where["productId"] = product_id

    total = db.buildjob.count(where=where)
    builds = db.buildjob.find_many(
        where=where,
        skip=skip,
        take=limit,
        order={"createdAt": "desc"},
        include={"artifacts": True, "product": True},
    )

    pages = math.ceil(total / limit) if limit > 0 else 0

    return jsonify(ApiResponse.ok({
        "data": [_serialize_build_job(b) for b in builds],
        "pagination": {
            "page": page,
            "limit": limit,
            "total": total,
            "pages": pages,
        },
    }).to_dict()), 200


@require_permissions(Permissions.BUILDS_VIEW)
def get_build(build_id: str):
    """GET /v2/builds/<id> — Build detail with artifacts and log."""
    db = get_db_client()

    build = db.buildjob.find_unique(
        where={"id": build_id},
        include={"artifacts": True, "product": True},
    )

    if not build:
        return not_found("Build job not found")

    data = _serialize_build_job(build)
    # Include build log in detail view
    data["buildLog"] = build.buildLog

    return jsonify(ApiResponse.ok(data).to_dict()), 200


@require_permissions(Permissions.BUILDS_VIEW)
def list_build_artifacts(build_id: str):
    """GET /v2/builds/<id>/artifacts — List artifacts for a build."""
    db = get_db_client()

    build = db.buildjob.find_unique(where={"id": build_id})
    if not build:
        return not_found("Build job not found")

    where = {"buildJobId": build_id}

    # Optional metadata filters
    role = request.args.get("role")
    if role:
        where["role"] = role

    artifact_type = request.args.get("type")
    if artifact_type:
        where["artifactType"] = artifact_type

    processor = request.args.get("processor")
    if processor:
        where["processor"] = processor

    artifacts = db.buildartifact.find_many(
        where=where,
        order={"createdAt": "asc"},
    )

    return jsonify(ApiResponse.ok(
        [_serialize_build_artifact(a) for a in artifacts]
    ).to_dict()), 200


@require_permissions(Permissions.BUILDS_VIEW)
def get_build_log(build_id: str):
    """GET /v2/builds/<id>/log — Get build log content."""
    db = get_db_client()

    build = db.buildjob.find_unique(where={"id": build_id})
    if not build:
        return not_found("Build job not found")

    return jsonify(ApiResponse.ok({
        "buildId": build_id,
        "status": build.status,
        "log": build.buildLog or "",
    }).to_dict()), 200


@require_permissions(Permissions.BUILDS_TRIGGER)
def create_build():
    """POST /v2/builds — Trigger a manual build."""
    data, error = BuildCreateRequest.from_json(request.get_json())
    if error:
        return bad_request(error)

    db = get_db_client()

    # Resolve Product: by direct ID if provided, otherwise by name/slug/repo slug
    product_record = None
    if data.product_id:
        product_record = db.product.find_unique(where={"id": data.product_id})
    elif data.product:
        product_record = db.product.find_first(
            where={"OR": [
                {"slug": data.product},
                {"name": {"contains": data.product, "mode": "insensitive"}},
            ]},
            include={"boards": {"include": {"revisions": True}}},
        )
    product_id = product_record.id if product_record else None

    # Use board from Product's Board model if available and not explicitly provided
    board = data.board
    if not board and product_record and hasattr(product_record, "boards") and product_record.boards:
        b = product_record.boards[0]
        if hasattr(b, "revisions") and b.revisions:
            board = b.revisions[0].ckBoardsName
        else:
            board = b.ckBoardsFamily

    # Build configFlags — merge versionOverride if present
    config_flags = dict(data.config) if data.config else {"source": data.trigger_type}
    if data.version_override:
        config_flags["versionOverride"] = data.version_override

    # Manual builds skip fingerprinting and cache
    is_manual = data.trigger_type == "manual"

    if is_manual:
        fingerprint = None
    else:
        # Compute build fingerprint for cache lookup
        fingerprint = compute_build_fingerprint(
            repo_url="",
            commit_sha=data.commit_sha or "",
            board=board,
            variant=data.variant,
            config_flags=config_flags,
        )

        # Check cache — reuse existing build if same fingerprint and no version override
        cached = find_cached_build(db, fingerprint)
        if cached and not data.version_override:
            try:
                build = db.buildjob.create(
                    data={
                        "productId": product_id,
                        "board": board,
                        "target": data.target,
                        "variant": data.variant,
                        "mtibRev": data.mtib_rev,
                        "branch": data.branch,
                        "commitSha": data.commit_sha,
                        "status": "CACHED",
                        "buildFingerprint": fingerprint,
                        "reusedFromId": cached.id,
                        "versionString": cached.versionString,
                        "webhookData": Json(config_flags),
                        "configFlags": Json(config_flags),
                        "triggerType": data.trigger_type,
                        "notes": data.notes,
                    },
                    include={"artifacts": True, "product": True},
                )
                log_audit("ci.build.cached", "BuildJob", build.id, {"reusedFromId": cached.id})
                return jsonify(ApiResponse.created(_serialize_build_job(build)).to_dict()), 201
            except Exception as e:
                logger.error("Failed to create cached build job: %s", e)
                return internal_error("Failed to create build job")

    # Determine initial status
    if is_manual and data.initial_status == "SUCCESS":
        from datetime import datetime, timezone
        initial_status = "SUCCESS"
        now = datetime.now(timezone.utc)
        extra_fields = {"startedAt": now, "finishedAt": now}
    else:
        initial_status = "QUEUED"
        extra_fields = {}

    try:
        create_data = {
            "productId": product_id,
            "board": board,
            "target": data.target,
            "variant": data.variant,
            "mtibRev": data.mtib_rev,
            "branch": data.branch,
            "commitSha": data.commit_sha,
            "status": initial_status,
            "buildFingerprint": fingerprint,
            "webhookData": Json(config_flags),
            "configFlags": Json(config_flags),
            "triggerType": data.trigger_type,
            "notes": data.notes,
            **extra_fields,
        }

        build = db.buildjob.create(
            data=create_data,
            include={"artifacts": True, "product": True},
        )

        log_audit("ci.build.create", "BuildJob", build.id, {
            "product": data.product,
            "productId": product_id,
            "board": board,
            "target": data.target,
            "variant": data.variant,
            "branch": data.branch,
            "triggerType": data.trigger_type,
        })

        return jsonify(ApiResponse.created(_serialize_build_job(build)).to_dict()), 201

    except Exception as e:
        logger.error("Failed to create build job: %s", e)
        return internal_error("Failed to create build job")


@require_permissions(Permissions.BUILDS_MANAGE)
def update_build(build_id: str):
    """PATCH /v2/builds/<id> — Update build status (used by workers)."""
    db = get_db_client()

    build = db.buildjob.find_unique(where={"id": build_id})
    if not build:
        return not_found("Build job not found")

    data = request.get_json() or {}
    update_data = {}

    # Allowed fields for update
    if "status" in data:
        status = data["status"].upper()
        if status not in ("QUEUED", "BLOCKED", "CLONING", "BUILDING", "SUCCESS", "FAILED", "CANCELLED"):
            return bad_request("Invalid status")

        # Atomic claim: workers claim by setting CLONING (from QUEUED only)
        # CLONING → BUILDING is normal progression after repos are cloned
        if status == "CLONING" and build.status != "QUEUED":
            return conflict(f"Build already claimed (status={build.status})")
        if status == "BUILDING" and build.status not in ("QUEUED", "CLONING"):
            return conflict(f"Build already claimed (status={build.status})")

        update_data["status"] = status

    if "workerId" in data:
        # Store workerId in webhookData (Prisma client needs regeneration for direct field)
        webhook_data = dict(build.webhookData) if isinstance(build.webhookData, dict) else {}
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
        max_log_size = 10 * 1024 * 1024  # 10MB cap, same as stream_build_log
        if data["buildLog"] and len(data["buildLog"]) > max_log_size:
            return bad_request("buildLog exceeds 10MB limit")
        update_data["buildLog"] = data["buildLog"]

    # Support updating version bump config (for matrix fixups)
    if "versionBump" in data:
        update_data["versionBump"] = bool(data["versionBump"])

    if "baseJobId" in data:
        update_data["baseJobId"] = data["baseJobId"]

    if "configFlags" in data:
        update_data["configFlags"] = Json(data["configFlags"]) if data["configFlags"] else None

    if not update_data:
        return bad_request("No valid fields to update")

    try:
        updated = db.buildjob.update(
            where={"id": build_id},
            data=update_data,
            include={"artifacts": True, "product": True},
        )

        # Update pipeline status based on build status changes
        if updated.buildRunId:
            new_status = update_data.get("status")

            # When a build starts (claimed by worker), update pipeline from PENDING to BUILDING
            if new_status in ("CLONING", "BUILDING"):
                pipeline = db.buildrun.find_unique(where={"id": updated.buildRunId})
                if pipeline and pipeline.status == "PENDING":
                    db.buildrun.update(
                        where={"id": updated.buildRunId},
                        data={"status": "BUILDING"},
                    )
                    logger.info("Build %s claimed, pipeline %s now BUILDING",
                               build_id, updated.buildRunId)

            # When a build succeeds, unblock dependent version-bump builds
            if new_status == "SUCCESS":
                # Find builds that depend on this one (have baseJobId pointing here)
                dependent_builds = db.buildjob.find_many(
                    where={
                        "baseJobId": build_id,
                        "status": "BLOCKED",
                    }
                )
                if dependent_builds:
                    for dep in dependent_builds:
                        db.buildjob.update(
                            where={"id": dep.id},
                            data={"status": "QUEUED"},
                        )
                        logger.info("Unblocked build %s (%s) - base build %s completed",
                                   dep.id, dep.matrixLabel, build_id)

            # When a build finishes, check if pipeline is complete
            if new_status in ("SUCCESS", "FAILED", "CANCELLED"):
                from src.services.build_run_service import check_pipeline_completion
                new_pipeline_status = check_pipeline_completion(updated.buildRunId)
                if new_pipeline_status:
                    logger.info("Build %s finished, pipeline %s now %s",
                               build_id, updated.buildRunId, new_pipeline_status)

        log_audit("ci.build.update", "BuildJob", build_id, {
            "fields": list(update_data.keys()),
            "status": update_data.get("status"),
        })

        return jsonify(ApiResponse.ok(_serialize_build_job(updated)).to_dict()), 200

    except Exception as e:
        logger.error("Failed to update build job: %s", e)
        return internal_error("Failed to update build job")


@require_permissions(Permissions.BUILDS_MANAGE)
def reset_build(build_id: str):
    """POST /v2/builds/<id>/reset — Force reset a stuck build to QUEUED.

    Use this when a build is stuck in BUILDING state (e.g., worker crashed).
    Clears the build log and timestamps so the worker will pick it up fresh.
    """
    db = get_db_client()

    build = db.buildjob.find_unique(where={"id": build_id})
    if not build:
        return not_found("Build job not found")

    # Only allow reset from BUILDING or FAILED states
    if build.status not in ("CLONING", "BUILDING", "FAILED"):
        return bad_request(f"Cannot reset build in {build.status} state. Only CLONING, BUILDING or FAILED builds can be reset.")

    try:
        updated = db.buildjob.update(
            where={"id": build_id},
            data={
                "status": "QUEUED",
                "startedAt": None,
                "finishedAt": None,
                "buildLog": None,
                "errorMessage": None,
                "durationSeconds": None,
            },
            include={"artifacts": True, "product": True},
        )

        log_audit("ci.build.reset", "BuildJob", build_id, {
            "previousStatus": build.status,
            "product": build.product,
            "matrixLabel": build.matrixLabel,
        })

        logger.info("Build %s (%s) reset to QUEUED from %s",
                   build_id, build.matrixLabel, build.status)

        return jsonify(ApiResponse.ok(_serialize_build_job(updated)).to_dict()), 200

    except Exception as e:
        logger.error("Failed to reset build %s: %s", build_id, e)
        return internal_error("Failed to reset build")


@require_permissions(Permissions.BUILDS_MANAGE)
def upload_build_artifact(build_id: str):
    """POST /v2/builds/<id>/artifacts — Upload a build artifact."""
    import hashlib
    from src.services.storage.client import get_storage_client, storage_key, StoragePrefixes

    db = get_db_client()

    build = db.buildjob.find_unique(where={"id": build_id}, include={"product": True})
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

        # Generate storage key using the derived product slug
        product_slug = _derive_product_slug(build) or "unknown"
        key = storage_key(
            StoragePrefixes.FIRMWARE_BUILDS,
            f"{product_slug}/{build.id}/{file.filename}"
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

        # Extract optional metadata from form fields
        role = request.form.get("role") or None
        processor = request.form.get("processor") or None
        artifact_type = request.form.get("artifactType") or None
        content_type = request.form.get("contentType") or None

        # Create artifact record
        create_data = {
            "buildJobId": build_id,
            "name": file.filename,
            "storageKey": key,
            "sizeBytes": size_bytes,
            "checksum": checksum,
        }
        if role is not None:
            create_data["role"] = role
        if processor is not None:
            create_data["processor"] = processor
        if artifact_type is not None:
            create_data["artifactType"] = artifact_type
        if content_type is not None:
            create_data["contentType"] = content_type

        artifact = db.buildartifact.create(data=create_data)

        log_audit("ci.artifact.upload", "BuildArtifact", artifact.id, {
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


@require_permissions(Permissions.BUILDS_VIEW)
def download_build_artifacts(build_id: str):
    """GET /v2/builds/<id>/artifacts/download — Download all artifacts as ZIP.

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

    artifacts = db.buildartifact.find_many(
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
                "Content-Disposition": f'attachment; filename="{_sanitize_filename(zip_filename)}"',
                "Content-Length": str(len(zip_buffer.getvalue())),
            },
        )

    except Exception as e:
        logger.error("Failed to create ZIP for build %s: %s", build_id, e)
        return internal_error("Failed to create artifact ZIP")


@require_permissions(Permissions.BUILDS_VIEW)
def download_single_artifact(build_id: str, artifact_name: str):
    """GET /v2/builds/<id>/artifacts/<name> — Download a single artifact.

    Streams the artifact file directly from MinIO storage.
    """
    from flask import Response
    from src.services.storage.client import get_storage_client

    db = get_db_client()

    build = db.buildjob.find_unique(where={"id": build_id})
    if not build:
        return not_found("Build job not found")

    artifact = db.buildartifact.find_first(
        where={
            "buildJobId": build_id,
            "name": artifact_name,
        }
    )

    if not artifact:
        return not_found("Artifact not found")

    try:
        storage = get_storage_client()
        response = storage.get_object("concord", artifact.storageKey)
        content = response.read()
        response.close()
        response.release_conn()

        # Determine content type
        content_type = "application/octet-stream"
        if artifact_name.endswith(".hex"):
            content_type = "application/octet-stream"
        elif artifact_name.endswith(".json"):
            content_type = "application/json"
        elif artifact_name.endswith(".cfw"):
            content_type = "application/octet-stream"

        return Response(
            content,
            mimetype=content_type,
            headers={
                "Content-Disposition": f'attachment; filename="{_sanitize_filename(artifact_name)}"',
                "Content-Length": str(len(content)),
            },
        )

    except Exception as e:
        logger.error("Failed to download artifact %s: %s", artifact_name, e)
        return internal_error("Failed to download artifact")


@require_permissions(Permissions.BUILDS_MANAGE)
def stream_build_log(build_id: str):
    """POST /v2/builds/<id>/log — Receive and broadcast log chunks from build worker.

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
            "pipelineId": build.buildRunId,
            "chunk": chunk,
        })

        return jsonify(ApiResponse.ok({"received": len(chunk)}).to_dict()), 200

    except Exception as e:
        logger.error("Failed to stream build log: %s", e)
        return internal_error("Failed to stream build log")
