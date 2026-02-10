import logging
from typing import Any

from flask import jsonify, request

from src.lib.audit import log_audit
from src.lib.decorators import require_permissions
from src.lib.errors import bad_request, conflict, not_found
from src.lib.permissions import Permissions
from src.lib.types import ApiResponse
from src.services.database.prisma import get_db_client

from .types import BoardCreateRequest, BoardUpdateRequest

logger = logging.getLogger(__name__)


def _serialize_board(b: Any) -> dict:
    data = {
        "id": b.id,
        "productId": b.productId,
        "name": b.name,
        "description": b.description,
        "active": b.active,
        "createdAt": b.createdAt.isoformat(),
        "updatedAt": b.updatedAt.isoformat(),
    }
    if hasattr(b, "revisions") and b.revisions is not None:
        data["revisionCount"] = len(b.revisions)
    return data


@require_permissions(Permissions.ADMIN_CATALOG_VIEW)
def list_boards(product_id: str):
    db = get_db_client()
    product = db.product.find_unique(where={"id": product_id})
    if not product:
        return not_found("Product not found")

    boards = db.board.find_many(
        where={"productId": product_id},
        order={"name": "asc"},
        include={"revisions": True},
    )
    return jsonify(ApiResponse.ok([_serialize_board(b) for b in boards]).to_dict()), 200


@require_permissions(Permissions.ADMIN_CATALOG_MANAGE)
def create_board(product_id: str):
    db = get_db_client()
    product = db.product.find_unique(where={"id": product_id})
    if not product:
        return not_found("Product not found")

    data, error = BoardCreateRequest.from_json(request.get_json())
    if error:
        return bad_request(error)

    existing = db.board.find_first(
        where={"productId": product_id, "name": data.name}
    )
    if existing:
        return conflict(f"Board '{data.name}' already exists for this product")

    board = db.board.create(
        data={
            "productId": product_id,
            "name": data.name,
            "description": data.description,
            "active": data.active,
        },
        include={"revisions": True},
    )
    log_audit("board.create", "Board", board.id, {
        "productName": product.name, "name": data.name,
    })
    return jsonify(ApiResponse.ok(_serialize_board(board)).to_dict()), 201


@require_permissions(Permissions.ADMIN_CATALOG_VIEW)
def get_board(product_id: str, board_id: str):
    db = get_db_client()
    board = db.board.find_first(
        where={"id": board_id, "productId": product_id},
        include={
            "revisions": {
                "order_by": {"version": "asc"},
                "include": {
                    "chipsets": {"include": {"chipset": True}},
                },
            },
        },
    )
    if not board:
        return not_found("Board not found")

    data = _serialize_board(board)
    # Include full revision details for get
    data["revisions"] = [_serialize_board_revision(r) for r in board.revisions]
    return jsonify(ApiResponse.ok(data).to_dict()), 200


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


@require_permissions(Permissions.ADMIN_CATALOG_MANAGE)
def update_board(product_id: str, board_id: str):
    db = get_db_client()
    existing = db.board.find_first(
        where={"id": board_id, "productId": product_id}
    )
    if not existing:
        return not_found("Board not found")

    data, error = BoardUpdateRequest.from_json(request.get_json())
    if error:
        return bad_request(error)

    if data.name and data.name != existing.name:
        dup = db.board.find_first(
            where={"productId": product_id, "name": data.name}
        )
        if dup:
            return conflict(f"Board '{data.name}' already exists for this product")

    board = db.board.update(
        where={"id": board_id},
        data=data.to_update_data(),
        include={"revisions": True},
    )
    log_audit("board.update", "Board", board_id, {
        "name": existing.name, "changes": data.to_update_data(),
    })
    return jsonify(ApiResponse.ok(_serialize_board(board)).to_dict()), 200


@require_permissions(Permissions.ADMIN_CATALOG_MANAGE)
def delete_board(product_id: str, board_id: str):
    db = get_db_client()
    existing = db.board.find_first(
        where={"id": board_id, "productId": product_id},
        include={"revisions": True},
    )
    if not existing:
        return not_found("Board not found")

    if hasattr(existing, "revisions") and existing.revisions:
        return conflict("Cannot delete board: it has revisions. Delete revisions first.")

    db.board.delete(where={"id": board_id})
    log_audit("board.delete", "Board", board_id, {"name": existing.name})
    return jsonify(ApiResponse.ok({"deleted": True}).to_dict()), 200
