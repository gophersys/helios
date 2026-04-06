import logging

from flask import jsonify, request

from src.lib.audit import log_audit
from src.lib.decorators import require_permissions
from src.lib.errors import bad_request, conflict, not_found
from src.lib.permissions import Permissions
from src.lib.types import ApiResponse
from src.services.database.prisma import get_db_client

from .types import (
    BoardRevisionCreateRequest,
    BoardRevisionUpdateRequest,
    TargetCreateRequest,
    TargetUpdateRequest,
)

logger = logging.getLogger(__name__)


def _serialize_target(t) -> dict:
    return {
        "id": t.id,
        "role": t.role,
        "soc": t.soc,
        "appId": t.appId,
    }


def _serialize_revision(r) -> dict:
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
        result["targets"] = [_serialize_target(t) for t in r.targets]
    else:
        result["targets"] = []
    return result


# ── Board Revisions CRUD ─────────────────────────────────


@require_permissions(Permissions.PRODUCTS_VIEW)
def get_board_revision(product_id: str, board_id: str, revision_id: str):
    """GET /v2/products/<pid>/boards/<bid>/revisions/<rid> — get a single revision."""
    db = get_db_client()
    revision = db.boardrevision.find_first(
        where={"id": revision_id, "boardId": board_id},
        include={"targets": True, "board": True},
    )
    if not revision:
        return not_found("Board revision not found")
    if revision.board and revision.board.productId != product_id:
        return not_found("Board revision not found")
    return jsonify(ApiResponse.ok(_serialize_revision(revision)).to_dict()), 200


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

    # Check ckBoardsName uniqueness across all revisions
    existing_ck = db.boardrevision.find_first(
        where={"ckBoardsName": data.ckBoardsName}
    )
    if existing_ck:
        return conflict(f"Board revision with ckBoardsName '{data.ckBoardsName}' already exists")

    create_data = {
        "boardId": board_id,
        "version": data.version,
        "ckBoardsName": data.ckBoardsName,
        "socs": data.socs,
        "status": data.status,
        "notes": data.notes,
    }
    if data.deviceType is not None:
        create_data["deviceType"] = data.deviceType
    if data.deviceVariant is not None:
        create_data["deviceVariant"] = data.deviceVariant

    revision = db.boardrevision.create(
        data=create_data,
        include={"targets": True},
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
        include={"targets": True},
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


# ── Product Targets CRUD ─────────────────────────────────


@require_permissions(Permissions.PRODUCTS_MANAGE)
def create_target(product_id: str, board_id: str, revision_id: str):
    db = get_db_client()

    board = db.board.find_first(where={"id": board_id, "productId": product_id})
    if not board:
        return not_found("Board not found")

    revision = db.boardrevision.find_first(
        where={"id": revision_id, "boardId": board_id},
        include={"targets": True},
    )
    if not revision:
        return not_found("Board revision not found")

    data, error = TargetCreateRequest.from_json(request.get_json())
    if error:
        return bad_request(error)

    # Check role uniqueness within this revision
    for t in (revision.targets or []):
        if t.role == data.role:
            return conflict(f"Target with role '{data.role}' already exists on this revision")
        if t.appId == data.appId:
            return conflict(f"Target with appId {data.appId} already exists on this revision")

    target = db.producttarget.create(
        data={
            "boardRevisionId": revision_id,
            "role": data.role,
            "soc": data.soc,
            "appId": data.appId,
        },
    )

    log_audit("productTarget.create", "ProductTarget", target.id, {
        "revisionId": revision_id, "role": data.role, "soc": data.soc, "appId": data.appId,
    })
    return jsonify(ApiResponse.ok(_serialize_target(target)).to_dict()), 201


@require_permissions(Permissions.PRODUCTS_MANAGE)
def update_target(product_id: str, board_id: str, revision_id: str, target_id: str):
    db = get_db_client()

    board = db.board.find_first(where={"id": board_id, "productId": product_id})
    if not board:
        return not_found("Board not found")

    revision = db.boardrevision.find_first(
        where={"id": revision_id, "boardId": board_id},
        include={"targets": True},
    )
    if not revision:
        return not_found("Board revision not found")

    target = None
    for t in (revision.targets or []):
        if t.id == target_id:
            target = t
            break
    if not target:
        return not_found("Target not found on this revision")

    data, error = TargetUpdateRequest.from_json(request.get_json())
    if error:
        return bad_request(error)

    # Check uniqueness constraints for role and appId changes
    if data._has_role and data.role and data.role != target.role:
        for t in (revision.targets or []):
            if t.id != target_id and t.role == data.role:
                return conflict(f"Target with role '{data.role}' already exists on this revision")
    if data._has_app_id and data.appId is not None and data.appId != target.appId:
        for t in (revision.targets or []):
            if t.id != target_id and t.appId == data.appId:
                return conflict(f"Target with appId {data.appId} already exists on this revision")

    update_data = data.to_update_data()
    updated = db.producttarget.update(
        where={"id": target_id},
        data=update_data,
    )

    log_audit("productTarget.update", "ProductTarget", target_id, {
        "revisionId": revision_id, "changes": update_data,
    })
    return jsonify(ApiResponse.ok(_serialize_target(updated)).to_dict()), 200


@require_permissions(Permissions.PRODUCTS_MANAGE)
def delete_target(product_id: str, board_id: str, revision_id: str, target_id: str):
    db = get_db_client()

    board = db.board.find_first(where={"id": board_id, "productId": product_id})
    if not board:
        return not_found("Board not found")

    revision = db.boardrevision.find_first(
        where={"id": revision_id, "boardId": board_id},
        include={"targets": True},
    )
    if not revision:
        return not_found("Board revision not found")

    found = False
    for t in (revision.targets or []):
        if t.id == target_id:
            found = True
            break
    if not found:
        return not_found("Target not found on this revision")

    db.producttarget.delete(where={"id": target_id})
    log_audit("productTarget.delete", "ProductTarget", target_id, {
        "revisionId": revision_id,
    })
    return jsonify(ApiResponse.ok({"deleted": True}).to_dict()), 200
