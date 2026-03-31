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
    {"stage": 2, "name": "Silicon"},
    {"stage": 3, "name": "Integration"},
    {"stage": 4, "name": "Nightly"},
    {"stage": 5, "name": "FUOTA"},
]

_INCLUDE = {"boardRevision": True, "signingKey": True}


def _serialize_stage_config(cfg) -> dict:
    data = {
        "id": cfg.id,
        "productId": cfg.productId,
        "stage": cfg.stage,
        "name": cfg.name,
        "enabled": cfg.enabled,
        "boardRevisionId": cfg.boardRevisionId,
        "watchBranch": cfg.watchBranch,
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
    return data


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
            "watchBranch": req.watchBranch,
            "signingKeyId": req.signingKeyId,
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
