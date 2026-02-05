import hashlib
import logging
import math
from io import BytesIO

from flask import jsonify, request

from src.lib.audit import log_audit
from src.lib.decorators import require_permissions
from src.lib.errors import bad_request, internal_error, not_found
from src.lib.permissions import Permissions
from src.lib.types import ApiResponse
from src.services.database.prisma import get_db_client
from src.services.storage.client import get_bucket_name, get_storage_client, StoragePrefixes, storage_key

logger = logging.getLogger(__name__)

from .shared import ALLOWED_ARTIFACT_EXTENSIONS, presigned_url
from .types import ArtifactCreateRequest

from typing import Any


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


# ── Artifacts CRUD ─────────────────────────────────────────


@require_permissions(Permissions.ADMIN_CODEBASES_VIEW)
def list_artifacts(codebase_id: str, release_id: str):
    db = get_db_client()
    release = db.release.find_first(
        where={"id": release_id, "codebaseId": codebase_id}
    )
    if not release:
        return not_found("Release not found")

    page = max(1, request.args.get("page", 1, type=int))
    limit = min(max(1, request.args.get("limit", 50, type=int)), 100)
    skip = (page - 1) * limit

    total = db.releaseartifact.count(where={"releaseId": release_id})
    artifacts = db.releaseartifact.find_many(
        where={"releaseId": release_id},
        skip=skip,
        take=limit,
        order={"createdAt": "asc"},
    )
    return jsonify(ApiResponse.ok({
        "data": [_serialize_artifact(a) for a in artifacts],
        "pagination": {
            "page": page,
            "limit": limit,
            "total": total,
            "pages": math.ceil(total / limit) if limit > 0 else 0,
        },
    }).to_dict()), 200


@require_permissions(Permissions.ADMIN_CODEBASES_MANAGE)
def create_artifact(codebase_id: str, release_id: str):
    db = get_db_client()
    release = db.release.find_first(
        where={"id": release_id, "codebaseId": codebase_id}
    )
    if not release:
        return not_found("Release not found")

    data, error = ArtifactCreateRequest.from_json(request.get_json())
    if error:
        return bad_request(error)

    artifact = db.releaseartifact.create(
        data={
            "releaseId": release_id,
            "name": data.name,
            "type": "EXTERNAL",
            "externalUrl": data.externalUrl,
        }
    )
    log_audit("artifact.create", "ReleaseArtifact", artifact.id, {"name": data.name, "type": "EXTERNAL", "releaseId": release_id})
    return jsonify(ApiResponse.ok(_serialize_artifact(artifact)).to_dict()), 201


@require_permissions(Permissions.ADMIN_CODEBASES_MANAGE)
def upload_artifact(codebase_id: str, release_id: str):
    db = get_db_client()
    release = db.release.find_first(
        where={"id": release_id, "codebaseId": codebase_id}
    )
    if not release:
        return not_found("Release not found")

    if "file" not in request.files:
        return bad_request("No file provided")

    file = request.files["file"]
    if not file.filename:
        return bad_request("No file selected")

    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in ALLOWED_ARTIFACT_EXTENSIONS:
        return bad_request(f"Invalid file type. Allowed: {', '.join(sorted(ALLOWED_ARTIFACT_EXTENSIONS))}")

    name = request.form.get("name", "").strip() or file.filename
    filename = file.filename

    # Determine content type
    content_type = file.content_type or "application/octet-stream"

    # Read file data and compute checksum
    file_data = file.read()
    size_bytes = len(file_data)
    checksum = hashlib.sha256(file_data).hexdigest()

    object_storage_key = storage_key(StoragePrefixes.CODEBASES, f"{codebase_id}/releases/{release_id}/{filename}")

    try:
        client = get_storage_client()
        bucket = get_bucket_name()

        client.put_object(
            bucket,
            object_storage_key,
            BytesIO(file_data),
            length=size_bytes,
            content_type=content_type,
        )

        artifact = db.releaseartifact.create(
            data={
                "releaseId": release_id,
                "name": name,
                "filename": filename,
                "type": "UPLOAD",
                "storageKey": object_storage_key,
                "sizeBytes": size_bytes,
                "checksum": checksum,
                "contentType": content_type,
            }
        )
        log_audit("artifact.upload", "ReleaseArtifact", artifact.id, {"name": name, "filename": filename, "sizeBytes": size_bytes, "releaseId": release_id})
        return jsonify(ApiResponse.ok(_serialize_artifact(artifact)).to_dict()), 201
    except Exception as e:
        logger.error("Failed to upload artifact: %s", e)
        return internal_error("Failed to upload artifact")


@require_permissions(Permissions.ADMIN_CODEBASES_MANAGE)
def delete_artifact(codebase_id: str, release_id: str, artifact_id: str):
    db = get_db_client()
    artifact = db.releaseartifact.find_first(
        where={"id": artifact_id, "releaseId": release_id}
    )
    if not artifact:
        return not_found("Artifact not found")

    # Verify the release belongs to the codebase
    release = db.release.find_first(
        where={"id": release_id, "codebaseId": codebase_id}
    )
    if not release:
        return not_found("Release not found")

    # Remove from MinIO if it's an upload
    if artifact.type == "UPLOAD" and artifact.storageKey:
        try:
            client = get_storage_client()
            bucket = get_bucket_name()
            client.remove_object(bucket, artifact.storageKey)
        except Exception as e:
            logger.warning("Failed to remove artifact object %s: %s", artifact.storageKey, e)

    db.releaseartifact.delete(where={"id": artifact_id})
    log_audit("artifact.delete", "ReleaseArtifact", artifact_id, {"name": artifact.name, "type": artifact.type})
    return jsonify(ApiResponse.ok({"deleted": True}).to_dict()), 200


# ── Download ─────────────────────────────────────────────


@require_permissions(Permissions.ADMIN_CODEBASES_VIEW)
def download_artifact(artifact_id: str):
    db = get_db_client()
    artifact = db.releaseartifact.find_unique(where={"id": artifact_id})
    if not artifact:
        return not_found("Artifact not found")

    if artifact.type == "EXTERNAL" and artifact.externalUrl:
        return jsonify(ApiResponse.ok({"url": artifact.externalUrl}).to_dict()), 200

    if artifact.type == "UPLOAD" and artifact.storageKey:
        url = presigned_url(artifact.storageKey, download_filename=artifact.filename)
        if url:
            return jsonify(ApiResponse.ok({"url": url}).to_dict()), 200
        return not_found("Artifact file not found in storage")

    return not_found("Artifact has no download source")
