"""Trigger a validation run from a specific asset set."""

import logging
from flask import jsonify, request

from src.lib.audit import log_audit
from src.lib.decorators import require_permissions
from src.lib.errors import bad_request, conflict, not_found
from src.lib.permissions import Permissions
from src.lib.types import ApiResponse
from src.services.database.prisma import get_db_client

logger = logging.getLogger(__name__)


@require_permissions(Permissions.VALIDATION_RUN)
def trigger_stage_run(product_id: str, stage: str):
    """POST /products/<product_id>/stages/<stage>/trigger-run

    Trigger a validation run for a given stage using a specific asset set.
    """
    db = get_db_client()

    # --- Parse body ---
    body = request.get_json(silent=True) or {}
    asset_set_id = (body.get("assetSetId") or "").strip()
    if not asset_set_id:
        return bad_request("assetSetId is required")

    # --- Validate product ---
    product = db.product.find_unique(where={"id": product_id})
    if not product:
        return not_found("Product not found")
    if product.status == "ARCHIVED":
        return conflict("Product is archived and cannot trigger new runs")

    # --- Parse stage number ---
    try:
        stage_int = int(stage)
    except ValueError:
        return bad_request("Stage must be a number")
    if stage_int < 1 or stage_int > 5:
        return bad_request("Stage must be between 1 and 5")

    # --- Look up stage config ---
    config = db.productstageconfig.find_first(
        where={
            "productId": product_id,
            "stage": stage_int,
            "type": "VALIDATION",
            "enabled": True,
        }
    )
    if not config:
        # Check if a disabled VALIDATION config exists
        disabled_config = db.productstageconfig.find_first(
            where={"productId": product_id, "stage": stage_int, "type": "VALIDATION"}
        )
        if disabled_config:
            return bad_request("Stage is not enabled")

        # Check if a MANUFACTURING config exists for this stage
        mfg_config = db.productstageconfig.find_first(
            where={"productId": product_id, "stage": stage_int, "type": "MANUFACTURING"}
        )
        if mfg_config:
            return bad_request("Manufacturing stage triggering is not yet supported")

        return not_found("Stage config not found")

    # --- Validate asset set ---
    asset_set = db.assetset.find_unique(where={"id": asset_set_id})
    if not asset_set:
        return not_found("Asset set not found")
    if asset_set.productId != product_id:
        return bad_request("Asset set does not belong to this product")
    if asset_set.status == "PENDING":
        return bad_request("Asset set is not ready (status: PENDING)")

    # --- Create queue entry ---
    queue_entry = db.validationqueueentry.create(
        data={
            "assetSetId": asset_set_id,
            "stageConfigId": config.id,
            "stage": stage_int,
            "status": "QUEUED",
            "reason": "Manual trigger",
        }
    )

    result = {
        "stageConfigId": config.id,
        "assetSetId": asset_set_id,
        "stage": stage_int,
        "productId": product_id,
        "queued": True,
        "queueEntryId": queue_entry.id,
    }

    log_audit(
        "stage.triggerRun",
        "ProductStageConfig",
        config.id,
        {
            "assetSetId": asset_set_id,
            "stage": stage_int,
            "queued": True,
            "queueEntryId": queue_entry.id,
        },
    )

    return jsonify(ApiResponse.ok(result).to_dict()), 200
