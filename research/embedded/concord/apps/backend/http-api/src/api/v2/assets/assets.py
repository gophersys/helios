"""Individual asset upload endpoint.

Upload firmware artifacts (hex, cfw, manifest) into an asset set.
Files are stored in MinIO under asset-sets/{asset_set_id}/{filename}.
"""

import hashlib
import io
import logging
from flask import jsonify, request

from src.lib.audit import log_audit
from src.lib.decorators import require_permissions
from src.lib.errors import bad_request, not_found
from src.lib.permissions import Permissions
from src.lib.types import ApiResponse
from src.services.database.prisma import get_db_client
from src.services.storage.client import get_storage_client, get_bucket_name, product_asset_key

logger = logging.getLogger(__name__)

VALID_ARTIFACT_TYPES = {"plaintextHex", "encryptedCfw", "manifest", "log", "metadata", "other"}


@require_permissions(Permissions.BUILDS_MANAGE)
def upload_asset(asset_set_id: str):
    """POST /asset-sets/<id>/assets — upload an individual asset file.

    Form fields:
        file: the file to upload
        label: build matrix label (e.g. "mfg_app_debug")
        role: "app", "comms", "modem"
        artifactType: "plaintextHex", "encryptedCfw", "manifest", etc.
        processor: (optional) "nrf52840", "nrf9151"
        contentType: (optional) MIME type
    """
    db = get_db_client()
    asset_set = db.assetset.find_unique(
        where={"id": asset_set_id},
        include={"product": True, "boardRevision": True},
    )
    if not asset_set:
        return not_found("Asset set not found")
    if asset_set.status not in ("PENDING",):
        return bad_request(f"Cannot upload to asset set with status {asset_set.status}")

    if "file" not in request.files:
        return bad_request("No file provided")
    file = request.files["file"]
    if not file.filename:
        return bad_request("File has no filename")

    label = (request.form.get("label") or "").strip()
    if not label:
        return bad_request("label is required")
    role = (request.form.get("role") or "").strip()
    if not role:
        return bad_request("role is required")
    artifact_type = (request.form.get("artifactType") or "").strip()
    if not artifact_type:
        return bad_request("artifactType is required")
    if artifact_type not in VALID_ARTIFACT_TYPES:
        return bad_request(f"Invalid artifactType. Valid: {sorted(VALID_ARTIFACT_TYPES)}")

    processor = (request.form.get("processor") or "").strip() or None
    content_type = (request.form.get("contentType") or file.content_type or "").strip() or None

    # Read file data, compute checksum and size
    file_data = file.read()
    size_bytes = len(file_data)
    checksum = hashlib.sha256(file_data).hexdigest()

    # Store in MinIO
    s3_key = product_asset_key(
        product_slug=getattr(asset_set.product, "slug", None) if asset_set.product else None,
        revision_version=getattr(asset_set.boardRevision, "version", None) if asset_set.boardRevision else None,
        stage_type=getattr(asset_set, "stageType", None),
        stage=getattr(asset_set, "stage", None),
        asset_version=asset_set.version,
        variant=asset_set.variant,
        label=label,
        filename=file.filename,
        stage_name=getattr(asset_set, "stageName", None),
    )
    storage = get_storage_client()
    bucket = get_bucket_name()

    storage.put_object(
        bucket,
        s3_key,
        io.BytesIO(file_data),
        length=size_bytes,
        content_type=content_type or "application/octet-stream",
    )

    asset = db.asset.create(data={
        "assetSetId": asset_set_id,
        "label": label,
        "role": role,
        "processor": processor,
        "artifactType": artifact_type,
        "storageKey": s3_key,
        "filename": file.filename,
        "sizeBytes": size_bytes,
        "checksum": checksum,
        "contentType": content_type,
    })

    log_audit("asset.upload", "Asset", asset.id, {
        "assetSetId": asset_set_id,
        "label": label,
        "filename": file.filename,
    })

    return jsonify(ApiResponse.ok({
        "id": asset.id,
        "assetSetId": asset.assetSetId,
        "label": asset.label,
        "role": asset.role,
        "processor": asset.processor,
        "artifactType": asset.artifactType,
        "storageKey": asset.storageKey,
        "filename": asset.filename,
        "sizeBytes": int(asset.sizeBytes),
        "checksum": asset.checksum,
        "contentType": asset.contentType,
        "createdAt": asset.createdAt.isoformat() if hasattr(asset.createdAt, "isoformat") else asset.createdAt,
    }).to_dict()), 201
