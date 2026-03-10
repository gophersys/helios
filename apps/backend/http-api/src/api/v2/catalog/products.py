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


def _serialize_product(p: Any, include_children: bool = False) -> dict:
    data = {
        "id": p.id,
        "name": p.name,
        "slug": p.slug,
        "description": p.description,
        "active": p.active,
        # Repo config (git poller uses these)
        "repoSlug": p.repoSlug,
        "repoSshUrl": p.repoSshUrl,
        "repoBranch": p.repoBranch,
        "mfgRepoSlug": p.mfgRepoSlug,
        "mfgRepoSshUrl": p.mfgRepoSshUrl,
        # Build config (build worker uses these)
        "buildBoard": p.buildBoard,
        "buildWestDir": p.buildWestDir,
        "buildMfgDir": p.buildMfgDir,
        "metadata": p.metadata,
        "createdAt": p.createdAt.isoformat(),
        "updatedAt": p.updatedAt.isoformat(),
    }
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
        "selectedBuilds": r.selectedBuilds if hasattr(r, "selectedBuilds") and r.selectedBuilds else {},
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


@require_permissions(Permissions.ADMIN_CATALOG_VIEW)
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


@require_permissions(Permissions.ADMIN_CATALOG_MANAGE)
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
            "boards": {"include": {"revisions": True}},
            "firmwareBuilds": {"include": {"chipset": True}},
        },
    )
    log_audit("product.create", "Product", product.id, {"name": data.name})
    return jsonify(ApiResponse.ok(_serialize_product(product)).to_dict()), 201


@require_permissions(Permissions.ADMIN_CATALOG_VIEW)
def get_product(product_id: str):
    db = get_db_client()
    product = db.product.find_unique(
        where={"id": product_id},
        include={
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


@require_permissions(Permissions.ADMIN_CATALOG_MANAGE)
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
            "boards": {"include": {"revisions": True}},
            "firmwareBuilds": {"include": {"chipset": True}},
        },
    )
    log_audit("product.update", "Product", product_id, {"name": existing.name, "changes": data.to_update_data()})
    return jsonify(ApiResponse.ok(_serialize_product(product)).to_dict()), 200


@require_permissions(Permissions.ADMIN_CATALOG_MANAGE)
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


@require_permissions(Permissions.ADMIN_CATALOG_VIEW)
def get_product_by_slug(slug: str):
    """GET /v2/catalog/products/by-slug/<slug> — Find product by slug (for API consumers)."""
    db = get_db_client()
    product = db.product.find_first(where={"slug": slug})
    if not product:
        return not_found(f"Product with slug '{slug}' not found")
    return jsonify(ApiResponse.ok(_serialize_product(product)).to_dict()), 200


@require_permissions(Permissions.ADMIN_CATALOG_VIEW)
def get_product_by_repo(repo_slug: str):
    """GET /v2/catalog/products/by-repo/<repo_slug> — Find product by repo slug (for git poller)."""
    db = get_db_client()
    product = db.product.find_first(
        where={"OR": [{"repoSlug": repo_slug}, {"mfgRepoSlug": repo_slug}]}
    )
    if not product:
        return not_found(f"Product with repo '{repo_slug}' not found")
    return jsonify(ApiResponse.ok(_serialize_product(product)).to_dict()), 200
