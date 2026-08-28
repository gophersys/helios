"""Zip-based asset set upload — validates and extracts firmware assets.

POST /v2/products/{pid}/asset-sets/upload-zip
POST /v2/products/{pid}/asset-sets/validate-zip
POST /v2/products/{pid}/asset-sets/analyze-files
POST /v2/products/{pid}/asset-sets/upload-files

Accepts a zip file structured by build matrix labels, validates contents
against the stage's StageBuildMatrix, then creates an AssetSet with
individual Asset records for each file.

The analyze-files and upload-files endpoints support loose file uploads
(no zip required), used by the UI wizard and TeamCity integrations.
"""

import hashlib
import io
import json
import logging
import re
import zipfile

from flask import g, jsonify, request
from database import Json

from src.lib.audit import log_audit
from src.lib.decorators import require_permissions
from src.lib.errors import bad_request, conflict, forbidden, not_found
from src.lib.permissions import Permissions
from src.lib.types import ApiResponse
from src.services.database.prisma import get_db_client
from src.services.storage.client import get_storage_client, get_bucket_name, product_asset_key, canonical_asset_filename

from .zip_validator import validate_zip, classify_file

logger = logging.getLogger(__name__)


def _try_parse_version(zf: zipfile.ZipFile) -> tuple[str | None, str | None]:
    """Try to extract firmware version from zip contents.

    Returns (version, source) where source is "build.json", "filename", or None.
    """
    # 1. Try build.json in any label directory
    for name in zf.namelist():
        normalized = name.replace("\\", "/")
        if normalized.endswith("/build.json") or normalized == "build.json":
            try:
                data = json.loads(zf.read(name))
                version = data.get("version")
                if version and version != "unknown":
                    return version, "build.json"
            except (json.JSONDecodeError, KeyError):
                pass

    # 2. Try parsing from hex filenames
    # Patterns: *_v1.2.3_*.hex, *_1.2.3.hex, *-1.2.3*.hex
    version_pattern = re.compile(r"[_-]v?(\d+\.\d+\.\d+(?:\.\d+)?)[_.-]")
    for name in zf.namelist():
        normalized = name.replace("\\", "/")
        filename = normalized.split("/")[-1]
        if filename.endswith(".hex") or filename.endswith(".cfw"):
            match = version_pattern.search(filename)
            if match:
                return match.group(1), "filename"

    # 3. Try parsing version from hex file content (MCUboot image header)
    # The MCUboot header contains a version at offset 0x20 in the binary.
    # Intel HEX files encode this differently, but we can look for
    # version strings embedded in the binary data.
    for name in zf.namelist():
        normalized = name.replace("\\", "/")
        filename = normalized.split("/")[-1]
        if filename.endswith(".hex"):
            try:
                content = zf.read(name).decode("ascii", errors="ignore")
                # Look for version strings in the hex content
                # Common patterns: "APP_VERSION 1.2.3", "FW_VERSION=1.2.3"
                ver_match = re.search(r"(?:APP_VERSION|FW_VERSION|VERSION)[=: ]+(\d+\.\d+\.\d+(?:\.\d+)?)", content)
                if ver_match:
                    return ver_match.group(1), "hex_content"
            except Exception:
                pass

    return None, None


@require_permissions(Permissions.BUILDS_VIEW)
def validate_asset_zip(product_id: str):
    """POST /products/<id>/asset-sets/validate-zip — validate without uploading.

    Validates the zip structure against the build matrix and attempts
    to parse the firmware version. Returns validation results + parsed
    version for the UI to display before committing the upload.

    Form fields:
        file: zip archive (required)
        stageConfigId: FK to ProductStageConfig (required)
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

    # Validate stage config exists and belongs to this product
    stage_config = db.productstageconfig.find_unique(
        where={"id": stage_config_id},
        include={"buildMatrixEntries": True},
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

    # Identify modem labels (fwType == "modem") -- these are handled separately
    modem_labels = {
        entry.label for entry in matrix_entries
        if getattr(entry, "fwType", None) == "modem"
    }

    validation = validate_zip(zip_bytes, matrix_entries, skip_labels=modem_labels)

    # Attempt version parsing — from build.json manifest or wrapper directory
    parsed_version = validation.parsed_version
    version_source = validation.version_source
    if not parsed_version:
        try:
            zip_bytes.seek(0)
            with zipfile.ZipFile(zip_bytes, "r") as zf:
                parsed_version, version_source = _try_parse_version(zf)
        except zipfile.BadZipFile:
            pass

    # Fetch available modem firmwares if modem labels are required
    available_modem_firmwares = []
    modem_labels_required = sorted(modem_labels) if modem_labels else []
    if modem_labels and stage_config.boardRevisionId:
        modem_fws = db.modemfirmware.find_many(
            where={"boardRevisionId": stage_config.boardRevisionId},
            order={"createdAt": "desc"},
        )
        available_modem_firmwares = [
            {
                "id": fw.id,
                "version": fw.version,
                "filename": fw.filename,
                "sizeBytes": fw.sizeBytes,
            }
            for fw in modem_fws
        ]

    return jsonify(ApiResponse.ok({
        "valid": validation.valid,
        "errors": validation.errors,
        "warnings": validation.warnings,
        "labelsFound": validation.labels_found,
        "fileCount": validation.file_count,
        "parsedVersion": parsed_version,
        "versionSource": version_source,
        "modemLabelsRequired": modem_labels_required,
        "availableModemFirmwares": available_modem_firmwares,
    }).to_dict()), 200


@require_permissions(Permissions.BUILDS_MANAGE)
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
    modem_firmware_id = (request.form.get("modemFirmwareId") or "").strip() or None

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

    # Skip modem labels from zip validation -- modem firmware is attached separately
    modem_labels = {
        entry.label for entry in matrix_entries
        if getattr(entry, "fwType", None) == "modem"
    }

    validation = validate_zip(zip_bytes, matrix_entries, skip_labels=modem_labels)
    if not validation.valid:
        return bad_request(
            f"Zip validation failed: {'; '.join(validation.errors)}"
        )

    # Validate modem firmware reference if provided
    modem_fw = None
    if modem_firmware_id:
        modem_fw = db.modemfirmware.find_first(where={"id": modem_firmware_id})
        if not modem_fw:
            return bad_request("Selected modem firmware not found")
        if modem_fw.boardRevisionId != stage_config.boardRevisionId:
            return bad_request("Selected modem firmware belongs to a different board revision")

    # Auto-extract version from build.json manifest if not provided
    if not version or version == "auto":
        zip_bytes.seek(0)
        zf_peek = zipfile.ZipFile(zip_bytes, "r")
        for name in zf_peek.namelist():
            if name.endswith("build.json"):
                try:
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

    # Check for duplicate version + variant + stage for this product/revision
    user_id = g.current_user.get("sub") if g.current_user else None
    board_revision_id = stage_config.boardRevisionId

    dup_where: dict = {
        "productId": product_id,
        "version": version,
        "variant": variant,
        "stage": stage_config.stage,
        "stageType": stage_config.type,
    }
    if board_revision_id:
        dup_where["boardRevisionId"] = board_revision_id
    existing = db.assetset.find_first(where=dup_where)
    if existing:
        return conflict(
            f"Asset set v{version} ({variant}) already exists for this stage and revision. "
            f"Delete the existing one first, or use a different version."
        )

    # Create AssetSet
    create_data: dict = {
        "product": {"connect": {"id": product_id}},
        "version": version,
        "variant": variant,
        "stage": stage_config.stage,
        "stageType": stage_config.type,
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
    if modem_firmware_id:
        create_data["modemFirmware"] = {"connect": {"id": modem_firmware_id}}

    asset_set = db.assetset.create(data=create_data)

    # Extract and upload files
    storage = get_storage_client()
    bucket = get_bucket_name()
    zip_bytes.seek(0)
    zf = zipfile.ZipFile(zip_bytes, "r")

    assets_created = []
    matrix_by_label = {entry.label: entry for entry in matrix_entries}

    # Look up product slug and revision version for canonical filenames
    product_slug = getattr(product, "slug", None)
    rev_version = getattr(stage_config.boardRevision, "version", None) if stage_config.boardRevision else None

    # Detect wrapper directory (e.g., v0.5.13/mfg_app_debug/file.hex)
    all_roots = set()
    for zi in zf.infolist():
        if zi.is_dir():
            continue
        parts = [p for p in zi.filename.replace("\\", "/").split("/") if p]
        if len(parts) >= 2:
            all_roots.add(parts[0])
    wrapper_dir = None
    if len(all_roots) == 1:
        candidate = all_roots.pop()
        if candidate.lower() not in matrix_by_label:
            wrapper_dir = candidate

    for zip_entry in zf.infolist():
        if zip_entry.is_dir():
            continue

        # Normalize backslashes (Windows zips) to forward slashes
        normalized_name = zip_entry.filename.replace("\\", "/")
        parts = [p for p in normalized_name.split("/") if p]

        # Strip wrapper directory if detected
        if wrapper_dir and len(parts) > 1 and parts[0] == wrapper_dir:
            parts = parts[1:]

        if len(parts) < 2:
            continue

        label = parts[0]
        filename = parts[-1]
        if not filename:
            continue

        # Skip modem label folders — modem firmware is attached separately
        if label in modem_labels:
            continue

        artifact_type = classify_file(filename)
        entry = matrix_by_label.get(label)

        # Determine role from matrix entry or filename
        role = _infer_role(filename, entry)

        # Compute canonical filename from matrix entry metadata
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "hex"
        if entry and product_slug and rev_version:
            canon_name = canonical_asset_filename(
                product_slug=product_slug,
                role=getattr(entry, "fwType", None) or role,
                processor=getattr(entry, "processor", None) or _infer_processor(filename, role) or "unknown",
                revision=rev_version,
                variant=getattr(entry, "variant", None) or variant,
                ext=ext,
            )
        else:
            canon_name = filename

        # Read file content
        content = zf.read(zip_entry.filename)
        checksum = hashlib.sha256(content).hexdigest()

        # Upload to MinIO
        object_key = product_asset_key(
            product_slug=product_slug,
            revision_version=rev_version,
            stage_type=stage_config.type,
            stage=stage_config.stage,
            asset_version=version,
            variant=variant,
            label=label,
            filename=canon_name,
            stage_name=getattr(stage_config, "name", None),
        )
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
                "processor": getattr(entry, "processor", None) or _infer_processor(filename, role),
                "artifactType": artifact_type,
                "storageKey": object_key,
                "filename": canon_name,
                "sizeBytes": len(content),
                "checksum": checksum,
            }
        )
        assets_created.append(asset)

    zf.close()

    # Create a virtual Asset record for the modem firmware if selected
    if modem_fw and modem_labels:
        modem_label = sorted(modem_labels)[0]
        asset = db.asset.create(
            data={
                "assetSetId": asset_set.id,
                "label": modem_label,
                "role": "modem",
                "processor": None,
                "artifactType": "other",
                "storageKey": modem_fw.storageKey,
                "filename": modem_fw.filename,
                "sizeBytes": modem_fw.sizeBytes,
                "checksum": modem_fw.checksum or "",
            }
        )
        assets_created.append(asset)

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
    """Infer the asset role from the matrix entry's fwType, falling
    back to filename pattern heuristics.

    The matrix entry comes from the product/board's stage config —
    when the operator picks a label in the upload wizard, we know
    which processor target (``app`` / ``comms``) that label is for.
    Trusting the matrix avoids a class of bugs where an operator
    uploaded a hex whose original filename didn't carry processor
    hints (e.g. ``firmware.hex`` straight from a build job): the
    canonical filename was already computed from ``entry.fwType``,
    but the DB ``role`` column was left at the filename-only guess
    so downstream consumers like FirmwareSet.hex(role=…) silently
    fell through to the "app" default and never found the comms hex.
    """
    fw_type = getattr(matrix_entry, "fwType", None)
    if fw_type:
        return fw_type
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
        "stageType": getattr(asset_set, "stageType", None),
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


# ---------------------------------------------------------------------------
# Smart file analysis and upload (loose files, no zip required)
# ---------------------------------------------------------------------------

def _detect_processor(filename: str) -> str | None:
    """Detect target processor from filename."""
    lower = filename.lower()
    if "nrf52840" in lower:
        return "nrf52840"
    if "nrf9151" in lower:
        return "nrf9151"
    if "nrf9160" in lower:
        return "nrf9160"
    return None


def _detect_variant(filename: str) -> str | None:
    """Detect firmware variant from filename."""
    lower = filename.lower()
    if "debug" in lower:
        return "debug"
    if "release" in lower:
        return "release"
    return None


def _detect_file_type(filename: str) -> str:
    """Detect artifact type from file extension."""
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    return {
        "hex": "plaintextHex",
        "cfw": "encryptedCfw",
        "json": "manifest",
        "zip": "other",
        "bin": "other",
    }.get(ext, "unknown")


def _match_file_to_label(filename, processor, variant, file_type, matrix_entries, skip_labels):
    """Find the best matching matrix label for a file.

    Returns (matrix_entry, confidence) where confidence is
    "high", "medium", "low", or None.
    """
    best_match = None
    best_score = 0

    for entry in matrix_entries:
        if entry.label in skip_labels:
            continue

        score = 0

        # Check processor match (strongest signal)
        if processor and getattr(entry, "processor", None) and processor == entry.processor:
            score += 3

        # Check variant match
        if variant and entry.variant == variant:
            score += 2

        # Check file type match
        if file_type == "plaintextHex" and entry.producesHex:
            score += 1
        elif file_type == "encryptedCfw" and entry.producesCfw:
            score += 1

        if score > best_score:
            best_score = score
            best_match = entry

    if best_match is None:
        return None, None

    if best_score >= 5:
        confidence = "high"
    elif best_score >= 3:
        confidence = "medium"
    elif best_score >= 1:
        confidence = "low"
    else:
        confidence = None

    return best_match, confidence


def _build_match_reason(processor, variant, file_type, label) -> str:
    """Build a human-readable reason for a match."""
    parts = []
    if processor:
        parts.append(f"Processor {processor}")
    if variant:
        parts.append(f"variant {variant}")
    if file_type in ("plaintextHex", "encryptedCfw"):
        ext = "hex" if file_type == "plaintextHex" else "cfw"
        parts.append(f"{ext} file")
    reason = " + ".join(parts)
    return f"{reason} matches {label}" if reason else f"Matched to {label}"


@require_permissions(Permissions.BUILDS_VIEW)
def analyze_asset_files(product_id: str):
    """Analyze uploaded files and suggest matrix label matches.

    Form fields:
        stageConfigId: FK to ProductStageConfig (required)
        files: multipart file uploads (required, multiple)
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

    # Validate stage config
    stage_config = db.productstageconfig.find_unique(
        where={"id": stage_config_id},
        include={"buildMatrixEntries": True},
    )
    if not stage_config:
        return not_found("Stage config not found")
    if stage_config.productId != product_id:
        return bad_request("Stage config does not belong to this product")

    matrix_entries = stage_config.buildMatrixEntries or []
    if not matrix_entries:
        return bad_request(
            "Stage has no build matrix entries. Configure the build matrix before uploading assets."
        )

    # Identify modem labels
    modem_labels = {
        entry.label for entry in matrix_entries
        if getattr(entry, "fwType", None) == "modem"
    }
    non_modem_entries = [e for e in matrix_entries if e.label not in modem_labels]

    # Validate files
    files = request.files.getlist("files")
    if not files:
        return bad_request("No files provided")

    # Analyze each file
    file_results = []
    assigned_labels = set()

    for f in files:
        filename = f.filename or "unknown"
        f.seek(0, 2)
        size = f.tell()
        f.seek(0)

        processor = _detect_processor(filename)
        variant = _detect_variant(filename)
        file_type = _detect_file_type(filename)

        match, confidence = _match_file_to_label(
            filename, processor, variant, file_type,
            non_modem_entries, assigned_labels,
        )

        suggested_label = match.label if match else None
        match_reason = None
        if match:
            match_reason = _build_match_reason(processor, variant, file_type, match.label)
            assigned_labels.add(match.label)

        file_results.append({
            "filename": filename,
            "size": size,
            "detectedType": file_type,
            "detectedProcessor": processor,
            "detectedVariant": variant,
            "suggestedLabel": suggested_label,
            "confidence": confidence,
            "matchReason": match_reason,
        })

    # Determine unmatched labels
    all_non_modem_labels = {e.label for e in non_modem_entries}
    unmatched_labels = sorted(all_non_modem_labels - assigned_labels)

    # Fetch available modem firmwares if needed
    available_modem_firmwares = []
    modem_labels_required = sorted(modem_labels) if modem_labels else []
    if modem_labels and stage_config.boardRevisionId:
        modem_fws = db.modemfirmware.find_many(
            where={"boardRevisionId": stage_config.boardRevisionId},
            order={"createdAt": "desc"},
        )
        available_modem_firmwares = [
            {
                "id": fw.id,
                "version": fw.version,
                "filename": fw.filename,
                "sizeBytes": fw.sizeBytes,
            }
            for fw in modem_fws
        ]

    return jsonify(ApiResponse.ok({
        "files": file_results,
        "unmatchedLabels": unmatched_labels,
        "allMatched": len(unmatched_labels) == 0,
        "modemLabelsRequired": modem_labels_required,
        "availableModemFirmwares": available_modem_firmwares,
    }).to_dict()), 200


@require_permissions(Permissions.BUILDS_MANAGE)
def upload_asset_files(product_id: str):
    """Upload loose files with explicit label assignments.

    Form fields:
        stageConfigId: FK to ProductStageConfig (required)
        version: semver string (required)
        modemFirmwareId: FK to ModemFirmware (optional)
        notes: free text (optional)
        files: multipart file uploads (required, multiple)
        labels: string array matching files order (required, same length)
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
    if not version:
        return bad_request("version is required")

    modem_firmware_id = (request.form.get("modemFirmwareId") or "").strip() or None
    notes = (request.form.get("notes") or "").strip() or None

    # Validate stage config
    stage_config = db.productstageconfig.find_unique(
        where={"id": stage_config_id},
        include={"buildMatrixEntries": True, "boardRevision": True},
    )
    if not stage_config:
        return not_found("Stage config not found")
    if stage_config.productId != product_id:
        return bad_request("Stage config does not belong to this product")

    matrix_entries = stage_config.buildMatrixEntries or []
    if not matrix_entries:
        return bad_request(
            "Stage has no build matrix entries. Configure the build matrix before uploading assets."
        )

    # Identify modem labels
    modem_labels = {
        entry.label for entry in matrix_entries
        if getattr(entry, "fwType", None) == "modem"
    }

    # Parse files and labels
    files = request.files.getlist("files")
    labels = request.form.getlist("labels")

    if not files:
        return bad_request("No files provided")
    if len(files) != len(labels):
        return bad_request(
            f"Number of files ({len(files)}) must match number of labels ({len(labels)})"
        )

    # Validate each label exists in the build matrix (excluding modem labels)
    matrix_by_label = {entry.label: entry for entry in matrix_entries}
    non_modem_labels = {e.label for e in matrix_entries if e.label not in modem_labels}

    for label in labels:
        label = label.strip()
        if label not in non_modem_labels:
            return bad_request(
                f"Label '{label}' is not in the build matrix (or is a modem label)"
            )

    # Validate all required non-modem labels have a file
    assigned_labels = {l.strip() for l in labels}
    missing_labels = non_modem_labels - assigned_labels
    if missing_labels:
        return bad_request(
            f"Missing files for required labels: {', '.join(sorted(missing_labels))}"
        )

    # Validate modem firmware if provided
    modem_fw = None
    if modem_firmware_id:
        modem_fw = db.modemfirmware.find_first(where={"id": modem_firmware_id})
        if not modem_fw:
            return bad_request("Selected modem firmware not found")
        if modem_fw.boardRevisionId != stage_config.boardRevisionId:
            return bad_request("Selected modem firmware belongs to a different board revision")

    # Check for duplicate version + variant + stage for this product/revision
    user_id = g.current_user.get("sub") if g.current_user else None
    board_revision_id = stage_config.boardRevisionId

    dup_where: dict = {
        "productId": product_id,
        "version": version,
        "variant": "multi",
        "stage": stage_config.stage,
        "stageType": stage_config.type,
    }
    if board_revision_id:
        dup_where["boardRevisionId"] = board_revision_id
    existing = db.assetset.find_first(where=dup_where)
    if existing:
        return conflict(
            f"Asset set v{version} already exists for this stage and revision. "
            f"Delete the existing one first, or use a different version."
        )

    # Create AssetSet
    create_data: dict = {
        "product": {"connect": {"id": product_id}},
        "version": version,
        "variant": "multi",
        "stage": stage_config.stage,
        "stageType": stage_config.type,
        "source": "MANUAL_UPLOAD",
        "status": "PENDING",
    }
    if board_revision_id:
        create_data["boardRevision"] = {"connect": {"id": board_revision_id}}
    if notes:
        create_data["notes"] = notes
    if user_id:
        create_data["createdBy"] = {"connect": {"id": user_id}}
    if modem_firmware_id:
        create_data["modemFirmware"] = {"connect": {"id": modem_firmware_id}}

    asset_set = db.assetset.create(data=create_data)

    # Upload each file
    storage = get_storage_client()
    bucket = get_bucket_name()
    assets_created = []

    # Look up product slug and revision version for canonical filenames
    product_slug = getattr(product, "slug", None)
    rev_version = getattr(stage_config.boardRevision, "version", None) if stage_config.boardRevision else None

    for f, label in zip(files, labels):
        label = label.strip()
        filename = f.filename or "unknown"
        content = f.read()
        checksum = hashlib.sha256(content).hexdigest()

        artifact_type = classify_file(filename)
        entry = matrix_by_label.get(label)
        role = _infer_role(filename, entry)

        # Compute canonical filename from matrix entry metadata
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "hex"
        if entry and product_slug and rev_version:
            canon_name = canonical_asset_filename(
                product_slug=product_slug,
                role=getattr(entry, "fwType", None) or role,
                processor=getattr(entry, "processor", None) or _infer_processor(filename, role) or "unknown",
                revision=rev_version,
                variant=getattr(entry, "variant", None) or "debug",
                ext=ext,
            )
        else:
            canon_name = filename

        object_key = product_asset_key(
            product_slug=product_slug,
            revision_version=rev_version,
            stage_type=stage_config.type,
            stage=stage_config.stage,
            asset_version=version,
            variant="debug",
            label=label,
            filename=canon_name,
            stage_name=getattr(stage_config, "name", None),
        )
        storage.put_object(
            bucket,
            object_key,
            io.BytesIO(content),
            length=len(content),
        )

        asset = db.asset.create(
            data={
                "assetSetId": asset_set.id,
                "label": label,
                "role": role,
                "processor": getattr(entry, "processor", None) or _infer_processor(filename, role),
                "artifactType": artifact_type,
                "storageKey": object_key,
                "filename": canon_name,
                "sizeBytes": len(content),
                "checksum": checksum,
            }
        )
        assets_created.append(asset)

    # Create virtual Asset for modem firmware if selected
    if modem_fw and modem_labels:
        modem_label = sorted(modem_labels)[0]
        asset = db.asset.create(
            data={
                "assetSetId": asset_set.id,
                "label": modem_label,
                "role": "modem",
                "processor": None,
                "artifactType": "other",
                "storageKey": modem_fw.storageKey,
                "filename": modem_fw.filename,
                "sizeBytes": modem_fw.sizeBytes,
                "checksum": modem_fw.checksum or "",
            }
        )
        assets_created.append(asset)

    # Mark complete
    asset_set = db.assetset.update(
        where={"id": asset_set.id},
        data={"status": "COMPLETE"},
        include={
            "assets": True,
            "boardRevision": True,
        },
    )

    log_audit("assetSet.uploadFiles", "AssetSet", asset_set.id, {
        "productId": product_id,
        "stageConfigId": stage_config_id,
        "version": version,
        "fileCount": len(assets_created),
        "labels": list(assigned_labels),
    })

    return jsonify(ApiResponse.ok(_serialize_asset_set(asset_set)).to_dict()), 201
