from flask import jsonify, request

from src.lib.audit import log_audit
from src.lib.decorators import require_permissions
from src.lib.errors import bad_request, conflict, not_found
from src.lib.permissions import Permissions
from src.lib.types import ApiResponse
from src.services.database.prisma import get_db_client

from .types import BoardRevisionCreateRequest, BoardRevisionUpdateRequest


def _serialize_revision(r) -> dict:
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


# ── Board Revisions CRUD ─────────────────────────────────


@require_permissions(Permissions.ADMIN_PRODUCTS_MANAGE)
def create_board_revision(product_id: str):
    db = get_db_client()
    product = db.product.find_unique(where={"id": product_id})
    if not product:
        return not_found("Product not found")

    data, error = BoardRevisionCreateRequest.from_json(request.get_json())
    if error:
        return bad_request(error)

    existing = db.productboardrevision.find_first(
        where={"productId": product_id, "version": data.version}
    )
    if existing:
        return conflict(f"Board revision '{data.version}' already exists for this product")

    revision = db.productboardrevision.create(
        data={
            "productId": product_id,
            "version": data.version,
            "chipsets": data.chipsets,
            "status": data.status,
            "notes": data.notes,
        }
    )
    log_audit("boardRevision.create", "ProductBoardRevision", revision.id, {
        "productName": product.name, "version": data.version, "status": data.status,
    })
    return jsonify(ApiResponse.ok(_serialize_revision(revision)).to_dict()), 201


@require_permissions(Permissions.ADMIN_PRODUCTS_MANAGE)
def update_board_revision(product_id: str, revision_id: str):
    db = get_db_client()
    revision = db.productboardrevision.find_first(
        where={"id": revision_id, "productId": product_id}
    )
    if not revision:
        return not_found("Board revision not found")

    data, error = BoardRevisionUpdateRequest.from_json(request.get_json())
    if error:
        return bad_request(error)

    if data.version and data.version != revision.version:
        dup = db.productboardrevision.find_first(
            where={"productId": product_id, "version": data.version}
        )
        if dup:
            return conflict(f"Board revision '{data.version}' already exists for this product")

    updated = db.productboardrevision.update(
        where={"id": revision_id},
        data=data.to_update_data(),
    )
    log_audit("boardRevision.update", "ProductBoardRevision", revision_id, {
        "version": revision.version, "changes": data.to_update_data(),
    })
    return jsonify(ApiResponse.ok(_serialize_revision(updated)).to_dict()), 200


@require_permissions(Permissions.ADMIN_PRODUCTS_MANAGE)
def delete_board_revision(product_id: str, revision_id: str):
    db = get_db_client()
    revision = db.productboardrevision.find_first(
        where={"id": revision_id, "productId": product_id}
    )
    if not revision:
        return not_found("Board revision not found")

    # Check for firmware build references
    build_ref = db.firmwarebuild.find_first(
        where={"boardRevisionId": revision_id}
    )
    if build_ref:
        return conflict("Cannot delete board revision: it is referenced by firmware builds")

    db.productboardrevision.delete(where={"id": revision_id})
    log_audit("boardRevision.delete", "ProductBoardRevision", revision_id, {
        "version": revision.version,
    })
    return jsonify(ApiResponse.ok({"deleted": True}).to_dict()), 200
