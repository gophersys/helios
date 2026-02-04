from datetime import datetime, timezone

from flask import jsonify, request

from src.lib.audit import log_audit
from src.lib.decorators import require_permissions
from src.lib.errors import bad_request, conflict, not_found
from src.lib.permissions import Permissions
from src.lib.types import ApiResponse
from src.services.database.prisma import get_db_client
from src.services.storage.client import get_codebases_bucket_name, get_storage_client

from .types import ReleaseCreateRequest, ReleaseUpdateRequest


def _serialize_release(r, include_artifacts=False) -> dict:
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
        data["artifactCount"] = len(r.artifacts)
        if include_artifacts:
            data["artifacts"] = [_serialize_artifact(a) for a in r.artifacts]
    return data


def _serialize_artifact(a) -> dict:
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


# ── Releases CRUD ─────────────────────────────────────────


@require_permissions(Permissions.ADMIN_CODEBASES_MANAGE)
def create_release(codebase_id: str):
    db = get_db_client()
    codebase = db.codebase.find_unique(where={"id": codebase_id})
    if not codebase:
        return not_found("Codebase not found")

    data, error = ReleaseCreateRequest.from_json(request.get_json())
    if error:
        return bad_request(error)

    existing = db.release.find_first(
        where={"codebaseId": codebase_id, "version": data.version}
    )
    if existing:
        return conflict(f"Release '{data.version}' already exists for this codebase")

    create_data = {
        "codebaseId": codebase_id,
        "version": data.version,
        "status": data.status,
        "releaseNotes": data.releaseNotes,
        "tagName": data.tagName,
    }
    if data.status == "RELEASED":
        create_data["releasedAt"] = datetime.now(timezone.utc)

    release = db.release.create(
        data=create_data,
        include={"artifacts": True},
    )
    log_audit("release.create", "Release", release.id, {"codebaseId": codebase_id, "version": data.version, "status": data.status})
    return jsonify(ApiResponse.ok(_serialize_release(release)).to_dict()), 201


@require_permissions(Permissions.ADMIN_CODEBASES_MANAGE)
def update_release(codebase_id: str, release_id: str):
    db = get_db_client()
    release = db.release.find_first(
        where={"id": release_id, "codebaseId": codebase_id}
    )
    if not release:
        return not_found("Release not found")

    data, error = ReleaseUpdateRequest.from_json(request.get_json())
    if error:
        return bad_request(error)

    if data.version and data.version != release.version:
        dup = db.release.find_first(
            where={"codebaseId": codebase_id, "version": data.version}
        )
        if dup:
            return conflict(f"Release '{data.version}' already exists for this codebase")

    update_data = data.to_update_data()

    # Auto-set releasedAt when transitioning to RELEASED
    if data.status == "RELEASED" and release.status != "RELEASED":
        update_data["releasedAt"] = datetime.now(timezone.utc)

    updated = db.release.update(
        where={"id": release_id},
        data=update_data,
        include={"artifacts": True},
    )
    log_audit("release.update", "Release", release_id, {"version": release.version, "before": {"status": release.status}, "after": update_data})
    return jsonify(ApiResponse.ok(_serialize_release(updated)).to_dict()), 200


@require_permissions(Permissions.ADMIN_CODEBASES_MANAGE)
def delete_release(codebase_id: str, release_id: str):
    db = get_db_client()
    release = db.release.find_first(
        where={"id": release_id, "codebaseId": codebase_id},
        include={"artifacts": True},
    )
    if not release:
        return not_found("Release not found")

    # Clean up MinIO objects for UPLOAD artifacts
    try:
        client = get_storage_client()
        bucket = get_codebases_bucket_name()
        for artifact in release.artifacts:
            if artifact.type == "UPLOAD" and artifact.storageKey:
                try:
                    client.remove_object(bucket, artifact.storageKey)
                except Exception:
                    pass
    except Exception:
        pass

    db.release.delete(where={"id": release_id})
    log_audit("release.delete", "Release", release_id, {"version": release.version, "artifactCount": len(release.artifacts)})
    return jsonify(ApiResponse.ok({"deleted": True}).to_dict()), 200
