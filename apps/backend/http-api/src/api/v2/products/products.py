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

from .types import ProductCreateRequest, ProductUpdateRequest

logger = logging.getLogger(__name__)


def _serialize_target(t: Any) -> dict:
    return {
        "id": t.id,
        "role": t.role,
        "soc": t.soc,
        "appId": t.appId,
    }


def _serialize_product(p: Any, include_children: bool = False) -> dict:
    data = {
        "id": p.id,
        "name": p.name,
        "slug": p.slug,
        "description": p.description,
        "active": p.active,
        "buildConfig": p.buildConfig,
        "metadata": p.metadata,
        "createdAt": p.createdAt.isoformat(),
        "updatedAt": p.updatedAt.isoformat(),
    }
    if hasattr(p, "targets") and p.targets is not None:
        data["targets"] = [_serialize_target(t) for t in p.targets]
    else:
        data["targets"] = []
    if hasattr(p, "boards") and p.boards is not None:
        data["boardCount"] = len(p.boards)
        if include_children:
            data["boards"] = [_serialize_board_summary(b) for b in p.boards]
    if hasattr(p, "firmwareBuilds") and p.firmwareBuilds is not None:
        data["firmwareBuildCount"] = len(p.firmwareBuilds)
        if include_children:
            data["firmwareBuilds"] = [_serialize_firmware_build(b) for b in p.firmwareBuilds]
    if hasattr(p, "_count") and p._count is not None:
        data["sessionCount"] = getattr(p._count, "sessions", 0)
        data["testCount"] = getattr(p._count, "tests", 0)
    return data


def _serialize_board_summary(b: Any) -> dict:
    result = {
        "id": b.id,
        "productId": b.productId,
        "name": b.name,
        "ckBoardsName": getattr(b, "ckBoardsName", None),
        "ckBoardsBranch": getattr(b, "ckBoardsBranch", "main"),
        "vendor": getattr(b, "vendor", "corekinect"),
        "description": b.description,
        "active": b.active,
        "createdAt": b.createdAt.isoformat(),
        "updatedAt": b.updatedAt.isoformat(),
    }
    if hasattr(b, "revisions") and b.revisions is not None:
        result["revisionCount"] = len(b.revisions)
        result["revisions"] = [_serialize_board_revision(r) for r in b.revisions]
    return result


def _serialize_board_revision(r: Any) -> dict:
    result = {
        "id": r.id,
        "boardId": r.boardId,
        "version": r.version,
        "status": r.status,
        "notes": r.notes,
        "createdAt": r.createdAt.isoformat(),
        "updatedAt": r.updatedAt.isoformat(),
    }
    if hasattr(r, "chipsets") and r.chipsets is not None:
        result["chipsets"] = [
            {"id": rc.chipset.id, "name": rc.chipset.name, "isModem": rc.chipset.isModem}
            for rc in r.chipsets
            if hasattr(rc, "chipset") and rc.chipset is not None
        ]
    else:
        result["chipsets"] = []
    return result


def _serialize_firmware_build(b: Any) -> dict:
    data = {
        "id": b.id,
        "productId": b.productId,
        "chipsetId": b.chipsetId,
        "version": b.version,
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
    if hasattr(b, "chipset") and b.chipset is not None:
        data["chipset"] = {
            "id": b.chipset.id,
            "name": b.chipset.name,
            "isModem": b.chipset.isModem,
        }
    else:
        data["chipset"] = None
    if hasattr(b, "modemFilename") and b.modemFilename:
        data["modemFilename"] = b.modemFilename
        data["modemSizeBytes"] = str(b.modemSizeBytes) if b.modemSizeBytes is not None else None
        data["modemChecksum"] = b.modemChecksum
    return data


# ── Products CRUD ─────────────────────────────────────────


@require_permissions(Permissions.PRODUCTS_VIEW)
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
            "targets": True,
            "boards": {"include": {"revisions": True}},
            "firmwareBuilds": {"include": {"chipset": True}},
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


@require_permissions(Permissions.PRODUCTS_MANAGE)
def create_product():
    data, error = ProductCreateRequest.from_json(request.get_json())
    if error:
        return bad_request(error)

    db = get_db_client()

    existing = db.product.find_unique(where={"name": data.name})
    if existing:
        return conflict("Product with this name already exists")

    # Check slug uniqueness if provided
    if data.slug:
        existing_slug = db.product.find_unique(where={"slug": data.slug})
        if existing_slug:
            return conflict("Product with this slug already exists")

    from database import Json

    create_data = {
        "name": data.name,
        "description": data.description,
        "active": data.active,
        "targets": {
            "create": [
                {"role": t.role, "soc": t.soc, "appId": t.appId}
                for t in data.targets
            ],
        },
    }
    if data.slug is not None:
        create_data["slug"] = data.slug
    if data.buildConfig is not None:
        create_data["buildConfig"] = Json(data.buildConfig)
    if data.metadata is not None:
        create_data["metadata"] = Json(data.metadata)

    product = db.product.create(
        data=create_data,
        include={
            "targets": True,
            "boards": {"include": {"revisions": True}},
            "firmwareBuilds": {"include": {"chipset": True}},
        },
    )
    log_audit("product.create", "Product", product.id, {
        "name": data.name,
        "targets": [{"role": t.role, "soc": t.soc, "appId": t.appId} for t in data.targets],
    })
    return jsonify(ApiResponse.ok(_serialize_product(product)).to_dict()), 201


@require_permissions(Permissions.PRODUCTS_VIEW)
def get_product(product_id: str):
    db = get_db_client()
    product = db.product.find_unique(
        where={"id": product_id},
        include={
            "targets": True,
            "boards": {
                "order_by": {"name": "asc"},
                "include": {
                    "revisions": {
                        "order_by": {"version": "asc"},
                        "include": {
                            "chipsets": {"include": {"chipset": True}},
                        },
                    },
                },
            },
            "firmwareBuilds": {
                "order_by": {"createdAt": "desc"},
                "include": {
                    "chipset": True,
                },
            },
        },
    )
    if not product:
        return not_found("Product not found")
    return jsonify(ApiResponse.ok(_serialize_product(product, include_children=True)).to_dict()), 200


@require_permissions(Permissions.PRODUCTS_MANAGE)
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

    # Check slug uniqueness if being changed
    if data._has_slug and data.slug and data.slug != existing.slug:
        dup_slug = db.product.find_unique(where={"slug": data.slug})
        if dup_slug:
            return conflict("Product with this slug already exists")

    update_data = data.to_update_data()

    # Handle targets replacement (delete-all + create-new)
    if data._has_targets and data.targets is not None:
        update_data["targets"] = {
            "deleteMany": {},
            "create": [
                {"role": t.role, "soc": t.soc, "appId": t.appId}
                for t in data.targets
            ],
        }

    product = db.product.update(
        where={"id": product_id},
        data=update_data,
        include={
            "targets": True,
            "boards": {"include": {"revisions": True}},
            "firmwareBuilds": {"include": {"chipset": True}},
        },
    )
    log_audit("product.update", "Product", product_id, {"name": existing.name, "changes": data.to_update_data()})
    return jsonify(ApiResponse.ok(_serialize_product(product)).to_dict()), 200


@require_permissions(Permissions.PRODUCTS_MANAGE)
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


@require_permissions(Permissions.PRODUCTS_VIEW)
def get_product_by_slug(slug: str):
    """GET /v2/catalog/products/by-slug/<slug> — Find product by slug (for API consumers)."""
    db = get_db_client()
    product = db.product.find_first(
        where={"slug": slug},
        include={"targets": True},
    )
    if not product:
        return not_found(f"Product with slug '{slug}' not found")
    return jsonify(ApiResponse.ok(_serialize_product(product)).to_dict()), 200
