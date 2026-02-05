from flask import jsonify, request

from src.lib.audit import log_audit
from src.lib.decorators import require_permissions
from src.lib.errors import bad_request, conflict, not_found
from src.lib.permissions import Permissions
from src.lib.types import ApiResponse
from src.services.database.prisma import get_db_client

from .types import FirmwareAppCreateRequest, FirmwareAppUpdateRequest

from typing import Any


def _serialize_firmware_app(a: Any) -> dict:
    data = {
        "id": a.id,
        "productId": a.productId,
        "applicationId": a.applicationId,
        "name": a.name,
        "targetMcu": a.targetMcu,
        "chipset": a.chipset,
        "coreCloudDeviceType": a.coreCloudDeviceType,
        "coreCloudVariant": a.coreCloudVariant,
        "notes": a.notes,
        "createdAt": a.createdAt.isoformat(),
        "updatedAt": a.updatedAt.isoformat(),
    }
    if hasattr(a, "firmwareBuilds") and a.firmwareBuilds is not None:
        data["buildCount"] = len(a.firmwareBuilds)
    return data


# ── Firmware Applications CRUD ────────────────────────────


@require_permissions(Permissions.ADMIN_PRODUCTS_MANAGE)
def create_firmware_app(product_id: str):
    db = get_db_client()
    product = db.product.find_unique(where={"id": product_id})
    if not product:
        return not_found("Product not found")

    data, error = FirmwareAppCreateRequest.from_json(request.get_json())
    if error:
        return bad_request(error)

    existing = db.firmwareapplication.find_first(
        where={"productId": product_id, "applicationId": data.applicationId}
    )
    if existing:
        return conflict(f"Application ID {data.applicationId} already exists for this product")

    app = db.firmwareapplication.create(
        data={
            "productId": product_id,
            "applicationId": data.applicationId,
            "name": data.name,
            "targetMcu": data.targetMcu,
            "chipset": data.chipset,
            "coreCloudDeviceType": data.coreCloudDeviceType,
            "coreCloudVariant": data.coreCloudVariant,
            "notes": data.notes,
        },
        include={"firmwareBuilds": True},
    )
    log_audit("firmwareApp.create", "FirmwareApplication", app.id, {
        "productName": product.name, "applicationId": data.applicationId, "name": data.name,
    })
    return jsonify(ApiResponse.ok(_serialize_firmware_app(app)).to_dict()), 201


@require_permissions(Permissions.ADMIN_PRODUCTS_MANAGE)
def update_firmware_app(product_id: str, app_id: str):
    db = get_db_client()
    app = db.firmwareapplication.find_first(
        where={"id": app_id, "productId": product_id}
    )
    if not app:
        return not_found("Firmware application not found")

    data, error = FirmwareAppUpdateRequest.from_json(request.get_json())
    if error:
        return bad_request(error)

    updated = db.firmwareapplication.update(
        where={"id": app_id},
        data=data.to_update_data(),
        include={"firmwareBuilds": True},
    )
    log_audit("firmwareApp.update", "FirmwareApplication", app_id, {
        "name": app.name, "changes": data.to_update_data(),
    })
    return jsonify(ApiResponse.ok(_serialize_firmware_app(updated)).to_dict()), 200


@require_permissions(Permissions.ADMIN_PRODUCTS_MANAGE)
def delete_firmware_app(product_id: str, app_id: str):
    db = get_db_client()
    app = db.firmwareapplication.find_first(
        where={"id": app_id, "productId": product_id}
    )
    if not app:
        return not_found("Firmware application not found")

    # Check for firmware build references
    build_ref = db.firmwarebuild.find_first(
        where={"applicationId": app_id}
    )
    if build_ref:
        return conflict("Cannot delete firmware application: it has associated firmware builds")

    db.firmwareapplication.delete(where={"id": app_id})
    log_audit("firmwareApp.delete", "FirmwareApplication", app_id, {
        "name": app.name, "applicationId": app.applicationId,
    })
    return jsonify(ApiResponse.ok({"deleted": True}).to_dict()), 200
