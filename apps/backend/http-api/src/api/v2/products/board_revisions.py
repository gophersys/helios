import logging

from flask import jsonify, request

from src.lib.audit import log_audit
from src.lib.decorators import require_permissions
from src.lib.errors import bad_request, conflict, not_found
from src.lib.permissions import Permissions
from src.lib.types import ApiResponse
from src.services.database.prisma import get_db_client

from .types import BoardRevisionCreateRequest, BoardRevisionUpdateRequest

logger = logging.getLogger(__name__)


def _serialize_revision(r) -> dict:
    return {
        "id": r.id,
        "boardId": r.boardId,
        "version": r.version,
        "status": r.status,
        "notes": r.notes,
        "createdAt": r.createdAt.isoformat(),
        "updatedAt": r.updatedAt.isoformat(),
    }


# ── Board Revisions CRUD ─────────────────────────────────


@require_permissions(Permissions.PRODUCTS_MANAGE)
def create_board_revision(product_id: str, board_id: str):
    db = get_db_client()

    # Validate board exists and belongs to product
    board = db.board.find_first(
        where={"id": board_id, "productId": product_id}
    )
    if not board:
        return not_found("Board not found")

    data, error = BoardRevisionCreateRequest.from_json(request.get_json())
    if error:
        return bad_request(error)

    existing = db.boardrevision.find_first(
        where={"boardId": board_id, "version": data.version}
    )
    if existing:
        return conflict(f"Board revision '{data.version}' already exists for this board")

    revision = db.boardrevision.create(
        data={
            "boardId": board_id,
            "version": data.version,
            "status": data.status,
            "notes": data.notes,
        },
    )

    log_audit("boardRevision.create", "BoardRevision", revision.id, {
        "boardName": board.name, "version": data.version, "status": data.status,
    })
    return jsonify(ApiResponse.ok(_serialize_revision(revision)).to_dict()), 201


@require_permissions(Permissions.PRODUCTS_MANAGE)
def update_board_revision(product_id: str, board_id: str, revision_id: str):
    db = get_db_client()

    # Validate board exists and belongs to product
    board = db.board.find_first(
        where={"id": board_id, "productId": product_id}
    )
    if not board:
        return not_found("Board not found")

    revision = db.boardrevision.find_first(
        where={"id": revision_id, "boardId": board_id},
    )
    if not revision:
        return not_found("Board revision not found")

    data, error = BoardRevisionUpdateRequest.from_json(request.get_json())
    if error:
        return bad_request(error)

    if data.version and data.version != revision.version:
        dup = db.boardrevision.find_first(
            where={"boardId": board_id, "version": data.version}
        )
        if dup:
            return conflict(f"Board revision '{data.version}' already exists for this board")

    update_data = data.to_update_data()
    if update_data:
        db.boardrevision.update(
            where={"id": revision_id},
            data=update_data,
        )

    # Re-fetch
    updated = db.boardrevision.find_unique(
        where={"id": revision_id},
    )

    log_audit("boardRevision.update", "BoardRevision", revision_id, {
        "version": revision.version, "changes": update_data,
    })
    return jsonify(ApiResponse.ok(_serialize_revision(updated)).to_dict()), 200


@require_permissions(Permissions.PRODUCTS_MANAGE)
def delete_board_revision(product_id: str, board_id: str, revision_id: str):
    db = get_db_client()

    # Validate board exists and belongs to product
    board = db.board.find_first(
        where={"id": board_id, "productId": product_id}
    )
    if not board:
        return not_found("Board not found")

    revision = db.boardrevision.find_first(
        where={"id": revision_id, "boardId": board_id}
    )
    if not revision:
        return not_found("Board revision not found")

    db.boardrevision.delete(where={"id": revision_id})
    log_audit("boardRevision.delete", "BoardRevision", revision_id, {
        "version": revision.version,
    })
    return jsonify(ApiResponse.ok({"deleted": True}).to_dict()), 200
