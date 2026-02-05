import hashlib
import logging
from io import BytesIO

from flask import jsonify, request

from src.lib.audit import log_audit
from src.lib.decorators import require_permissions
from src.lib.errors import bad_request, conflict, internal_error, not_found
from src.lib.permissions import Permissions
from src.lib.types import ApiResponse
from src.services.database.prisma import get_db_client
from src.services.storage.client import get_bucket_name, get_storage_client, StoragePrefixes, storage_key

logger = logging.getLogger(__name__)

from .shared import ALLOWED_FIRMWARE_EXTENSIONS, MIME_TYPES, presigned_url
from .types import FirmwareBuildUpdateRequest

from typing import Any


def _serialize_build(b: Any) -> dict:
    data = {
        "id": b.id,
        "productId": b.productId,
        "applicationId": b.applicationId,
        "boardRevisionId": b.boardRevisionId,
        "version": b.version,
        "majorVersion": b.majorVersion,
        "minorVersion": b.minorVersion,
        "buildNumber": b.buildNumber,
        "bootloaderId": b.bootloaderId,
        "isManufacturing": b.isManufacturing,
        "storageKey": b.storageKey,
        "filename": b.filename,
        "sizeBytes": str(b.sizeBytes) if b.sizeBytes is not None else None,
        "checksum": b.checksum,
        "contentType": b.contentType,
        "status": b.status,
        "notes": b.notes,
        "createdAt": b.createdAt.isoformat(),
        "updatedAt": b.updatedAt.isoformat(),
    }
    if hasattr(b, "application") and b.application is not None:
        data["applicationName"] = b.application.name
        data["applicationAppId"] = b.application.applicationId
    if hasattr(b, "boardRevision") and b.boardRevision is not None:
        data["boardRevisionVersion"] = b.boardRevision.version
    return data


# ── Firmware Builds ─────────────────────────────────────────


@require_permissions(Permissions.ADMIN_PRODUCTS_VIEW)
def list_firmware_builds(product_id: str):
    db = get_db_client()
    product = db.product.find_unique(where={"id": product_id})
    if not product:
        return not_found("Product not found")

    # Optional query filters
    where: dict = {"productId": product_id}
    app_id = request.args.get("applicationId")
    if app_id:
        where["applicationId"] = app_id
    status = request.args.get("status")
    if status:
        where["status"] = status
    is_mfg = request.args.get("isManufacturing")
    if is_mfg is not None:
        where["isManufacturing"] = is_mfg.lower() == "true"

    page = max(1, request.args.get("page", 1, type=int))
    limit = min(max(1, request.args.get("limit", 50, type=int)), 100)
    skip = (page - 1) * limit

    total = db.firmwarebuild.count(where=where)
    builds = db.firmwarebuild.find_many(
        where=where,
        skip=skip,
        take=limit,
        order={"createdAt": "desc"},
        include={
            "application": True,
            "boardRevision": True,
        },
    )
    return jsonify(ApiResponse.ok({
        "data": [_serialize_build(b) for b in builds],
        "pagination": {
            "page": page,
            "limit": limit,
            "total": total,
            "pages": (total + limit - 1) // limit if limit > 0 else 0,
        },
    }).to_dict()), 200


@require_permissions(Permissions.ADMIN_PRODUCTS_MANAGE)
def upload_firmware_build(product_id: str):
    db = get_db_client()
    product = db.product.find_unique(where={"id": product_id})
    if not product:
        return not_found("Product not found")

    if "file" not in request.files:
        return bad_request("No file provided")

    file = request.files["file"]
    if not file.filename:
        return bad_request("No file selected")

    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in ALLOWED_FIRMWARE_EXTENSIONS:
        return bad_request(f"Invalid file type. Allowed: {', '.join(ALLOWED_FIRMWARE_EXTENSIONS)}")

    # Read form metadata
    application_id = request.form.get("applicationId", "").strip()
    if not application_id:
        return bad_request("Application ID is required")

    # Verify application exists and belongs to product
    fw_app = db.firmwareapplication.find_first(
        where={"id": application_id, "productId": product_id}
    )
    if not fw_app:
        return not_found("Firmware application not found for this product")

    version = request.form.get("version", "").strip()
    if not version:
        return bad_request("Version is required")

    try:
        major = int(request.form.get("majorVersion", "0"))
        minor = int(request.form.get("minorVersion", "0"))
        build_num = int(request.form.get("buildNumber", "0"))
    except (ValueError, TypeError):
        return bad_request("Major version, minor version, and build number must be integers")

    board_revision_id = request.form.get("boardRevisionId", "").strip() or None
    if board_revision_id:
        board_rev = db.productboardrevision.find_first(
            where={"id": board_revision_id, "productId": product_id}
        )
        if not board_rev:
            return not_found("Board revision not found for this product")

    bootloader_id = request.form.get("bootloaderId", "").strip() or None
    is_manufacturing = request.form.get("isManufacturing", "false").lower() == "true"
    status = request.form.get("status", "DRAFT").strip()
    if status not in ("DRAFT", "RELEASED", "DEPRECATED"):
        return bad_request("Status must be DRAFT, RELEASED, or DEPRECATED")
    notes = request.form.get("notes", "").strip() or None

    # Check version uniqueness
    existing = db.firmwarebuild.find_first(
        where={"applicationId": application_id, "version": version}
    )
    if existing:
        return conflict(f"Build version '{version}' already exists for this application")

    # Read file data and compute checksum
    file_data = file.read()
    size_bytes = len(file_data)
    checksum = hashlib.sha256(file_data).hexdigest()
    content_type = MIME_TYPES.get(ext, file.content_type or "application/octet-stream")

    try:
        client = get_storage_client()
        bucket = get_bucket_name()

        # Create DB record first with a placeholder key to get the cuid
        placeholder_key = storage_key(
            StoragePrefixes.FIRMWARE_BUILDS,
            f"{product_id}/pending/{file.filename}"
        )

        build = db.firmwarebuild.create(
            data={
                "productId": product_id,
                "applicationId": application_id,
                "boardRevisionId": board_revision_id,
                "version": version,
                "majorVersion": major,
                "minorVersion": minor,
                "buildNumber": build_num,
                "bootloaderId": bootloader_id,
                "isManufacturing": is_manufacturing,
                "storageKey": placeholder_key,
                "filename": file.filename,
                "sizeBytes": size_bytes,
                "checksum": checksum,
                "contentType": content_type,
                "status": status,
                "notes": notes,
            },
        )

        # Now upload with the real key using the build ID
        object_key = storage_key(
            StoragePrefixes.FIRMWARE_BUILDS,
            f"{product_id}/{build.id}/{file.filename}"
        )

        client.put_object(
            bucket,
            object_key,
            BytesIO(file_data),
            length=size_bytes,
            content_type=content_type,
        )

        # Update the record with the real storage key
        build = db.firmwarebuild.update(
            where={"id": build.id},
            data={"storageKey": object_key},
            include={
                "application": True,
                "boardRevision": True,
            },
        )

        log_audit("firmwareBuild.upload", "FirmwareBuild", build.id, {
            "productName": product.name, "version": version,
            "filename": file.filename, "sizeBytes": size_bytes,
        })
        return jsonify(ApiResponse.ok(_serialize_build(build)).to_dict()), 201
    except Exception as e:
        logger.error("Failed to upload firmware build: %s", e)
        return internal_error("Failed to upload firmware build")


@require_permissions(Permissions.ADMIN_PRODUCTS_MANAGE)
def update_firmware_build(product_id: str, build_id: str):
    db = get_db_client()
    build = db.firmwarebuild.find_first(
        where={"id": build_id, "productId": product_id}
    )
    if not build:
        return not_found("Firmware build not found")

    data, error = FirmwareBuildUpdateRequest.from_json(request.get_json())
    if error:
        return bad_request(error)

    updated = db.firmwarebuild.update(
        where={"id": build_id},
        data=data.to_update_data(),
        include={
            "application": True,
            "boardRevision": True,
        },
    )
    log_audit("firmwareBuild.update", "FirmwareBuild", build_id, {
        "version": build.version, "changes": data.to_update_data(),
    })
    return jsonify(ApiResponse.ok(_serialize_build(updated)).to_dict()), 200


@require_permissions(Permissions.ADMIN_PRODUCTS_MANAGE)
def delete_firmware_build(product_id: str, build_id: str):
    db = get_db_client()
    build = db.firmwarebuild.find_first(
        where={"id": build_id, "productId": product_id}
    )
    if not build:
        return not_found("Firmware build not found")

    # Remove from MinIO
    if build.storageKey:
        try:
            client = get_storage_client()
            bucket = get_bucket_name()
            client.remove_object(bucket, build.storageKey)
        except Exception as e:
            logger.warning("Failed to remove firmware build object %s: %s", build.storageKey, e)

    db.firmwarebuild.delete(where={"id": build_id})
    log_audit("firmwareBuild.delete", "FirmwareBuild", build_id, {
        "version": build.version, "filename": build.filename,
    })
    return jsonify(ApiResponse.ok({"deleted": True}).to_dict()), 200


@require_permissions(Permissions.ADMIN_PRODUCTS_VIEW)
def download_firmware_build(build_id: str):
    db = get_db_client()
    build = db.firmwarebuild.find_unique(where={"id": build_id})
    if not build:
        return not_found("Firmware build not found")

    if build.storageKey:
        url = presigned_url(build.storageKey, download_filename=build.filename)
        if url:
            return jsonify(ApiResponse.ok({"url": url, "filename": build.filename}).to_dict()), 200
        return not_found("Firmware build file not found in storage")

    return not_found("Firmware build has no storage key")
