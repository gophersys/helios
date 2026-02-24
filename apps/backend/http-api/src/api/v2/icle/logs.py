"""ICLE device log upload and listing endpoints."""

import io
import logging
from datetime import datetime, timezone

from flask import jsonify, request

from src.lib.audit import log_audit
from src.lib.decorators import require_permissions
from src.lib.errors import bad_request, not_found
from src.lib.permissions import Permissions
from src.lib.types import ApiResponse
from src.services.database.prisma import get_db_client
from src.services.storage.client import (
    get_bucket_name,
    get_storage_client,
    presigned_get_url,
    storage_key,
)

logger = logging.getLogger(__name__)

# Storage prefix for ICLE logs
ICLE_LOGS_PREFIX = "icle/logs"


def _serialize_log(log_entry) -> dict:
    """Serialize IcleLog to JSON-compatible dict."""
    return {
        "id": log_entry.id,
        "deviceId": log_entry.deviceId,
        "filename": log_entry.filename,
        "storageKey": log_entry.storageKey,
        "sizeBytes": int(log_entry.sizeBytes) if log_entry.sizeBytes else 0,
        "format": log_entry.format,
        "uploadedAt": log_entry.uploadedAt.isoformat() if log_entry.uploadedAt else None,
    }


@require_permissions(Permissions.ADMIN_ICLE_VIEW)
def list_device_logs(device_id: str):
    """List log files uploaded from an ICLE device.

    GET /v2/icle/devices/:id/logs?page=1&limit=50
    """
    db = get_db_client()

    # Check device exists
    device = db.icledevice.find_unique(where={"id": device_id})
    if not device:
        return not_found("ICLE device not found")

    # Pagination
    page = max(1, request.args.get("page", 1, type=int))
    limit = min(max(1, request.args.get("limit", 50, type=int)), 100)
    skip = (page - 1) * limit

    # Get total count
    total = db.iclelog.count(where={"deviceId": device_id})

    # Fetch logs
    logs = db.iclelog.find_many(
        where={"deviceId": device_id},
        skip=skip,
        take=limit,
        order={"uploadedAt": "desc"},
    )

    pages = (total + limit - 1) // limit if total > 0 else 1

    # Add download URLs
    log_data = []
    for log_entry in logs:
        entry = _serialize_log(log_entry)
        entry["downloadUrl"] = presigned_get_url(
            log_entry.storageKey,
            expires_hours=1,
            download_filename=log_entry.filename,
        )
        log_data.append(entry)

    return jsonify(ApiResponse.paginated(
        data=log_data,
        page=page,
        total_pages=pages,
        total_results=total,
        results_per_page=limit,
    ).to_dict()), 200


@require_permissions(Permissions.ADMIN_ICLE_MANAGE)
def upload_device_log(device_id: str):
    """Upload a log file from an ICLE device.

    POST /v2/icle/devices/:id/logs

    Form data:
        - file: The log file (binary or CSV)
        - filename: Optional filename override
        - format: "binary" or "csv" (default: auto-detect from extension)
    """
    db = get_db_client()

    # Check device exists
    device = db.icledevice.find_unique(where={"id": device_id})
    if not device:
        return not_found("ICLE device not found")

    # Get uploaded file
    if "file" not in request.files:
        return bad_request("No file provided")

    file = request.files["file"]
    if not file.filename:
        return bad_request("No filename provided")

    # Get filename (allow override from form data)
    filename = request.form.get("filename", "").strip() or file.filename
    if len(filename) > 255:
        return bad_request("Filename too long (max 255 characters)")

    # Validate filename - basic sanitization
    if "/" in filename or "\\" in filename or ".." in filename:
        return bad_request("Invalid filename")

    # Determine format
    log_format = request.form.get("format", "").strip().lower()
    if not log_format:
        # Auto-detect from extension
        if filename.endswith(".csv"):
            log_format = "csv"
        else:
            log_format = "binary"

    if log_format not in ["binary", "csv"]:
        return bad_request("Invalid format. Must be 'binary' or 'csv'")

    # Read file content
    file_content = file.read()
    file_size = len(file_content)

    if file_size == 0:
        return bad_request("Empty file")

    # Max file size: 100MB
    if file_size > 100 * 1024 * 1024:
        return bad_request("File too large (max 100MB)")

    # Generate storage key
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    key = storage_key(ICLE_LOGS_PREFIX, f"{device.deviceId}/{timestamp}_{filename}")

    # Upload to MinIO
    try:
        storage = get_storage_client()
        content_type = "text/csv" if log_format == "csv" else "application/octet-stream"
        storage.put_object(
            get_bucket_name(),
            key,
            io.BytesIO(file_content),
            length=file_size,
            content_type=content_type,
        )
    except Exception as e:
        logger.error("Failed to upload ICLE log to storage: %s", e)
        return bad_request("Failed to upload file to storage")

    # Check for existing log with same filename (upsert)
    existing = db.iclelog.find_first(
        where={"deviceId": device_id, "filename": filename}
    )

    if existing:
        # Update existing entry
        log_entry = db.iclelog.update(
            where={"id": existing.id},
            data={
                "storageKey": key,
                "sizeBytes": file_size,
                "format": log_format,
                "uploadedAt": datetime.now(timezone.utc),
            },
        )
    else:
        # Create new entry
        log_entry = db.iclelog.create(
            data={
                "deviceId": device_id,
                "filename": filename,
                "storageKey": key,
                "sizeBytes": file_size,
                "format": log_format,
            },
        )

    log_audit("icle.log.upload", "IcleLog", log_entry.id, {
        "deviceId": device.deviceId,
        "filename": filename,
        "sizeBytes": file_size,
        "format": log_format,
    })

    result = _serialize_log(log_entry)
    result["downloadUrl"] = presigned_get_url(key, expires_hours=1, download_filename=filename)

    return jsonify(ApiResponse.created(result).to_dict()), 201
