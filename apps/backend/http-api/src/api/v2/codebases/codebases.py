import logging
import math
from io import BytesIO
from typing import Any

from flask import jsonify, request

from src.lib.audit import log_audit
from src.lib.decorators import require_permissions
from src.lib.errors import bad_request, conflict, internal_error, not_found
from src.lib.permissions import Permissions
from src.lib.types import ApiResponse
from src.services.database.prisma import get_db_client
from src.services.storage.client import get_bucket_name, get_storage_client, StoragePrefixes, storage_key

from .shared import ALLOWED_IMAGE_EXTENSIONS, MIME_TYPES, presigned_url
from .types import CodebaseCreateRequest, CodebaseUpdateRequest

logger = logging.getLogger(__name__)


def _serialize_codebase(c: Any, include_releases: bool = False) -> dict:
    data = {
        "id": c.id,
        "name": c.name,
        "description": c.description,
        "repoUrl": c.repoUrl,
        "defaultBranch": c.defaultBranch,
        "imageKey": c.imageKey,
        "imageUrl": presigned_url(c.imageKey),
        "createdAt": c.createdAt.isoformat(),
        "updatedAt": c.updatedAt.isoformat(),
    }
    if hasattr(c, "releases") and c.releases is not None:
        data["releaseCount"] = len(c.releases)
        # Find latest RELEASED release
        released = [r for r in c.releases if r.status == "RELEASED"]
        if released:
            latest = max(released, key=lambda r: r.releasedAt or r.createdAt)
            data["latestRelease"] = _serialize_release(latest)
        else:
            data["latestRelease"] = None
        if include_releases:
            data["releases"] = [
                _serialize_release(r, include_artifacts=True)
                for r in sorted(
                    c.releases,
                    key=lambda r: r.releasedAt or r.createdAt,
                    reverse=True,
                )
            ]
    return data


def _serialize_artifact(a: Any) -> dict:
    return {
        "id": a.id,
        "releaseId": a.releaseId,
        "name": a.name,
        "filename": a.filename,
        "type": a.type,
        "storageKey": a.storageKey,
        "externalUrl": a.externalUrl,
        "sizeBytes": str(a.sizeBytes) if a.sizeBytes is not None else None,
        "checksum": a.checksum,
        "contentType": a.contentType,
        "createdAt": a.createdAt.isoformat(),
        "updatedAt": a.updatedAt.isoformat(),
    }


def _serialize_release(r: Any, include_artifact_count: bool = False, include_artifacts: bool = False) -> dict:
    data = {
        "id": r.id,
        "codebaseId": r.codebaseId,
        "version": r.version,
        "status": r.status,
        "releaseNotes": r.releaseNotes,
        "tagName": r.tagName,
        "releasedAt": r.releasedAt.isoformat() if r.releasedAt else None,
        "createdAt": r.createdAt.isoformat(),
        "updatedAt": r.updatedAt.isoformat(),
    }
    if hasattr(r, "artifacts") and r.artifacts is not None:
        if include_artifact_count or include_artifacts:
            data["artifactCount"] = len(r.artifacts)
        if include_artifacts:
            data["artifacts"] = [_serialize_artifact(a) for a in r.artifacts]
    return data


# ── Codebases CRUD ─────────────────────────────────────────


@require_permissions(Permissions.BUILDS_VIEW)
def list_codebases():
    db = get_db_client()

    page = max(1, request.args.get("page", 1, type=int))
    limit = min(max(1, request.args.get("limit", 50, type=int)), 100)
    skip = (page - 1) * limit

    total = db.codebase.count()
    codebases = db.codebase.find_many(
        skip=skip,
        take=limit,
        order={"name": "asc"},
        include={"releases": {"include": {"artifacts": True}}},
    )
    return jsonify(ApiResponse.ok({
        "data": [_serialize_codebase(c) for c in codebases],
        "pagination": {
            "page": page,
            "limit": limit,
            "total": total,
            "pages": math.ceil(total / limit) if limit > 0 else 0,
        },
    }).to_dict()), 200


@require_permissions(Permissions.BUILDS_MANAGE)
def create_codebase():
    data, error = CodebaseCreateRequest.from_json(request.get_json())
    if error:
        return bad_request(error)

    db = get_db_client()

    existing = db.codebase.find_unique(where={"name": data.name})
    if existing:
        return conflict("Codebase with this name already exists")

    codebase = db.codebase.create(
        data={
            "name": data.name,
            "description": data.description,
            "repoUrl": data.repoUrl,
            "defaultBranch": data.defaultBranch,
        },
        include={"releases": True},
    )
    log_audit("codebase.create", "Codebase", codebase.id, {"name": data.name})
    return jsonify(ApiResponse.ok(_serialize_codebase(codebase)).to_dict()), 201


@require_permissions(Permissions.BUILDS_VIEW)
def get_codebase(codebase_id: str):
    db = get_db_client()
    codebase = db.codebase.find_unique(
        where={"id": codebase_id},
        include={"releases": {"include": {"artifacts": True}}},
    )
    if not codebase:
        return not_found("Codebase not found")
    return jsonify(ApiResponse.ok(_serialize_codebase(codebase, include_releases=True)).to_dict()), 200


@require_permissions(Permissions.BUILDS_MANAGE)
def update_codebase(codebase_id: str):
    data, error = CodebaseUpdateRequest.from_json(request.get_json())
    if error:
        return bad_request(error)

    db = get_db_client()
    existing = db.codebase.find_unique(where={"id": codebase_id})
    if not existing:
        return not_found("Codebase not found")

    if data.name and data.name != existing.name:
        dup = db.codebase.find_unique(where={"name": data.name})
        if dup:
            return conflict("Codebase with this name already exists")

    codebase = db.codebase.update(
        where={"id": codebase_id},
        data=data.to_update_data(),
        include={"releases": {"include": {"artifacts": True}}},
    )
    log_audit("codebase.update", "Codebase", codebase_id, {"name": existing.name, "changes": data.to_update_data()})
    return jsonify(ApiResponse.ok(_serialize_codebase(codebase)).to_dict()), 200


@require_permissions(Permissions.BUILDS_MANAGE)
def delete_codebase(codebase_id: str):
    db = get_db_client()
    existing = db.codebase.find_unique(
        where={"id": codebase_id},
        include={"releases": {"include": {"artifacts": True}}},
    )
    if not existing:
        return not_found("Codebase not found")

    # Clean up MinIO objects for all UPLOAD artifacts
    try:
        client = get_storage_client()
        bucket = get_bucket_name()
        for release in existing.releases:
            for artifact in release.artifacts:
                if artifact.type == "UPLOAD" and artifact.storageKey:
                    try:
                        client.remove_object(bucket, artifact.storageKey)
                    except Exception as e:
                        logger.warning("Failed to remove artifact object %s: %s", artifact.storageKey, e)
        # Remove codebase image
        if existing.imageKey:
            try:
                client.remove_object(bucket, existing.imageKey)
            except Exception as e:
                logger.warning("Failed to remove codebase image %s: %s", existing.imageKey, e)
    except Exception as e:
        logger.warning("Failed to clean up storage objects for codebase %s: %s", codebase_id, e)

    db.codebase.delete(where={"id": codebase_id})
    log_audit("codebase.delete", "Codebase", codebase_id, {"name": existing.name})
    return jsonify(ApiResponse.ok({"deleted": True}).to_dict()), 200


# ── Image upload ─────────────────────────────────────────────


@require_permissions(Permissions.BUILDS_MANAGE)
def upload_codebase_image(codebase_id: str):
    db = get_db_client()
    codebase = db.codebase.find_unique(where={"id": codebase_id})
    if not codebase:
        return not_found("Codebase not found")

    if "file" not in request.files:
        return bad_request("No file provided")

    file = request.files["file"]
    if not file.filename:
        return bad_request("No file selected")

    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        return bad_request(f"Invalid file type. Allowed: {', '.join(ALLOWED_IMAGE_EXTENSIONS)}")

    object_key = storage_key(StoragePrefixes.CODEBASES, f"{codebase_id}/logo.{ext}")

    try:
        client = get_storage_client()
        bucket = get_bucket_name()

        if codebase.imageKey and codebase.imageKey != object_key:
            try:
                client.remove_object(bucket, codebase.imageKey)
            except Exception as e:
                logger.warning("Failed to remove old codebase image %s: %s", codebase.imageKey, e)

        file_data = file.read()
        client.put_object(
            bucket,
            object_key,
            BytesIO(file_data),
            length=len(file_data),
            content_type=MIME_TYPES.get(ext, "application/octet-stream"),
        )

        updated = db.codebase.update(
            where={"id": codebase_id},
            data={"imageKey": object_key},
            include={"releases": True},
        )
        log_audit("codebase.imageUpload", "Codebase", codebase_id, {"name": codebase.name})
        return jsonify(ApiResponse.ok(_serialize_codebase(updated)).to_dict()), 200
    except Exception as e:
        logger.error("Failed to upload codebase image: %s", e)
        return internal_error("Failed to upload image")
