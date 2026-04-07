"""Product stage configuration endpoints — CRUD for validation stage configs.

Thin config: which revision, which branch, which signing key.
Test config lives in the test repo. Build recipes are convention-driven.
"""

import logging
from flask import jsonify, request

from src.lib.audit import log_audit
from src.lib.decorators import require_permissions
from src.lib.errors import bad_request, conflict, not_found
from src.lib.permissions import Permissions
from src.lib.types import ApiResponse
from src.services.database.prisma import get_db_client

from .stage_config_types import StageConfigCreateRequest, StageConfigUpdateRequest

logger = logging.getLogger(__name__)

DEFAULT_STAGES = [
    {"stage": 1, "name": "Smoke"},
    {"stage": 2, "name": "Driver"},
    {"stage": 3, "name": "Integration"},
    {"stage": 4, "name": "Regression"},
    {"stage": 5, "name": "FUOTA"},
]

_INCLUDE = {"boardRevision": True, "signingKey": True, "buildMatrixEntries": True}


def _serialize_stage_config(cfg) -> dict:
    """Serialize a ProductStageConfig DB record to an API response dict."""
    data = {
        "id": cfg.id,
        "productId": cfg.productId,
        "stage": cfg.stage,
        "name": cfg.name,
        "enabled": cfg.enabled,
        "boardRevisionId": cfg.boardRevisionId,
        "watchBranch": cfg.watchBranch,
        "triggerTypes": getattr(cfg, "triggerTypes", "manual"),
        "signingKeyId": cfg.signingKeyId,
        "createdAt": cfg.createdAt.isoformat() if hasattr(cfg.createdAt, 'isoformat') else cfg.createdAt,
        "updatedAt": cfg.updatedAt.isoformat() if hasattr(cfg.updatedAt, 'isoformat') else cfg.updatedAt,
    }
    if hasattr(cfg, "boardRevision") and cfg.boardRevision:
        data["boardRevision"] = {
            "id": cfg.boardRevision.id,
            "version": cfg.boardRevision.version,
            "ckBoardsName": cfg.boardRevision.ckBoardsName,
        }
    else:
        data["boardRevision"] = None
    if hasattr(cfg, "signingKey") and cfg.signingKey:
        data["signingKey"] = {
            "id": cfg.signingKey.id,
            "name": cfg.signingKey.name,
            "type": cfg.signingKey.type,
        }
    else:
        data["signingKey"] = None
    if hasattr(cfg, "buildMatrixEntries") and cfg.buildMatrixEntries:
        data["buildMatrix"] = [
            _serialize_build_matrix_entry(e)
            for e in sorted(cfg.buildMatrixEntries, key=lambda x: x.sortOrder)
        ]
    return data


@require_permissions(Permissions.BUILDS_VIEW)
def list_stage_configs(product_id: str):
    """List all stage configs for a product."""
    db = get_db_client()
    product = db.product.find_unique(where={"id": product_id})
    if not product:
        return not_found("Product not found")
    configs = db.productstageconfig.find_many(
        where={"productId": product_id},
        order={"stage": "asc"},
        include=_INCLUDE,
    )
    return jsonify(ApiResponse.ok([_serialize_stage_config(c) for c in configs]).to_dict()), 200


@require_permissions(Permissions.BUILDS_VIEW)
def get_stage_config(product_id: str, stage: str):
    """Get a single stage config by product and stage number."""
    db = get_db_client()
    product = db.product.find_unique(where={"id": product_id})
    if not product:
        return not_found("Product not found")
    try:
        stage_num = int(stage)
    except ValueError:
        return bad_request("Stage must be a number")
    config = db.productstageconfig.find_first(
        where={"productId": product_id, "stage": stage_num},
        include=_INCLUDE,
    )
    if not config:
        return not_found(f"Stage {stage} config not found")
    return jsonify(ApiResponse.ok(_serialize_stage_config(config)).to_dict()), 200


@require_permissions(Permissions.BUILDS_MANAGE)
def create_stage_config(product_id: str):
    """Create a new stage config for a product."""
    db = get_db_client()
    product = db.product.find_unique(where={"id": product_id})
    if not product:
        return not_found("Product not found")
    req, err = StageConfigCreateRequest.from_json(request.get_json())
    if err or req is None:
        return bad_request(err)
    existing = db.productstageconfig.find_first(
        where={"productId": product_id, "stage": req.stage, "boardRevisionId": req.boardRevisionId}
    )
    if existing:
        return conflict(f"Stage {req.stage} already exists for this product and revision")
    # Block creating enabled stages for deprecated/EOL revisions
    if req.enabled and req.boardRevisionId:
        rev = db.boardrevision.find_unique(where={"id": req.boardRevisionId})
        if rev and rev.status in ("DEPRECATED", "EOL"):
            return bad_request(f"Cannot enable stage for {rev.status} revision {rev.version}")
    config = db.productstageconfig.create(
        data={
            "productId": product_id,
            "stage": req.stage,
            "name": req.name,
            "enabled": req.enabled,
            "boardRevisionId": req.boardRevisionId,
            "watchBranch": req.watchBranch,
            "triggerTypes": req.triggerTypes,
            "signingKeyId": req.signingKeyId,
        },
        include=_INCLUDE,
    )
    log_audit("stageConfig.create", "ProductStageConfig", config.id, {"stage": req.stage})
    return jsonify(ApiResponse.ok(_serialize_stage_config(config)).to_dict()), 201


@require_permissions(Permissions.BUILDS_MANAGE)
def update_stage_config(product_id: str, stage: str):
    """Update a stage config, optionally triggering a build."""
    db = get_db_client()
    product = db.product.find_unique(where={"id": product_id})
    if not product:
        return not_found("Product not found")
    try:
        stage_num = int(stage)
    except ValueError:
        return bad_request("Stage must be a number")
    config = db.productstageconfig.find_first(
        where={"productId": product_id, "stage": stage_num}
    )
    if not config:
        return not_found(f"Stage {stage} config not found")
    req, err = StageConfigUpdateRequest.from_json(request.get_json())
    if err or req is None:
        return bad_request(err)
    update_data = req.to_update_data()
    if not update_data:
        return bad_request("No fields to update")
    # Block enabling stages for deprecated/EOL revisions
    enabling = update_data.get("enabled", False)
    rev_id = update_data.get("boardRevisionId", config.boardRevisionId)
    if enabling and rev_id:
        rev = db.boardrevision.find_unique(where={"id": rev_id})
        if rev and rev.status in ("DEPRECATED", "EOL"):
            return bad_request(f"Cannot enable stage for {rev.status} revision {rev.version}")
    updated = db.productstageconfig.update(
        where={"id": config.id},
        data=update_data,
        include=_INCLUDE,
    )
    log_audit("stageConfig.update", "ProductStageConfig", config.id, update_data)

    result = _serialize_stage_config(updated)

    # If buildNow is requested and stage is being enabled, trigger builds
    raw_data = request.get_json() or {}
    if raw_data.get("buildNow") and updated.enabled:
        from src.services.build_trigger import trigger_stage_build
        try:
            trigger_result = trigger_stage_build(product_id, config.id)
            if trigger_result:
                result["buildTriggered"] = True
                result["buildRunId"] = trigger_result["buildRunId"]
                result["jobCount"] = trigger_result["jobCount"]
                logger.info("Build triggered for stage %s: %s", stage, trigger_result["buildRunId"])
            else:
                result["buildTriggered"] = False
                result["buildError"] = "Failed to trigger build — check product repos and revision config"
        except Exception as e:
            logger.error("Failed to trigger build for stage %s: %s", stage, e)
            result["buildTriggered"] = False
            result["buildError"] = str(e)

    return jsonify(ApiResponse.ok(result).to_dict()), 200


@require_permissions(Permissions.BUILDS_MANAGE)
def delete_stage_config(product_id: str, stage: str):
    """Delete a stage config by product and stage number."""
    db = get_db_client()
    product = db.product.find_unique(where={"id": product_id})
    if not product:
        return not_found("Product not found")
    try:
        stage_num = int(stage)
    except ValueError:
        return bad_request("Stage must be a number")
    config = db.productstageconfig.find_first(
        where={"productId": product_id, "stage": stage_num}
    )
    if not config:
        return not_found(f"Stage {stage} config not found")
    db.productstageconfig.delete(where={"id": config.id})
    log_audit("stageConfig.delete", "ProductStageConfig", config.id, {"stage": stage_num})
    return jsonify(ApiResponse.ok({"deleted": True}).to_dict()), 200


@require_permissions(Permissions.BUILDS_MANAGE)
def initialize_stages(product_id: str):
    """Create all five default stage configs for a product."""
    db = get_db_client()
    product = db.product.find_unique(where={"id": product_id})
    if not product:
        return not_found("Product not found")
    existing = db.productstageconfig.find_many(where={"productId": product_id})
    if existing:
        return conflict("Product already has stage configurations. Delete them first to reinitialize.")
    created = []
    for stage_def in DEFAULT_STAGES:
        config = db.productstageconfig.create(
            data={"productId": product_id, "enabled": False, **stage_def},
            include=_INCLUDE,
        )
        created.append(_serialize_stage_config(config))
    log_audit("stageConfig.initialize", "ProductStageConfig", product_id, {"stages": len(created)})
    return jsonify(ApiResponse.ok(created).to_dict()), 201


# =============================================================================
# Build Matrix — per-stage build definitions
# =============================================================================

def _serialize_build_matrix_entry(entry) -> dict:
    """Serialize a StageBuildMatrix entry to an API response dict."""
    return {
        "id": entry.id,
        "stageConfigId": entry.stageConfigId,
        "sortOrder": entry.sortOrder,
        "label": entry.label,
        "fwType": entry.fwType,
        "variant": entry.variant,
        "configLog": entry.configLog,
        "producesHex": entry.producesHex,
        "producesCfw": entry.producesCfw,
        "gitRef": entry.gitRef,
        "isVersionBump": entry.isVersionBump,
        "baseLabel": entry.baseLabel,
        "description": entry.description,
    }


@require_permissions(Permissions.BUILDS_VIEW)
def get_stage_build_matrix(product_id: str, stage: str):
    """GET /products/<id>/stages/<stage>/build-matrix — return build matrix for a stage."""
    db = get_db_client()
    product = db.product.find_unique(where={"id": product_id})
    if not product:
        return not_found("Product not found")
    try:
        stage_num = int(stage)
    except ValueError:
        return bad_request("Stage must be a number")
    config = db.productstageconfig.find_first(
        where={"productId": product_id, "stage": stage_num},
    )
    if not config:
        return not_found(f"Stage {stage} config not found")
    entries = db.stagebuildmatrix.find_many(
        where={"stageConfigId": config.id},
        order={"sortOrder": "asc"},
    )
    return jsonify(ApiResponse.ok([_serialize_build_matrix_entry(e) for e in entries]).to_dict()), 200


@require_permissions(Permissions.BUILDS_MANAGE)
def update_stage_build_matrix(product_id: str, stage: str):
    """PUT /products/<id>/stages/<stage>/build-matrix — replace build matrix entries."""
    db = get_db_client()
    product = db.product.find_unique(where={"id": product_id})
    if not product:
        return not_found("Product not found")
    try:
        stage_num = int(stage)
    except ValueError:
        return bad_request("Stage must be a number")
    config = db.productstageconfig.find_first(
        where={"productId": product_id, "stage": stage_num},
    )
    if not config:
        return not_found(f"Stage {stage} config not found")

    data = request.get_json()
    if not data or not isinstance(data.get("entries"), list):
        return bad_request("Request body must contain 'entries' array")

    entries = data["entries"]
    # Validate entries
    seen_labels = set()
    for i, entry in enumerate(entries):
        label = (entry.get("label") or "").strip()
        if not label:
            return bad_request(f"Entry {i}: label is required")
        if label in seen_labels:
            return bad_request(f"Entry {i}: duplicate label '{label}'")
        seen_labels.add(label)
        fw_type = (entry.get("fwType") or "").strip()
        if not fw_type:
            return bad_request(f"Entry {i}: fwType is required")
        variant = (entry.get("variant") or "").strip()
        if not variant:
            return bad_request(f"Entry {i}: variant is required")

    # Replace: delete old, create new
    db.stagebuildmatrix.delete_many(where={"stageConfigId": config.id})
    created = []
    for i, entry in enumerate(entries):
        row = db.stagebuildmatrix.create(data={
            "stageConfigId": config.id,
            "sortOrder": entry.get("sortOrder", i),
            "label": entry["label"].strip(),
            "fwType": entry["fwType"].strip(),
            "variant": entry["variant"].strip(),
            "configLog": entry.get("configLog", True),
            "producesHex": entry.get("producesHex", True),
            "producesCfw": entry.get("producesCfw", False),
            "gitRef": entry.get("gitRef", "pr"),
            "isVersionBump": entry.get("isVersionBump", False),
            "baseLabel": entry.get("baseLabel"),
            "description": entry.get("description"),
        })
        created.append(_serialize_build_matrix_entry(row))

    log_audit("stageConfig.buildMatrix.update", "ProductStageConfig", config.id, {"count": len(created)})
    return jsonify(ApiResponse.ok(created).to_dict()), 200


@require_permissions(Permissions.BUILDS_MANAGE)
def reset_stage_build_matrix(product_id: str, stage: str):
    """POST /products/<id>/stages/<stage>/build-matrix/reset — reset to Python defaults."""
    from corekinect.stages import Stage, get_stage_build_defs

    db = get_db_client()
    product = db.product.find_unique(where={"id": product_id})
    if not product:
        return not_found("Product not found")
    try:
        stage_num = int(stage)
    except ValueError:
        return bad_request("Stage must be a number")
    config = db.productstageconfig.find_first(
        where={"productId": product_id, "stage": stage_num},
    )
    if not config:
        return not_found(f"Stage {stage} config not found")

    stage_enum_map = {1: Stage.SMOKE, 2: Stage.DRIVER, 3: Stage.INTEGRATION, 4: Stage.REGRESSION, 5: Stage.FUOTA}
    stage_enum = stage_enum_map.get(stage_num)
    if not stage_enum:
        return bad_request(f"No default build definitions for stage {stage_num}")

    build_defs = get_stage_build_defs(stage_enum)

    # Replace existing entries
    db.stagebuildmatrix.delete_many(where={"stageConfigId": config.id})
    created = []
    for i, bd in enumerate(build_defs):
        row = db.stagebuildmatrix.create(data={
            "stageConfigId": config.id,
            "sortOrder": i,
            "label": bd.label,
            "fwType": bd.fw_type,
            "variant": bd.variant,
            "configLog": bd.config_log,
            "producesHex": bd.produces_hex,
            "producesCfw": bd.produces_cfw,
            "gitRef": bd.git_ref,
            "isVersionBump": bd.is_version_bump,
            "baseLabel": bd.base_label,
            "description": bd.description,
        })
        created.append(_serialize_build_matrix_entry(row))

    log_audit("stageConfig.buildMatrix.reset", "ProductStageConfig", config.id, {"count": len(created)})
    return jsonify(ApiResponse.ok(created).to_dict()), 200
