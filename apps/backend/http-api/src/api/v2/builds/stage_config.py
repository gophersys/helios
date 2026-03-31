"""Product stage configuration endpoints — CRUD for validation stage configs.

Each stage config defines:
- Which revision to build/test against
- Test configuration (directory, markers, timeout)
- Scheduling rules (priority, auto-progress, merge blocking)

Build recipes are convention-driven via StageBuildDef (stage_builds.py).
The system derives what to build from the product's repos + revision + stage.
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

# Default stage definitions — test config only, no build config
DEFAULT_STAGES = [
    {"stage": 1, "name": "Smoke", "priority": 10, "blocksMerge": True,
     "testDirectory": "tests/smoke/", "testMarker": "-m smoke",
     "testTimeout": 120, "requiresBench": False, "maxDurationSec": 300},
    {"stage": 2, "name": "Silicon", "priority": 20, "blocksMerge": True,
     "testDirectory": "tests/silicon/", "testMarker": "-m silicon",
     "testTimeout": 300, "requiresBench": True, "maxDurationSec": 600},
    {"stage": 3, "name": "Integration", "priority": 30, "blocksMerge": True,
     "testDirectory": "tests/integration/", "testMarker": "-m integration",
     "testTimeout": 600, "requiresBench": True, "maxDurationSec": 1200},
    {"stage": 4, "name": "Nightly", "priority": 40, "blocksMerge": False,
     "testDirectory": "tests/nightly/", "testMarker": "-m nightly",
     "testTimeout": 1800, "requiresBench": True, "maxDurationSec": 3600},
    {"stage": 5, "name": "FUOTA", "priority": 100, "blocksMerge": True,
     "testDirectory": "tests/fuota/", "testMarker": "-m fuota",
     "testTimeout": 600, "requiresBench": True, "maxDurationSec": 900},
]


def _serialize_stage_config(cfg) -> dict:
    data = {
        "id": cfg.id,
        "productId": cfg.productId,
        "stage": cfg.stage,
        "name": cfg.name,
        "enabled": cfg.enabled,
        "boardRevisionId": cfg.boardRevisionId,
        "testDirectory": cfg.testDirectory,
        "testMarker": cfg.testMarker,
        "testTimeout": cfg.testTimeout,
        "priority": cfg.priority,
        "blocksMerge": cfg.blocksMerge,
        "autoProgress": cfg.autoProgress,
        "requiresBench": cfg.requiresBench,
        "maxDurationSec": cfg.maxDurationSec,
        "description": cfg.description,
        "createdAt": cfg.createdAt.isoformat() if hasattr(cfg.createdAt, 'isoformat') else cfg.createdAt,
        "updatedAt": cfg.updatedAt.isoformat() if hasattr(cfg.updatedAt, 'isoformat') else cfg.updatedAt,
    }
    if hasattr(cfg, "boardRevision") and cfg.boardRevision:
        data["boardRevision"] = {
            "id": cfg.boardRevision.id,
            "version": cfg.boardRevision.version,
            "ckBoardsName": cfg.boardRevision.ckBoardsName,
        }
    return data


_INCLUDE = {"boardRevision": True}


@require_permissions(Permissions.BUILDS_VIEW)
def list_stage_configs(product_id: str):
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
    db = get_db_client()
    product = db.product.find_unique(where={"id": product_id})
    if not product:
        return not_found("Product not found")

    req, err = StageConfigCreateRequest.from_json(request.get_json())
    if err:
        return bad_request(err)

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
            "boardRevisionId": req.boardRevisionId,
            "priority": req.priority,
            "blocksMerge": req.blocksMerge,
            "autoProgress": getattr(req, "autoProgress", False),
            "requiresBench": req.requiresBench,
            "testTimeout": req.testTimeout,
            "testDirectory": req.testDirectory,
            "testMarker": req.testMarker,
            "maxDurationSec": req.maxDurationSec,
            "description": req.description,
        },
        include=_INCLUDE,
    )

    log_audit("stageConfig.create", "ProductStageConfig", config.id, {"stage": req.stage})
    return jsonify(ApiResponse.ok(_serialize_stage_config(config)).to_dict()), 201


@require_permissions(Permissions.BUILDS_MANAGE)
def update_stage_config(product_id: str, stage: str):
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
        include=_INCLUDE,
    )

    log_audit("stageConfig.update", "ProductStageConfig", config.id, update_data)
    return jsonify(ApiResponse.ok(_serialize_stage_config(updated)).to_dict()), 200


@require_permissions(Permissions.BUILDS_MANAGE)
def delete_stage_config(product_id: str, stage: str):
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
    """POST /v2/products/<product_id>/stages/initialize — Create default stage configs."""
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
            data={
                "productId": product_id,
                **stage_def,
            },
            include=_INCLUDE,
        )
        created.append(_serialize_stage_config(config))

    log_audit("stageConfig.initialize", "ProductStageConfig", product_id, {"stages": len(created)})
    return jsonify(ApiResponse.ok(created).to_dict()), 201
