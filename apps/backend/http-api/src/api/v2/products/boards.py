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
    """Serialize a Board DB record to an API response dict."""
    data = {
        "id": b.id,
        "productId": b.productId,
        "name": b.name,
        "ckBoardsFamily": getattr(b, "ckBoardsFamily", None),
        "vendor": getattr(b, "vendor", "corekinect"),
        "description": b.description,
        "active": b.active,
        "createdAt": b.createdAt.isoformat(),
        "updatedAt": b.updatedAt.isoformat(),
    }
    if hasattr(b, "revisions") and b.revisions is not None:
        data["revisionCount"] = len(b.revisions)
    return data


@require_permissions(Permissions.PRODUCTS_VIEW)
def list_boards(product_id: str):
    """List all boards for a product."""
    db = get_db_client()
    product = db.product.find_unique(where={"id": product_id})
    if not product:
        return not_found("Product not found")

    boards = db.board.find_many(
        where={"productId": product_id},
        order={"name": "asc"},
        include={"revisions": {"include": {"targets": True}}},
    )
    return jsonify(ApiResponse.ok([_serialize_board(b) for b in boards]).to_dict()), 200


@require_permissions(Permissions.PRODUCTS_MANAGE)
def create_board(product_id: str):
    """Create a new board for a product with optional inline revisions."""
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

    # Check ckBoardsFamily uniqueness
    existing_ck = db.board.find_first(where={"ckBoardsFamily": data.ckBoardsFamily})
    if existing_ck:
        return conflict(f"Board with ckBoardsFamily '{data.ckBoardsFamily}' already exists")

    create_data = {
        "productId": product_id,
        "name": data.name,
        "ckBoardsFamily": data.ckBoardsFamily,
        "vendor": data.vendor,
        "description": data.description,
        "active": data.active,
    }

    # Create inline revisions if provided
    if data.revisions:
        rev_creates = []
        for r in data.revisions:
            rev_data = {
                "version": r["version"],
                "ckBoardsName": r["ckBoardsName"],
                "socs": r["socs"],
            }
            if r.get("deviceType") is not None:
                rev_data["deviceType"] = r["deviceType"]
            if r.get("deviceVariant") is not None:
                rev_data["deviceVariant"] = r["deviceVariant"]
            if r.get("targets"):
                rev_data["targets"] = {
                    "create": [
                        {"role": t.role, "soc": t.soc, "appId": t.appId}
                        for t in r["targets"]
                    ],
                }
            rev_creates.append(rev_data)
        create_data["revisions"] = {"create": rev_creates}

    board = db.board.create(
        data=create_data,
        include={"revisions": {"include": {"targets": True}}},
    )
    log_audit("board.create", "Board", board.id, {
        "productName": product.name, "name": data.name,
    })
    return jsonify(ApiResponse.ok(_serialize_board(board)).to_dict()), 201


@require_permissions(Permissions.PRODUCTS_VIEW)
def get_board(product_id: str, board_id: str):
    """Get a board with its revisions and targets."""
    db = get_db_client()
    board = db.board.find_first(
        where={"id": board_id, "productId": product_id},
        include={
            "revisions": {
                "order_by": {"version": "asc"},
                "include": {"targets": True},
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
    """Serialize a BoardRevision DB record to an API response dict."""
    result = {
        "id": r.id,
        "boardId": r.boardId,
        "version": r.version,
        "ckBoardsName": getattr(r, "ckBoardsName", None),
        "socs": getattr(r, "socs", []),
        "deviceType": getattr(r, "deviceType", None),
        "deviceVariant": getattr(r, "deviceVariant", None),
        "status": r.status,
        "notes": r.notes,
        "createdAt": r.createdAt.isoformat(),
        "updatedAt": r.updatedAt.isoformat(),
    }
    if hasattr(r, "targets") and r.targets is not None:
        result["targets"] = [{"id": t.id, "role": t.role, "soc": t.soc, "appId": t.appId} for t in r.targets]
    else:
        result["targets"] = []
    return result


@require_permissions(Permissions.PRODUCTS_MANAGE)
def update_board(product_id: str, board_id: str):
    """Update a board's properties."""
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
        include={"revisions": {"include": {"targets": True}}},
    )
    log_audit("board.update", "Board", board_id, {
        "name": existing.name, "changes": data.to_update_data(),
    })
    return jsonify(ApiResponse.ok(_serialize_board(board)).to_dict()), 200


@require_permissions(Permissions.PRODUCTS_MANAGE)
def delete_board(product_id: str, board_id: str):
    """Delete a board if it has no revisions."""
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
