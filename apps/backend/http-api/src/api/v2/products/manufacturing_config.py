"""Manufacturing config CRUD — /v2/products/<id>/manufacturing."""

import logging

from flask import jsonify, request
from database import Json

from src.lib.audit import log_audit
from src.lib.decorators import require_permissions
from src.lib.errors import bad_request, conflict, not_found
from src.lib.permissions import Permissions
from src.lib.types import ApiResponse
from src.services.database.prisma import get_db_client

from ..manufacturing.types import ManufacturingConfigCreateRequest, ManufacturingConfigUpdateRequest

logger = logging.getLogger(__name__)


def _serialize_config(cfg) -> dict:
    return {
        "id": cfg.id,
        "productId": cfg.productId,
        "boardRevisionId": cfg.boardRevisionId,
        "enabled": cfg.enabled,
        "stages": cfg.stages,
        "firmwareSource": cfg.firmwareSource,
        "firmwareSetId": cfg.firmwareSetId,
        "personalizationConfig": cfg.personalizationConfig,
        "passCriteria": cfg.passCriteria,
        "createdAt": cfg.createdAt.isoformat() if cfg.createdAt else None,
        "updatedAt": cfg.updatedAt.isoformat() if cfg.updatedAt else None,
        "boardRevision": {
            "id": cfg.boardRevision.id,
            "version": cfg.boardRevision.version,
        } if hasattr(cfg, "boardRevision") and cfg.boardRevision else None,
    }


@require_permissions(Permissions.MANUFACTURING_VIEW)
def get_manufacturing_config(product_id: str):
    """GET /v2/products/<id>/manufacturing"""
    db = get_db_client()
    product = db.product.find_unique(where={"id": product_id})
    if not product:
        return not_found("Product not found")

    cfg = db.manufacturingconfig.find_unique(
        where={"productId_boardRevisionId": {"productId": product_id, "boardRevisionId": product_id}},
    )
    # Fall back: find first config for this product
    if not cfg:
        cfg = db.manufacturingconfig.find_first(
            where={"productId": product_id},
            include={"boardRevision": True},
        )
    if not cfg:
        return not_found("Manufacturing config not found for this product")

    return jsonify(ApiResponse.ok(_serialize_config(cfg)).to_dict()), 200


@require_permissions(Permissions.MANUFACTURING_MANAGE)
def create_manufacturing_config(product_id: str):
    """POST /v2/products/<id>/manufacturing"""
    db = get_db_client()
    product = db.product.find_unique(where={"id": product_id})
    if not product:
        return not_found("Product not found")

    data, error = ManufacturingConfigCreateRequest.from_json(request.get_json())
    if error:
        return bad_request(error)

    existing = db.manufacturingconfig.find_unique(
        where={"productId_boardRevisionId": {"productId": product_id, "boardRevisionId": data.boardRevisionId}},
    )
    if existing:
        return conflict("Manufacturing config already exists for this product and board revision")

    create_data: dict = {
        "productId": product_id,
        "boardRevisionId": data.boardRevisionId,
        "enabled": data.enabled,
        "stages": Json(data.stages) if data.stages else Json([]),
        "firmwareSource": data.firmwareSource,
    }
    if data.firmwareSetId:
        create_data["firmwareSetId"] = data.firmwareSetId
    if data.personalizationConfig:
        create_data["personalizationConfig"] = Json(data.personalizationConfig)
    if data.passCriteria:
        create_data["passCriteria"] = Json(data.passCriteria)

    cfg = db.manufacturingconfig.create(
        data=create_data,
        include={"boardRevision": True},
    )

    log_audit("create", "manufacturing_config", cfg.id, {"productId": product_id})
    return jsonify(ApiResponse.ok(_serialize_config(cfg)).to_dict()), 201


@require_permissions(Permissions.MANUFACTURING_MANAGE)
def update_manufacturing_config(product_id: str):
    """PUT /v2/products/<id>/manufacturing"""
    db = get_db_client()
    product = db.product.find_unique(where={"id": product_id})
    if not product:
        return not_found("Product not found")

    existing = db.manufacturingconfig.find_first(
        where={"productId": product_id},
    )
    if not existing:
        return not_found("Manufacturing config not found for this product")

    data, error = ManufacturingConfigUpdateRequest.from_json(request.get_json())
    if error:
        return bad_request(error)

    update_data = data.to_update_data()
    if not update_data:
        return jsonify(ApiResponse.ok(_serialize_config(existing)).to_dict()), 200

    cfg = db.manufacturingconfig.update(
        where={"id": existing.id},
        data=update_data,
        include={"boardRevision": True},
    )

    log_audit("update", "manufacturing_config", cfg.id, {"productId": product_id, "fields": list(update_data.keys())})
    return jsonify(ApiResponse.ok(_serialize_config(cfg)).to_dict()), 200


@require_permissions(Permissions.MANUFACTURING_MANAGE)
def delete_manufacturing_config(product_id: str):
    """DELETE /v2/products/<id>/manufacturing"""
    db = get_db_client()
    product = db.product.find_unique(where={"id": product_id})
    if not product:
        return not_found("Product not found")

    existing = db.manufacturingconfig.find_first(
        where={"productId": product_id},
    )
    if not existing:
        return not_found("Manufacturing config not found for this product")

    db.manufacturingconfig.delete(where={"id": existing.id})

    log_audit("delete", "manufacturing_config", existing.id, {"productId": product_id})
    return jsonify(ApiResponse.ok({"deleted": True}).to_dict()), 200
