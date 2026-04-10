"""Zip-based asset set upload — validates and extracts firmware assets.

POST /v2/products/{pid}/asset-sets/upload-zip

Accepts a zip file structured by build matrix labels, validates contents
against the stage's StageBuildMatrix, then creates an AssetSet with
individual Asset records for each file.
"""

import hashlib
import io
import logging
import zipfile

from flask import g, jsonify, request
from database import Json

from src.lib.audit import log_audit
from src.lib.decorators import require_auth
from src.lib.errors import bad_request, forbidden, not_found
from src.lib.permissions import Permissions
from src.lib.types import ApiResponse
from src.services.database.prisma import get_db_client
from src.services.storage.client import get_storage_client, get_bucket_name

from .zip_validator import validate_zip, classify_file

logger = logging.getLogger(__name__)

ASSET_SETS_PREFIX = "asset-sets"


@require_auth
def upload_asset_set_zip(product_id: str):
    """Upload a zip file of firmware assets for a specific stage config.

    Form fields:
        file: zip archive (required)
        stageConfigId: FK to ProductStageConfig (required)
        version: semver string (required)
        variant: "debug", "release", "mfg" (default "debug")
        commitSha: git commit (optional)
        branch: git branch (optional)
        notes: free text (optional)
    """
    db = get_db_client()

    # Validate product
    product = db.product.find_unique(where={"id": product_id})
    if not product:
        return not_found("Product not found")

    # Parse form fields
    stage_config_id = (request.form.get("stageConfigId") or "").strip()
    if not stage_config_id:
        return bad_request("stageConfigId is required")

    version = (request.form.get("version") or "").strip()
    variant = (request.form.get("variant") or "debug").strip()
    commit_sha = (request.form.get("commitSha") or "").strip() or None
    branch = (request.form.get("branch") or "").strip() or None
    notes = (request.form.get("notes") or "").strip() or None

    # Validate stage config exists and belongs to this product
    stage_config = db.productstageconfig.find_unique(
        where={"id": stage_config_id},
        include={"buildMatrixEntries": True, "boardRevision": True},
    )
    if not stage_config:
        return not_found("Stage config not found")
    if stage_config.productId != product_id:
        return bad_request("Stage config does not belong to this product")

    # Validate zip file
    if "file" not in request.files:
        return bad_request("No file provided")
    file = request.files["file"]
    if not file.filename or not file.filename.lower().endswith(".zip"):
        return bad_request("File must be a .zip archive")

    # Read zip into memory
    zip_bytes = io.BytesIO(file.read())

    # Validate zip contents against build matrix
    matrix_entries = stage_config.buildMatrixEntries or []
    if not matrix_entries:
        return bad_request(
            "Stage has no build matrix entries. Configure the build matrix before uploading assets."
        )

    validation = validate_zip(zip_bytes, matrix_entries)
    if not validation.valid:
        return bad_request(
            f"Zip validation failed: {'; '.join(validation.errors)}"
        )

    # Auto-extract version from build.json manifest if not provided
    if not version or version == "auto":
        zip_bytes.seek(0)
        zf_peek = zipfile.ZipFile(zip_bytes, "r")
        for name in zf_peek.namelist():
            if name.endswith("build.json"):
                try:
                    import json
                    manifest = json.loads(zf_peek.read(name))
                    version = manifest.get("version", "unknown")
                    variant = manifest.get("variant", variant)
                    commit_sha = commit_sha or manifest.get("commitSha")
                    branch = branch or manifest.get("branch")
                    break
                except Exception:
                    pass
        zf_peek.close()
        if not version or version == "auto":
            version = "unknown"

    # Create AssetSet
    user_id = g.current_user.get("sub") if g.current_user else None
    board_revision_id = stage_config.boardRevisionId

    create_data: dict = {
        "product": {"connect": {"id": product_id}},
        "version": version,
        "variant": variant,
        "stage": stage_config.stage,
        "source": "MANUAL_UPLOAD",
        "status": "PENDING",
    }
    if board_revision_id:
        create_data["boardRevision"] = {"connect": {"id": board_revision_id}}
    if commit_sha:
        create_data["commitSha"] = commit_sha
    if branch:
        create_data["branch"] = branch
    if notes:
        create_data["notes"] = notes
    if user_id:
        create_data["createdBy"] = {"connect": {"id": user_id}}

    asset_set = db.assetset.create(data=create_data)

    # Extract and upload files
    storage = get_storage_client()
    bucket = get_bucket_name()
    zip_bytes.seek(0)
    zf = zipfile.ZipFile(zip_bytes, "r")

    assets_created = []
    matrix_by_label = {entry.label: entry for entry in matrix_entries}

    for zip_entry in zf.infolist():
        if zip_entry.is_dir():
            continue

        # Normalize backslashes (Windows zips) to forward slashes
        normalized_name = zip_entry.filename.replace("\\", "/")
        parts = normalized_name.split("/")
        if len(parts) < 2:
            continue

        label = parts[0]
        filename = parts[-1]
        if not filename:
            continue

        artifact_type = classify_file(filename)
        entry = matrix_by_label.get(label)

        # Determine role from matrix entry or filename
        role = _infer_role(filename, entry)

        # Read file content
        content = zf.read(zip_entry.filename)
        checksum = hashlib.sha256(content).hexdigest()

        # Upload to MinIO
        object_key = f"{ASSET_SETS_PREFIX}/{asset_set.id}/{label}/{filename}"
        storage.put_object(
            bucket,
            object_key,
            io.BytesIO(content),
            length=len(content),
        )

        # Create Asset record
        asset = db.asset.create(
            data={
                "assetSetId": asset_set.id,
                "label": label,
                "role": role,
                "processor": _infer_processor(filename, role),
                "artifactType": artifact_type,
                "storageKey": object_key,
                "filename": filename,
                "sizeBytes": len(content),
                "checksum": checksum,
            }
        )
        assets_created.append(asset)

    zf.close()

    # Mark complete
    asset_set = db.assetset.update(
        where={"id": asset_set.id},
        data={"status": "COMPLETE"},
        include={
            "assets": True,
            "boardRevision": True,
        },
    )

    log_audit("assetSet.uploadZip", "AssetSet", asset_set.id, {
        "productId": product_id,
        "stageConfigId": stage_config_id,
        "version": version,
        "fileCount": len(assets_created),
        "labels": validation.labels_found,
    })

    return jsonify(ApiResponse.ok(_serialize_asset_set(asset_set)).to_dict()), 201


def _infer_role(filename: str, matrix_entry) -> str:
    """Infer the asset role from filename patterns."""
    fn = filename.lower()
    if "modem" in fn:
        return "modem"
    if "comms" in fn or "nrf9151" in fn or "nrf9160" in fn:
        return "comms"
    if fn == "build.json":
        return "manifest"
    return "app"


def _infer_processor(filename: str, role: str) -> str | None:
    """Infer processor from role or filename."""
    fn = filename.lower()
    if "nrf52840" in fn or role == "app":
        return "nrf52840"
    if "nrf9151" in fn:
        return "nrf9151"
    if "nrf9160" in fn:
        return "nrf9160"
    if role == "comms":
        return None  # Could be either 9151 or 9160
    return None


def _serialize_asset_set(asset_set) -> dict:
    """Serialize an AssetSet with nested assets."""
    data = {
        "id": asset_set.id,
        "productId": asset_set.productId,
        "boardRevisionId": asset_set.boardRevisionId,
        "version": asset_set.version,
        "variant": asset_set.variant,
        "stage": asset_set.stage,
        "source": asset_set.source,
        "status": asset_set.status,
        "commitSha": asset_set.commitSha,
        "branch": asset_set.branch,
        "notes": asset_set.notes,
        "createdAt": asset_set.createdAt.isoformat() if asset_set.createdAt else None,
        "updatedAt": asset_set.updatedAt.isoformat() if asset_set.updatedAt else None,
    }
    if hasattr(asset_set, "boardRevision") and asset_set.boardRevision:
        data["boardRevision"] = {
            "id": asset_set.boardRevision.id,
            "version": asset_set.boardRevision.version,
            "ckBoardsName": getattr(asset_set.boardRevision, "ckBoardsName", None),
        }
    if hasattr(asset_set, "assets") and asset_set.assets:
        data["assets"] = [
            {
                "id": a.id,
                "label": a.label,
                "role": a.role,
                "processor": a.processor,
                "artifactType": a.artifactType,
                "filename": a.filename,
                "sizeBytes": int(a.sizeBytes),
                "checksum": a.checksum,
            }
            for a in asset_set.assets
        ]
    else:
        data["assets"] = []
    return data
