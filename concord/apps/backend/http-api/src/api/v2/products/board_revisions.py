import hashlib
import logging
import re
from io import BytesIO
from typing import Any, Dict

from flask import Response, g, jsonify, request

from src.lib.audit import log_audit
from src.lib.decorators import require_permissions
from src.lib.errors import bad_request, conflict, internal_error, not_found
from src.lib.permissions import Permissions
from src.lib.types import ApiResponse
from src.services.database.prisma import get_db_client
from src.services.storage.client import get_bucket_name, get_storage_client, storage_key, modem_firmware_key

from .types import (
    BoardRevisionCreateRequest,
    BoardRevisionUpdateRequest,
    TargetCreateRequest,
    TargetUpdateRequest,
)

from .shared import serialize_target as _serialize_target

logger = logging.getLogger(__name__)


def _serialize_revision(r) -> dict:
    """Serialize a BoardRevision DB record to an API response dict."""
    result = {
        "id": r.id,
        "boardId": r.boardId,
        "version": r.version,
        "ckBoardsName": getattr(r, "ckBoardsName", None),
        "socs": getattr(r, "socs", []),
        "deviceType": getattr(r, "deviceType", None),
        "deviceVariant": getattr(r, "deviceVariant", None),
        "modemVersion": getattr(r, "modemVersion", None),
        "hasModemFirmware": bool(getattr(r, "modemStorageKey", None)),
        "snrLength": getattr(r, "snrLength", None),
        "status": r.status,
        "notes": r.notes,
        "createdById": getattr(r, "createdById", None),
        "createdAt": r.createdAt.isoformat(),
        "updatedAt": r.updatedAt.isoformat(),
    }
    if hasattr(r, "targets") and r.targets is not None:
        result["targets"] = [_serialize_target(t) for t in r.targets]
    else:
        result["targets"] = []
    if hasattr(r, "modemFirmwares") and r.modemFirmwares is not None:
        result["modemFirmwares"] = [_serialize_modem_firmware(fw) for fw in r.modemFirmwares]
    return result


# ── Board Revisions CRUD ─────────────────────────────────


@require_permissions(Permissions.PRODUCTS_VIEW)
def get_board_revision(product_id: str, board_id: str, revision_id: str):
    """GET /v2/products/<pid>/boards/<bid>/revisions/<rid> — get a single revision."""
    db = get_db_client()
    revision = db.boardrevision.find_first(
        where={"id": revision_id, "boardId": board_id},
        include={"targets": True, "board": True},
    )
    if not revision:
        return not_found("Board revision not found")
    if revision.board and revision.board.productId != product_id:
        return not_found("Board revision not found")
    return jsonify(ApiResponse.ok(_serialize_revision(revision)).to_dict()), 200


@require_permissions(Permissions.PRODUCTS_MANAGE)
def create_board_revision(product_id: str, board_id: str):
    """POST — create a new board revision under a board."""
    db = get_db_client()

    # Validate board exists and belongs to product
    board = db.board.find_first(
        where={"id": board_id, "productId": product_id}
    )
    if not board:
        return not_found("Board not found")

    data, error = BoardRevisionCreateRequest.from_json(request.get_json())
    if error or data is None:
        return bad_request(error)

    existing = db.boardrevision.find_first(
        where={"boardId": board_id, "version": data.version}
    )
    if existing:
        return conflict(f"Board revision '{data.version}' already exists for this board")

    # Check ckBoardsName uniqueness across all revisions
    existing_ck = db.boardrevision.find_first(
        where={"ckBoardsName": data.ckBoardsName}
    )
    if existing_ck:
        return conflict(f"Board revision with ckBoardsName '{data.ckBoardsName}' already exists")

    create_data: Dict[str, Any] = {
        "boardId": board_id,
        "version": data.version,
        "ckBoardsName": data.ckBoardsName,
        "socs": data.socs,
        "status": data.status,
        "notes": data.notes,
    }
    if data.deviceType is not None:
        create_data["deviceType"] = data.deviceType
    if data.deviceVariant is not None:
        create_data["deviceVariant"] = data.deviceVariant
    if data.snrLength is not None:
        create_data["snrLength"] = data.snrLength

    user = getattr(g, "current_user", None)
    if user and isinstance(user, dict):
        create_data["createdById"] = user.get("sub")

    revision = db.boardrevision.create(
        data=create_data,
        include={"targets": True},
    )

    log_audit("boardRevision.create", "BoardRevision", revision.id, {
        "boardName": board.name, "version": data.version, "status": data.status,
    })
    return jsonify(ApiResponse.ok(_serialize_revision(revision)).to_dict()), 201


@require_permissions(Permissions.PRODUCTS_MANAGE)
def update_board_revision(product_id: str, board_id: str, revision_id: str):
    """PUT — update a board revision's properties and cascade status changes."""
    db = get_db_client()

    # Validate board exists and belongs to product
    board = db.board.find_first(
        where={"id": board_id, "productId": product_id}
    )
    if not board:
        return not_found("Board not found")

    revision = db.boardrevision.find_first(
        where={"id": revision_id, "boardId": board_id},
    )
    if not revision:
        return not_found("Board revision not found")

    data, error = BoardRevisionUpdateRequest.from_json(request.get_json())
    if error or data is None:
        return bad_request(error)

    if data.version and data.version != revision.version:
        dup = db.boardrevision.find_first(
            where={"boardId": board_id, "version": data.version}
        )
        if dup:
            return conflict(f"Board revision '{data.version}' already exists for this board")

    update_data = data.to_update_data()
    if update_data:
        db.boardrevision.update(
            where={"id": revision_id},
            data=update_data,
        )

    # Cascade: when status changes to DEPRECATED or EOL, disable all linked stage configs
    disabled_stages = []
    new_status = update_data.get("status")
    if new_status in ("DEPRECATED", "EOL"):
        active_configs = db.productstageconfig.find_many(
            where={"boardRevisionId": revision_id, "enabled": True},
        )
        if active_configs:
            db.productstageconfig.update_many(
                where={"boardRevisionId": revision_id, "enabled": True},
                data={"enabled": False},
            )
            disabled_stages = [{"stage": c.stage, "name": c.name} for c in active_configs]
            log_audit("boardRevision.cascadeDisable", "ProductStageConfig", revision_id, {
                "reason": f"Board revision {revision.version} set to {new_status}",
                "disabledStages": disabled_stages,
            })

    # Re-fetch
    updated = db.boardrevision.find_unique(
        where={"id": revision_id},
        include={"targets": True},
    )

    result = _serialize_revision(updated)
    if disabled_stages:
        result["disabledStages"] = disabled_stages

    log_audit("boardRevision.update", "BoardRevision", revision_id, {
        "version": revision.version, "changes": update_data,
    })
    return jsonify(ApiResponse.ok(result).to_dict()), 200


@require_permissions(Permissions.PRODUCTS_MANAGE)
def delete_board_revision(product_id: str, board_id: str, revision_id: str):
    """DELETE — remove a board revision and its targets."""
    db = get_db_client()

    # Validate board exists and belongs to product
    board = db.board.find_first(
        where={"id": board_id, "productId": product_id}
    )
    if not board:
        return not_found("Board not found")

    revision = db.boardrevision.find_first(
        where={"id": revision_id, "boardId": board_id}
    )
    if not revision:
        return not_found("Board revision not found")

    # Check for referencing models before deletion
    stage_configs = db.productstageconfig.count(where={"boardRevisionId": revision_id})
    if stage_configs > 0:
        return conflict(f"Cannot delete — {stage_configs} stage config(s) reference this revision")

    fixtures = db.fixture.count(where={"boardRevisionId": revision_id})
    if fixtures > 0:
        return conflict(f"Cannot delete — {fixtures} fixture(s) reference this revision")

    asset_sets = db.assetset.count(where={"boardRevisionId": revision_id})
    if asset_sets > 0:
        return conflict(f"Cannot delete — {asset_sets} asset set(s) reference this revision")

    test_runs = db.testrun.count(where={"boardRevisionId": revision_id})
    if test_runs > 0:
        return conflict(f"Cannot delete — {test_runs} test run(s) reference this revision")

    modem_fws = db.modemfirmware.count(where={"boardRevisionId": revision_id})
    if modem_fws > 0:
        return conflict(f"Cannot delete — {modem_fws} modem firmware(s) reference this revision. Delete them first.")

    db.boardrevision.delete(where={"id": revision_id})
    log_audit("boardRevision.delete", "BoardRevision", revision_id, {
        "version": revision.version,
    })
    return jsonify(ApiResponse.ok({"deleted": True}).to_dict()), 200


# ── Product Targets CRUD ─────────────────────────────────


@require_permissions(Permissions.PRODUCTS_MANAGE)
def create_target(product_id: str, board_id: str, revision_id: str):
    """POST — add a product target (processor role + appId) to a revision."""
    db = get_db_client()

    board = db.board.find_first(where={"id": board_id, "productId": product_id})
    if not board:
        return not_found("Board not found")

    revision = db.boardrevision.find_first(
        where={"id": revision_id, "boardId": board_id},
        include={"targets": True},
    )
    if not revision:
        return not_found("Board revision not found")

    data, error = TargetCreateRequest.from_json(request.get_json())
    if error or data is None:
        return bad_request(error)

    # Check role uniqueness within this revision
    for t in (revision.targets or []):
        if t.role == data.role:
            return conflict(f"Target with role '{data.role}' already exists on this revision")
        if t.appId == data.appId:
            return conflict(f"Target with appId {data.appId} already exists on this revision")

    target = db.producttarget.create(
        data={
            "boardRevisionId": revision_id,
            "role": data.role,
            "soc": data.soc,
            "appId": data.appId,
        },
    )

    log_audit("productTarget.create", "ProductTarget", target.id, {
        "revisionId": revision_id, "role": data.role, "soc": data.soc, "appId": data.appId,
    })
    return jsonify(ApiResponse.ok(_serialize_target(target)).to_dict()), 201


@require_permissions(Permissions.PRODUCTS_MANAGE)
def update_target(product_id: str, board_id: str, revision_id: str, target_id: str):
    """PUT — update a product target's role, soc, or appId."""
    db = get_db_client()

    board = db.board.find_first(where={"id": board_id, "productId": product_id})
    if not board:
        return not_found("Board not found")

    revision = db.boardrevision.find_first(
        where={"id": revision_id, "boardId": board_id},
        include={"targets": True},
    )
    if not revision:
        return not_found("Board revision not found")

    target = None
    for t in (revision.targets or []):
        if t.id == target_id:
            target = t
            break
    if not target:
        return not_found("Target not found on this revision")

    data, error = TargetUpdateRequest.from_json(request.get_json())
    if error or data is None:
        return bad_request(error)

    # Check uniqueness constraints for role and appId changes
    if data._has_role and data.role and data.role != target.role:
        for t in (revision.targets or []):
            if t.id != target_id and t.role == data.role:
                return conflict(f"Target with role '{data.role}' already exists on this revision")
    if data._has_app_id and data.appId is not None and data.appId != target.appId:
        for t in (revision.targets or []):
            if t.id != target_id and t.appId == data.appId:
                return conflict(f"Target with appId {data.appId} already exists on this revision")

    update_data = data.to_update_data()
    updated = db.producttarget.update(
        where={"id": target_id},
        data=update_data,
    )

    log_audit("productTarget.update", "ProductTarget", target_id, {
        "revisionId": revision_id, "changes": update_data,
    })
    return jsonify(ApiResponse.ok(_serialize_target(updated)).to_dict()), 200


@require_permissions(Permissions.PRODUCTS_MANAGE)
def delete_target(product_id: str, board_id: str, revision_id: str, target_id: str):
    """DELETE — remove a product target from a revision."""
    db = get_db_client()

    board = db.board.find_first(where={"id": board_id, "productId": product_id})
    if not board:
        return not_found("Board not found")

    revision = db.boardrevision.find_first(
        where={"id": revision_id, "boardId": board_id},
        include={"targets": True},
    )
    if not revision:
        return not_found("Board revision not found")

    found = False
    for t in (revision.targets or []):
        if t.id == target_id:
            found = True
            break
    if not found:
        return not_found("Target not found on this revision")

    db.producttarget.delete(where={"id": target_id})
    log_audit("productTarget.delete", "ProductTarget", target_id, {
        "revisionId": revision_id,
    })
    return jsonify(ApiResponse.ok({"deleted": True}).to_dict()), 200


# ── Modem Firmware Management ──────────────────────────────


def _validate_revision_access(db, product_id: str, board_id: str, revision_id: str):
    """Validate board+revision belong to product. Returns (revision, error_response)."""
    board = db.board.find_first(where={"id": board_id, "productId": product_id})
    if not board:
        return None, not_found("Board not found")
    revision = db.boardrevision.find_first(
        where={"id": revision_id, "boardId": board_id},
    )
    if not revision:
        return None, not_found("Board revision not found")
    return revision, None


def _validate_revision(db, product_id: str, revision_id: str):
    """Validate revision belongs to product (via board). Returns (revision, error_response)."""
    revision = db.boardrevision.find_unique(
        where={"id": revision_id},
        include={"board": True},
    )
    if not revision or not revision.board or revision.board.productId != product_id:
        return None, not_found("Board revision not found")
    return revision, None


def _serialize_modem_firmware(fw) -> dict:
    """Serialize a ModemFirmware record to an API response dict."""
    return {
        "id": fw.id,
        "boardRevisionId": fw.boardRevisionId,
        "version": fw.version,
        "filename": fw.filename,
        "storageKey": fw.storageKey,
        "sizeBytes": fw.sizeBytes,
        "checksum": fw.checksum,
        "notes": fw.notes,
        "createdById": fw.createdById,
        "createdAt": fw.createdAt.isoformat() if fw.createdAt else None,
    }


@require_permissions(Permissions.PRODUCTS_VIEW)
def list_modem_firmwares(product_id: str, revision_id: str):
    """GET /v2/products/<pid>/revisions/<rid>/modem-firmware

    List all modem firmware versions for a board revision, newest first.
    """
    db = get_db_client()
    revision, err = _validate_revision(db, product_id, revision_id)
    if err:
        return err

    firmwares = db.modemfirmware.find_many(
        where={"boardRevisionId": revision_id},
        order={"createdAt": "desc"},
    )

    return jsonify(ApiResponse.ok(
        [_serialize_modem_firmware(fw) for fw in firmwares]
    ).to_dict()), 200


@require_permissions(Permissions.PRODUCTS_MANAGE)
def upload_modem_firmware(product_id: str, revision_id: str):
    """POST /v2/products/<pid>/revisions/<rid>/modem-firmware

    Upload modem firmware for a board revision. Creates a new ModemFirmware
    record. Version is auto-extracted from the filename. Duplicate filenames
    for the same revision are rejected.
    """
    db = get_db_client()
    revision, err = _validate_revision(db, product_id, revision_id)
    if err:
        return err

    if "file" not in request.files:
        return bad_request("No file provided. Use multipart form with 'file' field.")

    file = request.files["file"]
    if not file.filename:
        return bad_request("File has no filename")

    if not file.filename.endswith(".zip"):
        return bad_request("Only .zip files are accepted for modem firmware")

    filename = file.filename.strip()

    # Auto-extract version from filename (e.g., "mfw_nrf91x1_2.0.2.zip" → "2.0.2")
    version = request.form.get("version", "").strip()
    if not version:
        match = re.search(r"(\d+\.\d+\.\d+)", filename)
        version = match.group(1) if match else filename.rsplit(".", 1)[0]

    notes = request.form.get("notes", "").strip() or None

    # Check uniqueness by filename
    existing = db.modemfirmware.find_first(
        where={"boardRevisionId": revision_id, "filename": filename}
    )
    if existing:
        return conflict(f"Modem firmware '{filename}' already exists for this revision")

    try:
        content = file.read()
        if len(content) == 0:
            return bad_request("Uploaded file is empty")

        checksum = hashlib.sha256(content).hexdigest()

        # Store in MinIO — resolve product slug for path
        product = db.product.find_unique(where={"id": product_id})
        key = modem_firmware_key(
            product_slug=getattr(product, "slug", None) if product else None,
            revision_version=revision.version,
            modem_version=version,
            filename=file.filename,
        )
        client = get_storage_client()
        bucket = get_bucket_name()

        client.put_object(
            bucket_name=bucket,
            object_name=key,
            data=BytesIO(content),
            length=len(content),
            content_type="application/octet-stream",
        )

        # Create ModemFirmware record
        user_id = g.current_user.get("sub") if hasattr(g, "current_user") and g.current_user else None
        create_data: Dict[str, Any] = {
            "boardRevisionId": revision_id,
            "version": version,
            "filename": file.filename,
            "storageKey": key,
            "sizeBytes": len(content),
            "checksum": checksum,
            "notes": notes,
        }
        if user_id:
            create_data["createdById"] = user_id

        fw = db.modemfirmware.create(data=create_data)

        # Update BoardRevision legacy fields for backward compat
        db.boardrevision.update(
            where={"id": revision_id},
            data={
                "modemVersion": version,
                "modemStorageKey": key,
            },
        )

        log_audit("modemFirmware.upload", "ModemFirmware", fw.id, {
            "revisionId": revision_id, "version": version,
            "filename": file.filename, "sizeBytes": len(content),
        })

        return jsonify(ApiResponse.ok(_serialize_modem_firmware(fw)).to_dict()), 201

    except Exception as e:
        logger.error("Failed to upload modem firmware for revision %s: %s", revision_id, e)
        return internal_error("Failed to upload modem firmware")


@require_permissions(Permissions.PRODUCTS_MANAGE)
def delete_modem_firmware(product_id: str, revision_id: str, fw_id: str):
    """DELETE /v2/products/<pid>/revisions/<rid>/modem-firmware/<fwId>

    Delete a specific modem firmware version. Blocks if referenced by any AssetSet.
    """
    db = get_db_client()
    revision, err = _validate_revision(db, product_id, revision_id)
    if err:
        return err

    fw = db.modemfirmware.find_first(
        where={"id": fw_id, "boardRevisionId": revision_id},
    )
    if not fw:
        return not_found("Modem firmware not found")

    # Block deletion if referenced by any asset set
    referencing = db.assetset.count(where={"modemFirmwareId": fw_id})
    if referencing > 0:
        return conflict(
            f"Cannot delete modem firmware v{fw.version}: referenced by {referencing} asset set(s)"
        )

    # Remove from MinIO
    try:
        client = get_storage_client()
        bucket = get_bucket_name()
        client.remove_object(bucket, fw.storageKey)
    except Exception:
        pass

    db.modemfirmware.delete(where={"id": fw_id})

    # If this was the latest, update legacy fields to next most recent or clear
    if getattr(revision, "modemStorageKey", None) == fw.storageKey:
        next_fw = db.modemfirmware.find_first(
            where={"boardRevisionId": revision_id},
            order={"createdAt": "desc"},
        )
        db.boardrevision.update(
            where={"id": revision_id},
            data={
                "modemVersion": next_fw.version if next_fw else None,
                "modemStorageKey": next_fw.storageKey if next_fw else None,
            },
        )

    log_audit("modemFirmware.delete", "ModemFirmware", fw_id, {
        "revisionId": revision_id, "version": fw.version,
    })

    return jsonify(ApiResponse.ok({"deleted": True}).to_dict()), 200
