"""Firmware endpoints — FirmwareSet CRUD, build uploads, artifact downloads.

A FirmwareSet groups all per-target builds from one build run.
Each FirmwareBuild within a set targets one AppID (one processor).
"""

import hashlib
import logging
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

from werkzeug.utils import secure_filename as _secure_filename

from .shared import ALLOWED_FIRMWARE_EXTENSIONS, MIME_TYPES, presigned_url

logger = logging.getLogger(__name__)

from .shared import serialize_target as _serialize_target

_SET_INCLUDE = {
    "builds": {"include": {"target": True}},
    "boardRevision": True,
}


def _serialize_build(b: Any) -> dict:
    """Serialize a FirmwareBuild DB record to an API response dict."""
    data = {
        "id": b.id,
        "firmwareSetId": b.firmwareSetId,
        "targetId": b.targetId,
        "versionString": b.versionString,
        "hexStorageKey": b.hexStorageKey,
        "cfwStorageKey": b.cfwStorageKey,
        "filename": b.filename,
        "sizeBytes": str(b.sizeBytes) if b.sizeBytes is not None else None,
        "checksum": b.checksum,
        "contentType": b.contentType,
        "notes": b.notes,
        "createdAt": b.createdAt.isoformat(),
    }
    if hasattr(b, "target") and b.target:
        data["target"] = _serialize_target(b.target)
    else:
        data["target"] = None
    return data


def _serialize_firmware_set(s: Any) -> dict:
    """Serialize a FirmwareSet DB record to an API response dict."""
    data = {
        "id": s.id,
        "productId": s.productId,
        "boardRevisionId": s.boardRevisionId,
        "version": s.version,
        "releaseTrack": s.releaseTrack,
        "isManufacturing": s.isManufacturing,
        "isDebug": s.isDebug,
        "source": s.source,
        "modemVersion": s.modemVersion,
        "status": s.status,
        "notes": s.notes,
        "createdAt": s.createdAt.isoformat(),
        "updatedAt": s.updatedAt.isoformat(),
    }
    if hasattr(s, "boardRevision") and s.boardRevision:
        data["boardRevision"] = {
            "id": s.boardRevision.id,
            "version": s.boardRevision.version,
            "ckBoardsName": s.boardRevision.ckBoardsName,
        }
    else:
        data["boardRevision"] = None
    if hasattr(s, "builds") and s.builds:
        data["builds"] = [_serialize_build(b) for b in s.builds]
    else:
        data["builds"] = []
    return data


# ── FirmwareSet CRUD ────────────────────────────────────────


@require_permissions(Permissions.PRODUCTS_VIEW)
def list_firmware_sets(product_id: str):
    """GET /v2/products/<id>/firmware — list firmware sets for a product."""
    db = get_db_client()
    product = db.product.find_unique(where={"id": product_id})
    if not product:
        return not_found("Product not found")

    where: dict = {"productId": product_id}
    revision_id = request.args.get("boardRevisionId")
    if revision_id:
        where["boardRevisionId"] = revision_id
    track = request.args.get("releaseTrack")
    if track:
        where["releaseTrack"] = track
    is_mfg = request.args.get("isManufacturing")
    if is_mfg is not None:
        where["isManufacturing"] = is_mfg.lower() == "true"

    page = max(1, request.args.get("page", 1, type=int))
    limit = min(max(1, request.args.get("limit", 50, type=int)), 100)
    skip = (page - 1) * limit

    total = db.firmwareset.count(where=where)
    sets = db.firmwareset.find_many(
        where=where,
        skip=skip,
        take=limit,
        order={"createdAt": "desc"},
        include=_SET_INCLUDE,
    )
    return jsonify(ApiResponse.ok({
        "data": [_serialize_firmware_set(s) for s in sets],
        "pagination": {
            "page": page, "limit": limit, "total": total,
            "pages": (total + limit - 1) // limit if limit > 0 else 0,
        },
    }).to_dict()), 200


@require_permissions(Permissions.PRODUCTS_VIEW)
def get_firmware_set(product_id: str, set_id: str):
    """GET /v2/products/<id>/firmware/<set_id>"""
    db = get_db_client()
    fw_set = db.firmwareset.find_first(
        where={"id": set_id, "productId": product_id},
        include=_SET_INCLUDE,
    )
    if not fw_set:
        return not_found("Firmware set not found")
    return jsonify(ApiResponse.ok(_serialize_firmware_set(fw_set)).to_dict()), 200


@require_permissions(Permissions.PRODUCTS_MANAGE)
def create_firmware_set(product_id: str):
    """POST /v2/products/<id>/firmware — create a firmware set (metadata only)."""
    db = get_db_client()
    product = db.product.find_unique(where={"id": product_id})
    if not product:
        return not_found("Product not found")

    data = request.get_json()
    if not data:
        return bad_request("Request body required")

    version = (data.get("version") or "").strip()
    if not version:
        return bad_request("version is required")

    release_track = (data.get("releaseTrack") or "bench").strip()
    if release_track not in ("bench", "engineering", "production"):
        return bad_request("releaseTrack must be bench, engineering, or production")

    board_revision_id = data.get("boardRevisionId")
    if board_revision_id:
        rev = db.boardrevision.find_first(
            where={"id": board_revision_id, "board": {"productId": product_id}},
        )
        if not rev:
            return bad_request("Board revision not found for this product")

    fw_set = db.firmwareset.create(
        data={
            "productId": product_id,
            "boardRevisionId": board_revision_id,
            "version": version,
            "releaseTrack": release_track,
            "isManufacturing": data.get("isManufacturing", False),
            "isDebug": data.get("isDebug", False),
            "source": data.get("source", "upload"),
            "modemVersion": data.get("modemVersion"),
            "notes": data.get("notes"),
        },
        include=_SET_INCLUDE,
    )

    log_audit("firmwareSet.create", "FirmwareSet", fw_set.id, {
        "productName": product.name, "version": version, "releaseTrack": release_track,
    })
    return jsonify(ApiResponse.ok(_serialize_firmware_set(fw_set)).to_dict()), 201


@require_permissions(Permissions.PRODUCTS_MANAGE)
def update_firmware_set(product_id: str, set_id: str):
    """PUT /v2/products/<id>/firmware/<set_id> — update firmware set metadata."""
    db = get_db_client()
    fw_set = db.firmwareset.find_first(
        where={"id": set_id, "productId": product_id},
    )
    if not fw_set:
        return not_found("Firmware set not found")

    data = request.get_json()
    if not data:
        return bad_request("Request body must contain JSON data")

    update_data = {}
    if "status" in data:
        status = data["status"].strip()
        if status not in ("active", "deprecated", "recalled"):
            return bad_request("Invalid status. Must be: active, deprecated, recalled")
        update_data["status"] = status
    if "notes" in data:
        update_data["notes"] = (data["notes"] or "").strip() or None

    if not update_data:
        return bad_request("No fields to update")

    updated = db.firmwareset.update(
        where={"id": set_id},
        data=update_data,
        include={"builds": True, "boardRevision": True},
    )
    log_audit("firmwareSet.update", "FirmwareSet", set_id, {
        "fields": list(update_data.keys()),
    })
    return jsonify(ApiResponse.ok(_serialize_firmware_set(updated)).to_dict()), 200


@require_permissions(Permissions.PRODUCTS_MANAGE)
def delete_firmware_set(product_id: str, set_id: str):
    """DELETE /v2/products/<id>/firmware/<set_id> — delete set + all builds."""
    db = get_db_client()
    fw_set = db.firmwareset.find_first(
        where={"id": set_id, "productId": product_id},
        include={"builds": True},
    )
    if not fw_set:
        return not_found("Firmware set not found")

    # Clean up storage
    try:
        client = get_storage_client()
        bucket = get_bucket_name()
        for build in (fw_set.builds or []):
            for key in [build.hexStorageKey, build.hexEncStorageKey, build.cfwStorageKey]:
                if key:
                    try:
                        client.remove_object(bucket, key)
                    except Exception:
                        pass
        if fw_set.modemStorageKey:
            try:
                client.remove_object(bucket, fw_set.modemStorageKey)
            except Exception:
                pass
    except Exception as e:
        logger.warning("Failed to clean storage for firmware set %s: %s", set_id, e)

    db.firmwareset.delete(where={"id": set_id})
    log_audit("firmwareSet.delete", "FirmwareSet", set_id, {
        "version": fw_set.version, "buildCount": len(fw_set.builds or []),
    })
    return jsonify(ApiResponse.ok({"deleted": True}).to_dict()), 200


# ── Build Upload (into a FirmwareSet) ──────────────────────


@require_permissions(Permissions.PRODUCTS_MANAGE)
def upload_firmware_build(product_id: str, set_id: str):
    """POST /v2/products/<id>/firmware/<set_id>/builds — upload a build artifact."""
    db = get_db_client()
    fw_set = db.firmwareset.find_first(
        where={"id": set_id, "productId": product_id},
    )
    if not fw_set:
        return not_found("Firmware set not found")

    if "file" not in request.files:
        return bad_request("No file provided")

    file = request.files["file"]
    if not file.filename:
        return bad_request("No file selected")

    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in ALLOWED_FIRMWARE_EXTENSIONS:
        return bad_request(f"Invalid file type. Allowed: {', '.join(ALLOWED_FIRMWARE_EXTENSIONS)}")

    target_id = request.form.get("targetId", "").strip() or None
    version_string = request.form.get("versionString", "").strip() or None
    artifact_type = request.form.get("artifactType", "hex").strip()  # hex, cfw, hexEncrypted
    notes = request.form.get("notes", "").strip() or None

    # Validate target if provided
    if target_id:
        target = db.producttarget.find_first(
            where={"id": target_id, "boardRevision": {"board": {"productId": product_id}}},
        )
        if not target:
            return bad_request("Target not found for this product")

    # Read + hash
    file_data = file.read()
    size_bytes = len(file_data)
    checksum = hashlib.sha256(file_data).hexdigest()
    content_type = MIME_TYPES.get(ext, file.content_type or "application/octet-stream")

    try:
        client = get_storage_client()
        bucket = get_bucket_name()
        safe_filename = _secure_filename(file.filename)
        object_key = storage_key(
            StoragePrefixes.FIRMWARE_BUILDS,
            f"{product_id}/{set_id}/{safe_filename}"
        )

        client.put_object(bucket, object_key, BytesIO(file_data), length=size_bytes, content_type=content_type)

        # Determine which storage key field to set
        storage_fields = {}
        if artifact_type == "cfw":
            storage_fields["cfwStorageKey"] = object_key
        elif artifact_type == "hexEncrypted":
            storage_fields["hexEncStorageKey"] = object_key
        else:
            storage_fields["hexStorageKey"] = object_key

        build = db.firmwarebuild.create(
            data={
                "firmwareSetId": set_id,
                "targetId": target_id,
                "versionString": version_string,
                "filename": file.filename,
                "sizeBytes": size_bytes,
                "checksum": checksum,
                "contentType": content_type,
                "notes": notes,
                **storage_fields,
            },
            include={"target": True},
        )

        log_audit("firmwareBuild.upload", "FirmwareBuild", build.id, {
            "firmwareSetId": set_id, "filename": file.filename,
            "artifactType": artifact_type, "sizeBytes": size_bytes,
        })
        return jsonify(ApiResponse.ok(_serialize_build(build)).to_dict()), 201
    except Exception as e:
        logger.error("Failed to upload firmware build: %s", e)
        return internal_error("Failed to upload firmware build")


# ── Download ────────────────────────────────────────────────


@require_permissions(Permissions.PRODUCTS_VIEW)
def download_firmware_build(build_id: str):
    """GET /v2/firmware/builds/<build_id>/download"""
    db = get_db_client()
    build = db.firmwarebuild.find_unique(where={"id": build_id})
    if not build:
        return not_found("Firmware build not found")

    # Try hex first, then cfw, then encrypted hex
    for key_attr in ["hexStorageKey", "cfwStorageKey", "hexEncStorageKey"]:
        key = getattr(build, key_attr, None)
        if key:
            url = presigned_url(key, download_filename=build.filename)
            if url:
                return jsonify(ApiResponse.ok({"url": url, "filename": build.filename}).to_dict()), 200

    return not_found("No downloadable artifact found")
