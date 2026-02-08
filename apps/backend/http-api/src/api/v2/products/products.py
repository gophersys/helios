import logging
import math
from typing import Any

from flask import jsonify, request

from src.lib.audit import log_audit
from src.lib.decorators import require_permissions
from src.lib.errors import bad_request, conflict, internal_error, not_found
from src.lib.permissions import Permissions
from src.lib.types import ApiResponse
from src.services.database.prisma import get_db_client

from .shared import SUPPORTED_CHIPSETS, SUPPORTED_SOCS
from .types import ProductCreateRequest, ProductUpdateRequest

logger = logging.getLogger(__name__)


# ── Chipset Configuration ────────────────────────────────


@require_permissions(Permissions.ADMIN_PRODUCTS_VIEW)
def get_supported_chipsets():
    data = {
        "chipsets": [
            {"name": name, "targetMcus": config["targetMcus"]}
            for name, config in sorted(SUPPORTED_CHIPSETS.items())
        ],
        "supportedSocs": SUPPORTED_SOCS,
    }
    return jsonify(ApiResponse.ok(data).to_dict()), 200


def _serialize_product(p: Any, include_children: bool = False) -> dict:
    data = {
        "id": p.id,
        "name": p.name,
        "description": p.description,
        "active": p.active,
        "metadata": p.metadata,
        "createdAt": p.createdAt.isoformat(),
        "updatedAt": p.updatedAt.isoformat(),
    }
    all_socs = set()
    if hasattr(p, "boardRevisions") and p.boardRevisions is not None:
        data["boardRevisionCount"] = len(p.boardRevisions)
        for r in p.boardRevisions:
            if r.chipsets:
                all_socs.update(r.chipsets)
        if include_children:
            data["boardRevisions"] = [_serialize_board_revision(r) for r in p.boardRevisions]
    if hasattr(p, "firmwareApplications") and p.firmwareApplications is not None:
        data["firmwareAppCount"] = len(p.firmwareApplications)
        for a in p.firmwareApplications:
            if a.targetMcu:
                all_socs.add(a.targetMcu)
        if include_children:
            data["firmwareApplications"] = [_serialize_firmware_app(a) for a in p.firmwareApplications]
    data["chipsets"] = sorted(all_socs)
    if hasattr(p, "firmwareBuilds") and p.firmwareBuilds is not None:
        data["firmwareBuildCount"] = len(p.firmwareBuilds)
        if include_children:
            data["firmwareBuilds"] = [_serialize_firmware_build(b) for b in p.firmwareBuilds]
    if hasattr(p, "_count") and p._count is not None:
        data["sessionCount"] = getattr(p._count, "sessions", 0)
        data["testCount"] = getattr(p._count, "tests", 0)
    return data


def _serialize_board_revision(r: Any) -> dict:
    return {
        "id": r.id,
        "productId": r.productId,
        "version": r.version,
        "chipsets": r.chipsets or [],
        "status": r.status,
        "notes": r.notes,
        "createdAt": r.createdAt.isoformat(),
        "updatedAt": r.updatedAt.isoformat(),
    }


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


def _serialize_firmware_build(b: Any) -> dict:
    data = {
        "id": b.id,
        "productId": b.productId,
        "applicationId": b.applicationId,
        "boardRevisionId": b.boardRevisionId,
        "version": b.version,
        "majorVersion": b.majorVersion,
        "minorVersion": b.minorVersion,
        "buildNumber": b.buildNumber,
        "bootloaderId": b.bootloaderId,
        "isManufacturing": b.isManufacturing,
        "storageKey": b.storageKey,
        "filename": b.filename,
        "sizeBytes": str(b.sizeBytes) if b.sizeBytes is not None else None,
        "checksum": b.checksum,
        "contentType": b.contentType,
        "status": b.status,
        "notes": b.notes,
        "createdAt": b.createdAt.isoformat(),
        "updatedAt": b.updatedAt.isoformat(),
    }
    if hasattr(b, "application") and b.application is not None:
        data["applicationName"] = b.application.name
    if hasattr(b, "boardRevision") and b.boardRevision is not None:
        data["boardRevisionVersion"] = b.boardRevision.version
    return data


# ── Products CRUD ─────────────────────────────────────────


@require_permissions(Permissions.ADMIN_PRODUCTS_VIEW)
def list_products():
    db = get_db_client()

    page = max(1, request.args.get("page", 1, type=int))
    limit = min(max(1, request.args.get("limit", 50, type=int)), 100)
    skip = (page - 1) * limit

    total = db.product.count()
    products = db.product.find_many(
        skip=skip,
        take=limit,
        order={"name": "asc"},
        include={
            "boardRevisions": True,
            "firmwareApplications": True,
            "firmwareBuilds": True,
        },
    )
    return jsonify(ApiResponse.ok({
        "data": [_serialize_product(p) for p in products],
        "pagination": {
            "page": page,
            "limit": limit,
            "total": total,
            "pages": math.ceil(total / limit) if limit > 0 else 0,
        },
    }).to_dict()), 200


@require_permissions(Permissions.ADMIN_PRODUCTS_MANAGE)
def create_product():
    data, error = ProductCreateRequest.from_json(request.get_json())
    if error:
        return bad_request(error)

    db = get_db_client()

    existing = db.product.find_unique(where={"name": data.name})
    if existing:
        return conflict("Product with this name already exists")

    product = db.product.create(
        data={
            "name": data.name,
            "description": data.description,
            "active": data.active,
        },
        include={
            "boardRevisions": True,
            "firmwareApplications": True,
            "firmwareBuilds": True,
        },
    )
    log_audit("product.create", "Product", product.id, {"name": data.name})
    return jsonify(ApiResponse.ok(_serialize_product(product)).to_dict()), 201


@require_permissions(Permissions.ADMIN_PRODUCTS_VIEW)
def get_product(product_id: str):
    db = get_db_client()
    product = db.product.find_unique(
        where={"id": product_id},
        include={
            "boardRevisions": {"order_by": {"version": "asc"}},
            "firmwareApplications": {
                "order_by": {"applicationId": "asc"},
                "include": {"firmwareBuilds": True},
            },
            "firmwareBuilds": {
                "order_by": {"createdAt": "desc"},
                "include": {
                    "application": True,
                    "boardRevision": True,
                },
            },
        },
    )
    if not product:
        return not_found("Product not found")
    return jsonify(ApiResponse.ok(_serialize_product(product, include_children=True)).to_dict()), 200


@require_permissions(Permissions.ADMIN_PRODUCTS_MANAGE)
def update_product(product_id: str):
    data, error = ProductUpdateRequest.from_json(request.get_json())
    if error:
        return bad_request(error)

    db = get_db_client()
    existing = db.product.find_unique(where={"id": product_id})
    if not existing:
        return not_found("Product not found")

    if data.name and data.name != existing.name:
        dup = db.product.find_unique(where={"name": data.name})
        if dup:
            return conflict("Product with this name already exists")

    product = db.product.update(
        where={"id": product_id},
        data=data.to_update_data(),
        include={
            "boardRevisions": True,
            "firmwareApplications": True,
            "firmwareBuilds": True,
        },
    )
    log_audit("product.update", "Product", product_id, {"name": existing.name, "changes": data.to_update_data()})
    return jsonify(ApiResponse.ok(_serialize_product(product)).to_dict()), 200


@require_permissions(Permissions.ADMIN_PRODUCTS_MANAGE)
def delete_product(product_id: str):
    db = get_db_client()
    existing = db.product.find_unique(where={"id": product_id})
    if not existing:
        return not_found("Product not found")

    # Check if product has sessions
    session_ref = db.session.find_first(where={"productId": product_id})
    if session_ref:
        return conflict("Cannot delete product: it has associated sessions")

    # Check if product has tests
    test_ref = db.test.find_first(where={"productId": product_id})
    if test_ref:
        return conflict("Cannot delete product: it has associated tests")

    db.product.delete(where={"id": product_id})
    log_audit("product.delete", "Product", product_id, {"name": existing.name})
    return jsonify(ApiResponse.ok({"deleted": True}).to_dict()), 200
