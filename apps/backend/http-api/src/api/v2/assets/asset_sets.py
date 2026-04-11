"""Asset set endpoints — unified firmware asset containers.

CRUD for asset sets that hold firmware artifacts from build service,
manual uploads, or external CI. Validation sessions link to an asset
set to track which firmware they consumed.
"""

import logging
from typing import Optional

from flask import g, jsonify, request

from src.lib.audit import log_audit
from src.lib.decorators import require_permissions
from src.lib.errors import bad_request, not_found
from src.lib.permissions import Permissions
from src.lib.types import ApiResponse
from src.services.database.prisma import get_db_client

from .types import AssetSetCreateRequest, ExternalAssetSetCreateRequest

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Status transition validation
# ---------------------------------------------------------------------------

_VALID_ASSET_SET_TRANSITIONS = {
    "PENDING": {"COMPLETE", "FAILED"},
    "COMPLETE": {"VALIDATED", "FAILED"},
    "VALIDATED": set(),
    "FAILED": set(),
}


def _validate_asset_set_transition(current: str, target: str) -> Optional[str]:
    """Return error message if transition is invalid, None if OK."""
    allowed = _VALID_ASSET_SET_TRANSITIONS.get(current, set())
    if target not in allowed:
        return f"Cannot transition asset set from '{current}' to '{target}'"
    return None

_ASSET_SET_INCLUDE = {
    "product": True,
    "boardRevision": True,
    "buildRun": True,
    "createdBy": True,
    "assets": True,
    "modemFirmware": True,
}


def _serialize_asset(asset) -> dict:
    """Serialize an Asset DB record to an API response dict."""
    return {
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
    }


def _serialize_asset_set(asset_set) -> dict:
    """Serialize an AssetSet DB record to an API response dict."""
    data = {
        "id": asset_set.id,
        "productId": asset_set.productId,
        "boardRevisionId": asset_set.boardRevisionId,
        "version": asset_set.version,
        "variant": asset_set.variant,
        "stage": asset_set.stage,
        "stageType": getattr(asset_set, "stageType", None),
        "source": asset_set.source,
        "buildRunId": asset_set.buildRunId,
        "externalBuildId": asset_set.externalBuildId,
        "commitSha": asset_set.commitSha,
        "branch": asset_set.branch,
        "recipeVersionId": asset_set.recipeVersionId,
        "modemFirmwareId": getattr(asset_set, "modemFirmwareId", None),
        "status": asset_set.status,
        "notes": asset_set.notes,
        "createdById": asset_set.createdById,
        "createdAt": asset_set.createdAt.isoformat() if hasattr(asset_set.createdAt, "isoformat") else asset_set.createdAt,
        "updatedAt": asset_set.updatedAt.isoformat() if hasattr(asset_set.updatedAt, "isoformat") else asset_set.updatedAt,
    }
    if hasattr(asset_set, "product") and asset_set.product:
        data["product"] = {"id": asset_set.product.id, "name": asset_set.product.name, "slug": asset_set.product.slug}
    if hasattr(asset_set, "boardRevision") and asset_set.boardRevision:
        data["boardRevision"] = {
            "id": asset_set.boardRevision.id,
            "version": asset_set.boardRevision.version,
            "ckBoardsName": asset_set.boardRevision.ckBoardsName,
        }
    else:
        data["boardRevision"] = None
    if hasattr(asset_set, "createdBy") and asset_set.createdBy:
        data["createdBy"] = {"id": asset_set.createdBy.id, "name": asset_set.createdBy.name}
    else:
        data["createdBy"] = None
    if hasattr(asset_set, "assets") and asset_set.assets:
        data["assets"] = [_serialize_asset(a) for a in asset_set.assets]
    else:
        data["assets"] = []

    if hasattr(asset_set, "modemFirmware") and asset_set.modemFirmware:
        mf = asset_set.modemFirmware
        data["modemFirmware"] = {
            "id": mf.id,
            "version": mf.version,
            "filename": mf.filename,
            "storageKey": mf.storageKey,
            "sizeBytes": mf.sizeBytes,
        }
    else:
        data["modemFirmware"] = None

    return data


@require_permissions(Permissions.BUILDS_VIEW)
def list_asset_sets(product_id: str):
    """GET /products/<id>/asset-sets — list asset sets for a product."""
    db = get_db_client()
    product = db.product.find_unique(where={"id": product_id})
    if not product:
        return not_found("Product not found")

    page = max(1, request.args.get("page", 1, type=int))
    limit = min(max(1, request.args.get("limit", 50, type=int)), 100)
    skip = (page - 1) * limit

    where = {"productId": product_id}

    # Optional filters
    stage = request.args.get("stage", type=int)
    if stage is not None:
        where["stage"] = stage
    status = request.args.get("status")
    if status:
        where["status"] = status.upper()
    source = request.args.get("source")
    if source:
        where["source"] = source.upper()
    board_revision_id = request.args.get("boardRevisionId")
    if board_revision_id:
        where["boardRevisionId"] = board_revision_id
    stage_config_id = request.args.get("stageConfigId")
    if stage_config_id:
        # stageConfigId is not a field on AssetSet — look up the stage number
        sc = db.productstageconfig.find_unique(where={"id": stage_config_id})
        if sc:
            where["stage"] = sc.stage

    total = db.assetset.count(where=where)
    asset_sets = db.assetset.find_many(
        where=where,
        include=_ASSET_SET_INCLUDE,
        order={"createdAt": "desc"},
        skip=skip,
        take=limit,
    )

    pages = (total + limit - 1) // limit if total > 0 else 0
    return jsonify(ApiResponse.paginated(
        data=[_serialize_asset_set(a) for a in asset_sets],
        page=page,
        total_pages=pages,
        total_results=total,
        results_per_page=limit,
    ).to_dict()), 200


@require_permissions(Permissions.BUILDS_MANAGE)
def create_asset_set(product_id: str):
    """POST /products/<id>/asset-sets — create a new asset set (manual or build service)."""
    db = get_db_client()
    product = db.product.find_unique(where={"id": product_id})
    if not product:
        return not_found("Product not found")

    req, err = AssetSetCreateRequest.from_json(request.get_json())
    if err or req is None:
        return bad_request(err)

    create_data: dict = {
        "product": {"connect": {"id": product_id}},
        "version": req.version,
        "variant": req.variant,
        "source": req.source,
        "stage": req.stage,
    }
    if req.boardRevisionId:
        rev = db.boardrevision.find_unique(
            where={"id": req.boardRevisionId},
            include={"board": True},
        )
        if not rev:
            return not_found("Board revision not found")
        if rev.board and rev.board.productId != product_id:
            return bad_request("Board revision does not belong to this product")
        create_data["boardRevision"] = {"connect": {"id": req.boardRevisionId}}
    if req.commitSha:
        create_data["commitSha"] = req.commitSha
    if req.branch:
        create_data["branch"] = req.branch
    if req.recipeVersionId:
        create_data["recipeVersion"] = {"connect": {"id": req.recipeVersionId}}
    if req.notes:
        create_data["notes"] = req.notes

    # Derive boardRevisionId and stageType from stageConfig
    if req.stageConfigId:
        sc = db.productstageconfig.find_unique(where={"id": req.stageConfigId})
        if sc:
            create_data["stageType"] = sc.type
            if not req.boardRevisionId and sc.boardRevisionId:
                create_data["boardRevisionId"] = sc.boardRevisionId

    user = getattr(g, "current_user", None)
    if user and isinstance(user, dict):
        create_data["createdById"] = user.get("userId")

    asset_set = db.assetset.create(data=create_data, include=_ASSET_SET_INCLUDE)
    log_audit("assetSet.create", "AssetSet", asset_set.id, {"version": req.version, "source": req.source})
    return jsonify(ApiResponse.ok(_serialize_asset_set(asset_set)).to_dict()), 201


@require_permissions(Permissions.BUILDS_MANAGE)
def create_external_asset_set(product_id: str):
    """POST /products/<id>/asset-sets/external — create asset set from external CI."""
    db = get_db_client()
    product = db.product.find_unique(where={"id": product_id})
    if not product:
        return not_found("Product not found")

    req, err = ExternalAssetSetCreateRequest.from_json(request.get_json())
    if err or req is None:
        return bad_request(err)

    create_data: dict = {
        "product": {"connect": {"id": product_id}},
        "version": req.version,
        "variant": req.variant,
        "source": "EXTERNAL_CI",
        "externalBuildId": req.externalBuildId,
        "stage": req.stage,
    }
    board_rev_id = req.boardRevisionId
    if req.stageConfigId:
        sc = db.productstageconfig.find_unique(where={"id": req.stageConfigId})
        if sc:
            create_data["stageType"] = sc.type
            if not board_rev_id and sc.boardRevisionId:
                board_rev_id = sc.boardRevisionId
    if board_rev_id:
        create_data["boardRevision"] = {"connect": {"id": board_rev_id}}
    if req.commitSha:
        create_data["commitSha"] = req.commitSha
    if req.branch:
        create_data["branch"] = req.branch
    if req.notes:
        create_data["notes"] = req.notes

    user = getattr(g, "current_user", None)
    if user and isinstance(user, dict) and user.get("userId"):
        create_data["createdBy"] = {"connect": {"id": user["userId"]}}

    asset_set = db.assetset.create(data=create_data, include=_ASSET_SET_INCLUDE)
    log_audit("assetSet.createExternal", "AssetSet", asset_set.id, {
        "version": req.version,
        "externalBuildId": req.externalBuildId,
    })
    return jsonify(ApiResponse.ok(_serialize_asset_set(asset_set)).to_dict()), 201


@require_permissions(Permissions.BUILDS_VIEW)
def get_asset_set(asset_set_id: str):
    """GET /asset-sets/<id> — get a single asset set with all assets."""
    db = get_db_client()
    asset_set = db.assetset.find_unique(where={"id": asset_set_id}, include=_ASSET_SET_INCLUDE)
    if not asset_set:
        return not_found("Asset set not found")
    return jsonify(ApiResponse.ok(_serialize_asset_set(asset_set)).to_dict()), 200


@require_permissions(Permissions.BUILDS_MANAGE)
def complete_asset_set(asset_set_id: str):
    """POST /asset-sets/<id>/complete — mark asset set as complete.

    If the asset set is linked to a stage config, validates that uploaded
    assets cover the required build matrix labels. Returns warnings for
    missing labels but does not block completion.
    """
    db = get_db_client()
    asset_set = db.assetset.find_unique(
        where={"id": asset_set_id},
        include={"assets": True},
    )
    if not asset_set:
        return not_found("Asset set not found")

    err = _validate_asset_set_transition(asset_set.status, "COMPLETE")
    if err:
        return bad_request(err)

    # Validate against build matrix if stage is set
    warnings = []
    if asset_set.stage and asset_set.productId:
        stage_config = db.productstageconfig.find_first(
            where={"productId": asset_set.productId, "stage": asset_set.stage},
            include={"buildMatrixEntries": True},
        )
        if stage_config and stage_config.buildMatrixEntries:
            required = {e.label for e in stage_config.buildMatrixEntries}
            present = {a.label for a in (asset_set.assets or [])}
            missing = required - present
            if missing:
                warnings.append(f"Missing labels: {', '.join(sorted(missing))}")

    updated = db.assetset.update(
        where={"id": asset_set_id},
        data={"status": "COMPLETE"},
        include=_ASSET_SET_INCLUDE,
    )
    log_audit("assetSet.complete", "AssetSet", asset_set_id, {"status": "COMPLETE", "warnings": warnings})

    result = _serialize_asset_set(updated)
    if warnings:
        result["warnings"] = warnings
    return jsonify(ApiResponse.ok(result).to_dict()), 200


@require_permissions(Permissions.BUILDS_MANAGE)
def delete_asset_set(asset_set_id: str):
    """DELETE /asset-sets/<id> — delete an asset set and all its assets."""
    db = get_db_client()
    asset_set = db.assetset.find_unique(where={"id": asset_set_id})
    if not asset_set:
        return not_found("Asset set not found")

    # Check if any test runs reference this asset set
    linked_runs = db.testrun.count(where={"assetSetId": asset_set_id})
    if linked_runs > 0:
        return bad_request(f"Cannot delete — {linked_runs} run(s) reference this asset set")

    # Check if any manufacturing sessions reference this asset set
    linked_sessions = db.manufacturingsession.count(
        where={"assetSetId": asset_set_id}
    )
    if linked_sessions > 0:
        return bad_request(f"Cannot delete — {linked_sessions} manufacturing session(s) reference this asset set")

    db.assetset.delete(where={"id": asset_set_id})
    log_audit("assetSet.delete", "AssetSet", asset_set_id, {"version": asset_set.version})
    return jsonify(ApiResponse.ok({"deleted": True}).to_dict()), 200


@require_permissions(Permissions.BUILDS_VIEW)
def get_latest_asset_set():
    """GET /asset-sets/latest?stageConfigId=X&status=COMPLETE — latest asset set for a stage config."""
    db = get_db_client()

    stage_config_id = request.args.get("stageConfigId")
    product_id = request.args.get("productId")
    stage = request.args.get("stage")

    where: dict = {}
    if stage_config_id:
        # Look up stage number from config
        sc = db.productstageconfig.find_unique(where={"id": stage_config_id})
        if sc:
            where["productId"] = sc.productId
            where["stage"] = sc.stage
    elif product_id and stage:
        where["productId"] = product_id
        where["stage"] = int(stage)
    else:
        return bad_request("stageConfigId or (productId + stage) is required")
    status = request.args.get("status", "COMPLETE").upper()
    where["status"] = status

    asset_set = db.assetset.find_first(
        where=where,
        order={"createdAt": "desc"},
        include=_ASSET_SET_INCLUDE,
    )
    if not asset_set:
        return not_found("No asset set found for this stage config")

    return jsonify(ApiResponse.ok(_serialize_asset_set(asset_set)).to_dict()), 200


@require_permissions(Permissions.BUILDS_VIEW)
def download_asset_set_zip(asset_set_id: str):
    """GET /asset-sets/<id>/download — download all files in an asset set as a .zip archive."""
    import io
    import re
    import zipfile

    from flask import Response
    from src.services.storage.client import get_storage_client

    db = get_db_client()
    asset_set = db.assetset.find_unique(
        where={"id": asset_set_id},
        include={"assets": True},
    )
    if not asset_set:
        return not_found("Asset set not found")

    assets = asset_set.assets or []
    if not assets:
        return not_found("Asset set has no files")

    storage = get_storage_client()
    zip_buffer = io.BytesIO()

    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for asset in assets:
            if not asset.storageKey:
                continue
            try:
                response = storage.get_object("concord", asset.storageKey)
                file_data = response.read()
                response.close()
                response.release_conn()

                # Use the original filename, sanitized
                filename = re.sub(r'[^a-zA-Z0-9._-]', '_', asset.filename or asset.label)
                zf.writestr(filename, file_data)
            except Exception as e:
                logger.warning("Failed to fetch %s for zip: %s", asset.storageKey, e)

    zip_buffer.seek(0)
    zip_data = zip_buffer.read()

    version = asset_set.version or "unknown"
    variant = asset_set.variant or "default"
    safe_version = re.sub(r'[^a-zA-Z0-9._-]', '_', version)
    safe_variant = re.sub(r'[^a-zA-Z0-9._-]', '_', variant)
    zip_filename = f"asset-set-{safe_version}-{safe_variant}.zip"

    return Response(
        zip_data,
        mimetype="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{zip_filename}"',
            "Content-Length": str(len(zip_data)),
        },
    )
