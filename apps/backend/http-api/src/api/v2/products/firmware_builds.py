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
from .types import FirmwareBuildUpdateRequest

logger = logging.getLogger(__name__)

_BUILD_INCLUDE = {
    "target": True,
}


def _serialize_build(b: Any) -> dict:
    data = {
        "id": b.id,
        "productId": b.productId,
        "targetId": b.targetId,
        "version": b.version,
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
    if hasattr(b, "target") and b.target is not None:
        data["target"] = {
            "id": b.target.id,
            "role": b.target.role,
            "soc": b.target.soc,
            "appId": b.target.appId,
        }
    else:
        data["target"] = None
    if hasattr(b, "modemFilename") and b.modemFilename:
        data["modemFilename"] = b.modemFilename
        data["modemSizeBytes"] = str(b.modemSizeBytes) if b.modemSizeBytes is not None else None
        data["modemChecksum"] = b.modemChecksum
    return data


# ── Firmware Builds ─────────────────────────────────────────


@require_permissions(Permissions.PRODUCTS_VIEW)
def list_firmware_builds(product_id: str):
    db = get_db_client()
    product = db.product.find_unique(where={"id": product_id})
    if not product:
        return not_found("Product not found")

    where: dict = {"productId": product_id}
    target_id = request.args.get("targetId")
    if target_id:
        where["targetId"] = target_id
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
        include=_BUILD_INCLUDE,
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


@require_permissions(Permissions.PRODUCTS_MANAGE)
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
    target_id = request.form.get("targetId", "").strip()
    if not target_id:
        return bad_request("Target ID is required")

    # Validate target exists and belongs to a board revision under this product
    target_record = db.producttarget.find_first(
        where={
            "id": target_id,
            "boardRevision": {"board": {"productId": product_id}},
        },
    )
    if not target_record:
        return bad_request(f"Target '{target_id}' not found for this product")

    version = request.form.get("version", "").strip()
    if not version:
        return bad_request("Version is required")

    is_manufacturing = request.form.get("isManufacturing", "false").lower() == "true"
    status = request.form.get("status", "DRAFT").strip()
    if status not in ("DRAFT", "RELEASED", "DEPRECATED"):
        return bad_request("Status must be DRAFT, RELEASED, or DEPRECATED")
    notes = request.form.get("notes", "").strip() or None

    # Check version uniqueness per (product, targetId, version)
    existing = db.firmwarebuild.find_first(
        where={
            "productId": product_id,
            "targetId": target_id,
            "version": version,
        }
    )
    if existing:
        return conflict(f"Build version '{version}' already exists for target {target_record.role}")

    # Modem firmware file
    modem_file = request.files.get("modemFile")
    modem_data = None
    modem_checksum = None
    if modem_file and modem_file.filename:
        modem_ext = modem_file.filename.rsplit(".", 1)[-1].lower() if "." in modem_file.filename else ""
        if modem_ext != "zip":
            return bad_request("Modem firmware file must be a .zip")
        modem_data = modem_file.read()
        modem_checksum = hashlib.sha256(modem_data).hexdigest()

    # Read file data and compute checksum
    file_data = file.read()
    size_bytes = len(file_data)
    checksum = hashlib.sha256(file_data).hexdigest()
    content_type = MIME_TYPES.get(ext, file.content_type or "application/octet-stream")

    try:
        client = get_storage_client()
        bucket = get_bucket_name()

        safe_filename = _secure_filename(file.filename)
        placeholder_key = storage_key(
            StoragePrefixes.FIRMWARE_BUILDS,
            f"{product_id}/pending/{safe_filename}"
        )

        create_data = {
            "productId": product_id,
            "targetId": target_id,
            "version": version,
            "isManufacturing": is_manufacturing,
            "storageKey": placeholder_key,
            "filename": file.filename,
            "sizeBytes": size_bytes,
            "checksum": checksum,
            "contentType": content_type,
            "status": status,
            "notes": notes,
        }
        if modem_data is not None:
            create_data["modemFilename"] = modem_file.filename
            create_data["modemSizeBytes"] = len(modem_data)
            create_data["modemChecksum"] = modem_checksum

        build = db.firmwarebuild.create(data=create_data)

        object_key = storage_key(
            StoragePrefixes.FIRMWARE_BUILDS,
            f"{product_id}/{build.id}/{safe_filename}"
        )

        client.put_object(
            bucket,
            object_key,
            BytesIO(file_data),
            length=size_bytes,
            content_type=content_type,
        )

        update_data = {"storageKey": object_key}
        if modem_data is not None:
            safe_modem_filename = _secure_filename(modem_file.filename)
            modem_key = storage_key(
                StoragePrefixes.FIRMWARE_BUILDS,
                f"{product_id}/{build.id}/{safe_modem_filename}"
            )
            client.put_object(
                bucket,
                modem_key,
                BytesIO(modem_data),
                length=len(modem_data),
                content_type="application/zip",
            )
            update_data["modemStorageKey"] = modem_key

        build = db.firmwarebuild.update(
            where={"id": build.id},
            data=update_data,
            include=_BUILD_INCLUDE,
        )

        log_audit("firmwareBuild.upload", "FirmwareBuild", build.id, {
            "productName": product.name, "version": version,
            "targetId": target_id, "targetRole": target_record.role,
            "filename": file.filename, "sizeBytes": size_bytes,
        })
        return jsonify(ApiResponse.ok(_serialize_build(build)).to_dict()), 201
    except Exception as e:
        logger.error("Failed to upload firmware build: %s", e)
        return internal_error("Failed to upload firmware build")


@require_permissions(Permissions.PRODUCTS_MANAGE)
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
        include=_BUILD_INCLUDE,
    )
    log_audit("firmwareBuild.update", "FirmwareBuild", build_id, {
        "version": build.version, "changes": data.to_update_data(),
    })
    return jsonify(ApiResponse.ok(_serialize_build(updated)).to_dict()), 200


@require_permissions(Permissions.PRODUCTS_MANAGE)
def delete_firmware_build(product_id: str, build_id: str):
    db = get_db_client()
    build = db.firmwarebuild.find_first(
        where={"id": build_id, "productId": product_id}
    )
    if not build:
        return not_found("Firmware build not found")

    try:
        client = get_storage_client()
        bucket = get_bucket_name()
        if build.storageKey:
            client.remove_object(bucket, build.storageKey)
        if hasattr(build, "modemStorageKey") and build.modemStorageKey:
            client.remove_object(bucket, build.modemStorageKey)
    except Exception as e:
        logger.warning("Failed to remove firmware build object(s): %s", e)

    db.firmwarebuild.delete(where={"id": build_id})
    log_audit("firmwareBuild.delete", "FirmwareBuild", build_id, {
        "version": build.version, "filename": build.filename,
    })
    return jsonify(ApiResponse.ok({"deleted": True}).to_dict()), 200


@require_permissions(Permissions.PRODUCTS_VIEW)
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
