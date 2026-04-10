"""Product stage configuration endpoints — CRUD for validation + manufacturing stage configs.

Stage 0 = manufacturing. Stages 1-5 = validation.
"""

import logging
from flask import g, jsonify, request

from src.lib.audit import log_audit
from src.lib.decorators import require_auth, require_permissions, _get_permissions_for_set
from src.lib.errors import bad_request, conflict, forbidden, not_found
from src.lib.permissions import Permissions
from src.lib.types import ApiResponse
from src.services.database.prisma import get_db_client

from .stage_config_types import StageConfigCreateRequest, StageConfigUpdateRequest

logger = logging.getLogger(__name__)

def _check_stage_permission(stage_type: str):
    """Check if the current user can manage the given stage type. Returns error response or None."""
    user = getattr(g, "current_user", None)
    if not user:
        return forbidden("Forbidden")
    role = getattr(g, "effective_role", user.get("role", "OPERATOR"))
    if role in ("ADMIN", "MAINTAINER"):
        return None
    perm_set_id = user.get("permissionSetId")
    perms = _get_permissions_for_set(perm_set_id) if perm_set_id else []
    perms = perms or []
    required = Permissions.MANUFACTURING_MANAGE if stage_type == "MANUFACTURING" else Permissions.BUILDS_MANAGE
    if required not in perms:
        return forbidden("Forbidden")
    return None


DEFAULT_VALIDATION_STAGES = [
    {"type": "VALIDATION", "stage": 1, "name": "Smoke"},
    {"type": "VALIDATION", "stage": 2, "name": "Driver"},
    {"type": "VALIDATION", "stage": 3, "name": "Integration"},
    {"type": "VALIDATION", "stage": 4, "name": "Regression"},
    {"type": "VALIDATION", "stage": 5, "name": "FUOTA"},
]

_INCLUDE = {"boardRevision": True, "signingKey": True, "buildMatrixEntries": True}


def _serialize_stage_config(cfg) -> dict:
    """Serialize a ProductStageConfig DB record to an API response dict."""
    data = {
        "id": cfg.id,
        "productId": cfg.productId,
        "type": cfg.type,
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


@require_auth
def list_stage_configs(product_id: str):
    """List stage configs for a product. Filter with ?type=VALIDATION or ?type=MANUFACTURING."""
    db = get_db_client()
    product = db.product.find_unique(where={"id": product_id})
    if not product:
        return not_found("Product not found")
    where: dict = {"productId": product_id}
    type_filter = request.args.get("type", "").strip().upper()
    if type_filter in ("VALIDATION", "MANUFACTURING"):
        where["type"] = type_filter
    configs = db.productstageconfig.find_many(
        where=where,
        order=[{"type": "asc"}, {"stage": "asc"}],
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


@require_auth
def create_stage_config(product_id: str):
    """Create a new stage config for a product. Stage 0 = manufacturing."""
    db = get_db_client()
    product = db.product.find_unique(where={"id": product_id})
    if not product:
        return not_found("Product not found")
    req, err = StageConfigCreateRequest.from_json(request.get_json())
    if err or req is None:
        return bad_request(err)
    perm_err = _check_stage_permission(req.type)
    if perm_err:
        return perm_err
    if not req.boardRevisionId:
        return bad_request("boardRevisionId is required — stage configs must be scoped to a hardware revision")
    existing = db.productstageconfig.find_first(
        where={"productId": product_id, "type": req.type, "stage": req.stage, "boardRevisionId": req.boardRevisionId}
    )
    if existing:
        return conflict(f"{req.type} stage {req.stage} already exists for this product and revision")
    # Block creating enabled stages for deprecated/EOL revisions
    if req.enabled and req.boardRevisionId:
        rev = db.boardrevision.find_unique(where={"id": req.boardRevisionId})
        if rev and rev.status in ("DEPRECATED", "EOL"):
            return bad_request(f"Cannot enable stage for {rev.status} revision {rev.version}")
    config = db.productstageconfig.create(
        data={
            "productId": product_id,
            "type": req.type,
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
    # Auto-populate build matrix from defaults
    _auto_populate_build_matrix(db, config.id, req.type, req.stage)
    # Re-fetch with matrix included
    config = db.productstageconfig.find_unique(where={"id": config.id}, include=_INCLUDE)
    log_audit("stageConfig.create", "ProductStageConfig", config.id, {"stage": req.stage})
    return jsonify(ApiResponse.ok(_serialize_stage_config(config)).to_dict()), 201


def _auto_populate_build_matrix(db, config_id: str, stage_type: str, stage_num: int):
    """Populate build matrix from corekinect.stages defaults. Non-critical — silently fails."""
    try:
        from corekinect.stages import Stage, StageType, get_stage_build_defs
        stage_map = {
            ("VALIDATION", 1): Stage.SMOKE,
            ("VALIDATION", 2): Stage.DRIVER,
            ("VALIDATION", 3): Stage.INTEGRATION,
            ("VALIDATION", 4): Stage.REGRESSION,
            ("VALIDATION", 5): Stage.FUOTA,
            ("MANUFACTURING", 1): Stage.MANUFACTURING,
        }
        stage_enum = stage_map.get((stage_type, stage_num))
        if not stage_enum:
            return
        defs = get_stage_build_defs(stage_enum)

        # Build processor lookup from ProductTarget records for this board revision
        processor_lookup = {}
        config = db.productstageconfig.find_unique(where={"id": config_id})
        if config and config.boardRevisionId:
            targets = db.producttarget.find_many(
                where={"boardRevisionId": config.boardRevisionId}
            )
            for t in targets:
                processor_lookup[t.role] = t.soc  # "app" → "nrf52840", "comms" → "nrf9151"

        for build_def in defs:
            # Resolve processor: map fw_type to target role, fall back to build_def default
            role = build_def.fw_type
            if role == "modem":
                role = "comms"  # modem uses same processor as comms
            processor = processor_lookup.get(role, build_def.processor) or None

            db.stagebuildmatrix.create(data={
                "stageConfigId": config_id,
                "label": build_def.label,
                "fwType": build_def.fw_type,
                "variant": build_def.variant,
                "configLog": build_def.config_log,
                "producesHex": build_def.produces_hex,
                "producesCfw": build_def.produces_cfw,
                "gitRef": build_def.git_ref,
                "isVersionBump": build_def.is_version_bump,
                "baseLabel": build_def.base_label,
                "processor": processor,
                "filenamePattern": build_def.filename_pattern or None,
            })
    except Exception:
        pass  # Non-critical — user can reset manually via UI


def _check_revision_enabled(db, enabling: bool, rev_id: str | None):
    """Block enabling stages for deprecated/EOL revisions.  Returns error string or None."""
    if not enabling or not rev_id:
        return None
    rev = db.boardrevision.find_unique(where={"id": rev_id})
    if rev and rev.status in ("DEPRECATED", "EOL"):
        return f"Cannot enable stage for {rev.status} revision {rev.version}"
    return None


def _try_trigger_build(product_id: str, config_id: str, stage: str, result: dict) -> None:
    """Attempt to trigger a build and annotate the result dict."""
    from src.services.build_trigger import trigger_stage_build
    try:
        trigger_result = trigger_stage_build(product_id, config_id)
        if trigger_result:
            result["buildTriggered"] = True
            result["buildRunId"] = trigger_result["buildRunId"]
            result["jobCount"] = trigger_result["jobCount"]
            logger.info("Build triggered for stage %s: %s", stage, trigger_result["buildRunId"])
        else:
            result["buildTriggered"] = False
            result["buildError"] = "Failed to trigger build — check product repos and revision config"
    except Exception as e:
        logger.exception("Failed to trigger build for stage %s: %s", stage, e)
        result["buildTriggered"] = False
        result["buildError"] = "Internal error occurred while triggering build"


def _resolve_stage_config(db, product_id: str, stage: str):
    """Look up product and stage config.  Returns (product, config, stage_num, error_response)."""
    product = db.product.find_unique(where={"id": product_id})
    if not product:
        return None, None, None, not_found("Product not found")
    try:
        stage_num = int(stage)
    except ValueError:
        return None, None, None, bad_request("Stage must be a number")
    config = db.productstageconfig.find_first(where={"productId": product_id, "stage": stage_num})
    if not config:
        return None, None, None, not_found(f"Stage {stage} config not found")
    return product, config, stage_num, None


@require_permissions(Permissions.BUILDS_MANAGE)
def update_stage_config(product_id: str, stage: str):
    """Update a stage config, optionally triggering a build."""
    db = get_db_client()
    product, config, stage_num, err = _resolve_stage_config(db, product_id, stage)
    if err:
        return err

    req, err = StageConfigUpdateRequest.from_json(request.get_json())
    if err or req is None:
        return bad_request(err)
    update_data = req.to_update_data()
    if not update_data:
        return bad_request("No fields to update")

    rev_err = _check_revision_enabled(
        db, update_data.get("enabled", False),
        update_data.get("boardRevisionId", config.boardRevisionId),
    )
    if rev_err:
        return bad_request(rev_err)

    updated = db.productstageconfig.update(where={"id": config.id}, data=update_data, include=_INCLUDE)
    log_audit("stageConfig.update", "ProductStageConfig", config.id, update_data)

    result = _serialize_stage_config(updated)

    raw_data = request.get_json() or {}
    if raw_data.get("buildNow") and updated.enabled:
        _try_trigger_build(product_id, config.id, stage, result)

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
    """Create all five default stage configs for a product (optionally scoped to a board revision)."""
    db = get_db_client()
    product = db.product.find_unique(where={"id": product_id})
    if not product:
        return not_found("Product not found")
    body = request.get_json(silent=True) or {}
    board_revision_id = body.get("boardRevisionId")
    if not board_revision_id:
        return bad_request("boardRevisionId is required — stage configs must be scoped to a hardware revision")
    # Verify the board revision exists
    board_rev = db.boardrevision.find_unique(where={"id": board_revision_id})
    if not board_rev:
        return not_found("Board revision not found")
    existing = db.productstageconfig.find_many(
        where={"productId": product_id, "type": "VALIDATION", "boardRevisionId": board_revision_id}
    )
    if existing:
        return conflict("Validation stages already configured for this revision. Delete them first to reinitialize.")
    created = []
    for stage_def in DEFAULT_VALIDATION_STAGES:
        data = {"productId": product_id, "enabled": False, "boardRevisionId": board_revision_id, **stage_def}
        config = db.productstageconfig.create(data=data, include=_INCLUDE)
        _auto_populate_build_matrix(db, config.id, "VALIDATION", stage_def.get("stage", 1))
        config = db.productstageconfig.find_unique(where={"id": config.id}, include=_INCLUDE)
        created.append(_serialize_stage_config(config))
    log_audit("stageConfig.initialize", "ProductStageConfig", product_id, {"stages": len(created), "boardRevisionId": board_revision_id})
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
        "processor": entry.processor,
        "filenamePattern": entry.filenamePattern,
    }


@require_permissions(Permissions.BUILDS_VIEW)
def get_stage_build_matrix(product_id: str, stage: str):
    """GET /products/<id>/stages/<stage>/build-matrix — return build matrix for a stage."""
    db = get_db_client()
    product, config, stage_num, err = _resolve_stage_config(db, product_id, stage)
    if err:
        return err
    entries = db.stagebuildmatrix.find_many(
        where={"stageConfigId": config.id},
        order={"sortOrder": "asc"},
    )
    return jsonify(ApiResponse.ok([_serialize_build_matrix_entry(e) for e in entries]).to_dict()), 200


def _validate_matrix_entries(entries: list) -> str | None:
    """Validate build matrix entries.  Returns an error string or None."""
    seen_labels: set = set()
    for i, entry in enumerate(entries):
        label = (entry.get("label") or "").strip()
        if not label:
            return f"Entry {i}: label is required"
        if label in seen_labels:
            return f"Entry {i}: duplicate label '{label}'"
        seen_labels.add(label)
        if not (entry.get("fwType") or "").strip():
            return f"Entry {i}: fwType is required"
        if not (entry.get("variant") or "").strip():
            return f"Entry {i}: variant is required"
    return None


@require_permissions(Permissions.BUILDS_MANAGE)
def update_stage_build_matrix(product_id: str, stage: str):
    """PUT /products/<id>/stages/<stage>/build-matrix — replace build matrix entries."""
    db = get_db_client()
    product, config, stage_num, err = _resolve_stage_config(db, product_id, stage)
    if err:
        return err

    data = request.get_json()
    if not data or not isinstance(data.get("entries"), list):
        return bad_request("Request body must contain 'entries' array")

    entries = data["entries"]
    validation_err = _validate_matrix_entries(entries)
    if validation_err:
        return bad_request(validation_err)

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
            "processor": entry.get("processor"),
            "filenamePattern": entry.get("filenamePattern"),
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

    # Build processor lookup from ProductTarget records for this board revision
    processor_lookup = {}
    if config.boardRevisionId:
        targets = db.producttarget.find_many(
            where={"boardRevisionId": config.boardRevisionId}
        )
        for t in targets:
            processor_lookup[t.role] = t.soc

    # Replace existing entries
    db.stagebuildmatrix.delete_many(where={"stageConfigId": config.id})
    created = []
    for i, bd in enumerate(build_defs):
        role = bd.fw_type
        if role == "modem":
            role = "comms"
        processor = processor_lookup.get(role, bd.processor) or None

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
            "processor": processor,
            "filenamePattern": bd.filename_pattern or None,
        })
        created.append(_serialize_build_matrix_entry(row))

    log_audit("stageConfig.buildMatrix.reset", "ProductStageConfig", config.id, {"count": len(created)})
    return jsonify(ApiResponse.ok(created).to_dict()), 200
