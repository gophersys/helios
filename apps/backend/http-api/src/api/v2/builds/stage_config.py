"""Product stage configuration endpoints — CRUD for validation stage configs."""

import logging
from flask import jsonify, request

from src.lib.audit import log_audit
from src.lib.decorators import require_permissions
from src.lib.errors import bad_request, conflict, internal_error, not_found
from src.lib.permissions import Permissions
from src.lib.types import ApiResponse
from src.services.database.prisma import get_db_client

from .stage_config_types import StageConfigCreateRequest, StageConfigUpdateRequest

logger = logging.getLogger(__name__)


# Default stage definitions for initialization
DEFAULT_STAGES = [
    {"stage": 1, "name": "Smoke", "priority": 10, "blocksMerge": True, "maxDurationSec": 300,
     "testTimeout": 120, "requiresFuota": False, "requiresBench": False},
    {"stage": 2, "name": "Unit", "priority": 20, "blocksMerge": True, "maxDurationSec": 600,
     "testTimeout": 300, "requiresFuota": False, "requiresBench": False},
    {"stage": 3, "name": "Integration", "priority": 30, "blocksMerge": True, "maxDurationSec": 1200,
     "testTimeout": 600, "requiresFuota": False, "requiresBench": True},
    {"stage": 4, "name": "FUOTA", "priority": 40, "blocksMerge": True, "maxDurationSec": 3600,
     "testTimeout": 1800, "requiresFuota": True, "requiresBench": True},
    {"stage": 5, "name": "Gate", "priority": 100, "blocksMerge": True, "maxDurationSec": 900,
     "testTimeout": 600, "requiresFuota": True, "requiresBench": True},
]


def _serialize_stage_config(cfg) -> dict:
    """Serialize a ProductStageConfig to JSON-friendly dict."""
    return {
        "id": cfg.id,
        "productId": cfg.productId,
        "stage": cfg.stage,
        "name": cfg.name,
        "enabled": cfg.enabled,
        "buildScript": cfg.buildScript,
        "buildTarget": cfg.buildTarget,
        "fwRepoUrl": cfg.fwRepoUrl,
        "fwRepoBranch": cfg.fwRepoBranch,
        "mfgRepoUrl": cfg.mfgRepoUrl,
        "mfgRepoBranch": cfg.mfgRepoBranch,
        "buildVariant": cfg.buildVariant,
        "configFlags": cfg.configFlags,
        "buildMatrix": cfg.buildMatrix,
        "testDirectory": cfg.testDirectory,
        "testMarker": cfg.testMarker,
        "testTimeout": cfg.testTimeout,
        "priority": cfg.priority,
        "blocksMerge": cfg.blocksMerge,
        "requiresFuota": cfg.requiresFuota,
        "requiresBench": cfg.requiresBench,
        "maxDurationSec": cfg.maxDurationSec,
        "description": cfg.description,
        "createdAt": cfg.createdAt.isoformat() if hasattr(cfg.createdAt, 'isoformat') else cfg.createdAt,
        "updatedAt": cfg.updatedAt.isoformat() if hasattr(cfg.updatedAt, 'isoformat') else cfg.updatedAt,
    }


@require_permissions(Permissions.BUILDS_VIEW)
def list_stage_configs(product_id: str):
    """GET /v2/products/<product_id>/stages — List stage configs for a product."""
    db = get_db_client()

    product = db.product.find_unique(where={"id": product_id})
    if not product:
        return not_found("Product not found")

    configs = db.productstageconfig.find_many(
        where={"productId": product_id},
        order={"stage": "asc"},
    )
    return jsonify(ApiResponse.ok([_serialize_stage_config(c) for c in configs]).to_dict()), 200


@require_permissions(Permissions.BUILDS_VIEW)
def get_stage_config(product_id: str, stage: str):
    """GET /v2/products/<product_id>/stages/<stage> — Get a specific stage config."""
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

    return jsonify(ApiResponse.ok(_serialize_stage_config(config)).to_dict()), 200


@require_permissions(Permissions.BUILDS_MANAGE)
def create_stage_config(product_id: str):
    """POST /v2/products/<product_id>/stages — Create a new stage config."""
    db = get_db_client()

    product = db.product.find_unique(where={"id": product_id})
    if not product:
        return not_found("Product not found")

    req, err = StageConfigCreateRequest.from_json(request.get_json())
    if err:
        return bad_request(err)

    # Check for duplicate stage
    existing = db.productstageconfig.find_first(
        where={"productId": product_id, "stage": req.stage}
    )
    if existing:
        return conflict(f"Stage {req.stage} already exists for this product")

    config = db.productstageconfig.create(
        data={
            "productId": product_id,
            "stage": req.stage,
            "name": req.name,
            "enabled": req.enabled,
            "priority": req.priority,
            "blocksMerge": req.blocksMerge,
            "requiresFuota": req.requiresFuota,
            "requiresBench": req.requiresBench,
            "testTimeout": req.testTimeout,
            "maxDurationSec": req.maxDurationSec,
            "buildScript": req.buildScript,
            "buildTarget": req.buildTarget,
            "buildVariant": req.buildVariant,
            "fwRepoUrl": req.fwRepoUrl,
            "fwRepoBranch": req.fwRepoBranch,
            "mfgRepoUrl": req.mfgRepoUrl,
            "mfgRepoBranch": req.mfgRepoBranch,
            "configFlags": req.configFlags,
            "buildMatrix": req.buildMatrix,
            "testDirectory": req.testDirectory,
            "testMarker": req.testMarker,
            "description": req.description,
        }
    )

    log_audit("create", "ProductStageConfig", config.id, {"stage": req.stage, "productId": product_id})
    return jsonify(ApiResponse.ok(_serialize_stage_config(config)).to_dict()), 201


@require_permissions(Permissions.BUILDS_MANAGE)
def update_stage_config(product_id: str, stage: str):
    """PUT /v2/products/<product_id>/stages/<stage> — Update a stage config."""
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
    if err:
        return bad_request(err)

    update_data = req.to_update_data()
    if not update_data:
        return bad_request("No fields to update")

    updated = db.productstageconfig.update(
        where={"id": config.id},
        data=update_data,
    )

    log_audit("update", "ProductStageConfig", config.id, update_data)
    return jsonify(ApiResponse.ok(_serialize_stage_config(updated)).to_dict()), 200


@require_permissions(Permissions.BUILDS_MANAGE)
def delete_stage_config(product_id: str, stage: str):
    """DELETE /v2/products/<product_id>/stages/<stage> — Delete a stage config."""
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

    log_audit("delete", "ProductStageConfig", config.id, {"stage": stage_num, "productId": product_id})
    return jsonify(ApiResponse.ok({"deleted": True}).to_dict()), 200


@require_permissions(Permissions.BUILDS_MANAGE)
def initialize_stages(product_id: str):
    """POST /v2/products/<product_id>/stages/initialize — Create default stage configs."""
    db = get_db_client()

    product = db.product.find_unique(where={"id": product_id})
    if not product:
        return not_found("Product not found")

    # Check for existing configs
    existing = db.productstageconfig.find_many(where={"productId": product_id})
    if existing:
        return conflict("Product already has stage configurations. Delete them first to reinitialize.")

    created = []
    for stage_def in DEFAULT_STAGES:
        config = db.productstageconfig.create(
            data={
                "productId": product_id,
                "stage": stage_def["stage"],
                "name": stage_def["name"],
                "enabled": True,
                "priority": stage_def["priority"],
                "blocksMerge": stage_def["blocksMerge"],
                "requiresFuota": stage_def["requiresFuota"],
                "requiresBench": stage_def["requiresBench"],
                "testTimeout": stage_def["testTimeout"],
                "maxDurationSec": stage_def["maxDurationSec"],
            }
        )
        created.append(_serialize_stage_config(config))

    log_audit("initialize", "ProductStageConfig", product_id, {"stages": len(created)})
    return jsonify(ApiResponse.ok(created).to_dict()), 201
