"""Fixture design CRUD — versioned fixture hardware specs."""

import logging
import math
from typing import Any, Dict

from flask import jsonify, request
from database import Json

from src.lib.audit import log_audit
from src.lib.decorators import require_permissions
from src.lib.errors import bad_request, conflict, internal_error, not_found
from src.lib.permissions import Permissions
from src.lib.types import ApiResponse
from src.services.database.prisma import get_db_client

logger = logging.getLogger(__name__)

_DESIGN_INCLUDE = {
    "boardRevision": {"include": {"board": {"include": {"product": True}}}},
    "fixtures": True,
}


def _serialize_design(design) -> Dict[str, Any]:
    data = {
        "id": design.id,
        "name": design.name,
        "boardRevisionId": design.boardRevisionId,
        "revision": design.revision,
        "capabilities": design.capabilities or [],
        "profileTemplate": design.profileTemplate,
        "schematicUrl": getattr(design, "schematicUrl", None),
        "bomUrl": getattr(design, "bomUrl", None),
        "assemblyGuide": getattr(design, "assemblyGuide", None),
        "notes": getattr(design, "notes", None),
        "createdAt": design.createdAt.isoformat(),
        "updatedAt": design.updatedAt.isoformat(),
    }
    if hasattr(design, "boardRevision") and design.boardRevision:
        rev = design.boardRevision
        data["boardRevision"] = {
            "id": rev.id,
            "version": rev.version,
            "ckBoardsName": getattr(rev, "ckBoardsName", None),
        }
        if hasattr(rev, "board") and rev.board:
            data["boardRevision"]["boardName"] = rev.board.name
            if hasattr(rev.board, "product") and rev.board.product:
                data["productName"] = rev.board.product.name
    if hasattr(design, "fixtures") and design.fixtures is not None:
        data["fixtureCount"] = len(design.fixtures)
    return data


def _serialize_design_summary(design) -> Dict[str, Any]:
    data = {
        "id": design.id,
        "name": design.name,
        "boardRevisionId": design.boardRevisionId,
        "revision": design.revision,
        "capabilities": design.capabilities or [],
        "fixtureCount": len(design.fixtures) if hasattr(design, "fixtures") and design.fixtures else 0,
        "createdAt": design.createdAt.isoformat(),
    }
    if hasattr(design, "boardRevision") and design.boardRevision:
        rev = design.boardRevision
        data["boardRevision"] = {
            "id": rev.id,
            "version": rev.version,
            "ckBoardsName": getattr(rev, "ckBoardsName", None),
        }
        if hasattr(rev, "board") and rev.board and hasattr(rev.board, "product") and rev.board.product:
            data["productName"] = rev.board.product.name
    return data


@require_permissions(Permissions.FIXTURES_VIEW)
def list_designs():
    """GET /v2/fixtures/designs — list fixture designs."""
    db = get_db_client()

    page = max(1, request.args.get("page", 1, type=int))
    limit = min(max(1, request.args.get("limit", 50, type=int)), 100)
    skip = (page - 1) * limit

    where: Dict[str, Any] = {}
    board_rev_id = request.args.get("boardRevisionId")
    if board_rev_id:
        where["boardRevisionId"] = board_rev_id

    total = db.fixturedesign.count(where=where)
    designs = db.fixturedesign.find_many(
        where=where,
        skip=skip,
        take=limit,
        order={"createdAt": "desc"},
        include=_DESIGN_INCLUDE,
    )

    pages = math.ceil(total / limit) if limit > 0 else 0
    return jsonify(ApiResponse.ok({
        "data": [_serialize_design_summary(d) for d in designs],
        "pagination": {"page": page, "limit": limit, "total": total, "pages": pages},
    }).to_dict()), 200


@require_permissions(Permissions.FIXTURES_VIEW)
def get_design(design_id: str):
    """GET /v2/fixtures/designs/<id> — get fixture design detail."""
    db = get_db_client()
    design = db.fixturedesign.find_unique(where={"id": design_id}, include=_DESIGN_INCLUDE)
    if not design:
        return not_found("Fixture design not found")
    return jsonify(ApiResponse.ok(_serialize_design(design)).to_dict()), 200


@require_permissions(Permissions.FIXTURES_MANAGE)
def create_design():
    """POST /v2/fixtures/designs — create a new fixture design."""
    db = get_db_client()
    data = request.get_json()
    if not data:
        return bad_request("Request body required")

    name = (data.get("name") or "").strip()
    if not name:
        return bad_request("name is required")

    board_revision_id = (data.get("boardRevisionId") or "").strip()
    if not board_revision_id:
        return bad_request("boardRevisionId is required")

    revision = (data.get("revision") or "").strip()
    if not revision:
        return bad_request("revision is required")

    # Validate board revision exists
    rev = db.boardrevision.find_unique(where={"id": board_revision_id})
    if not rev:
        return not_found("Board revision not found")

    # Check duplicate name
    existing = db.fixturedesign.find_unique(where={"name": name})
    if existing:
        return conflict(f"Design '{name}' already exists")

    capabilities = data.get("capabilities") or []
    if isinstance(capabilities, str):
        capabilities = [c.strip() for c in capabilities.split(",") if c.strip()]

    profile_template = data.get("profileTemplate") or {}

    design = db.fixturedesign.create(
        data={
            "name": name,
            "boardRevisionId": board_revision_id,
            "revision": revision,
            "capabilities": capabilities,
            "profileTemplate": Json(profile_template),
            "schematicUrl": (data.get("schematicUrl") or "").strip() or None,
            "bomUrl": (data.get("bomUrl") or "").strip() or None,
            "assemblyGuide": (data.get("assemblyGuide") or "").strip() or None,
            "notes": (data.get("notes") or "").strip() or None,
        },
        include=_DESIGN_INCLUDE,
    )
    log_audit("fixtureDesign.create", "FixtureDesign", design.id, {"name": name, "revision": revision})
    return jsonify(ApiResponse.ok(_serialize_design(design)).to_dict()), 201


@require_permissions(Permissions.FIXTURES_MANAGE)
def update_design(design_id: str):
    """PUT /v2/fixtures/designs/<id> — update fixture design."""
    db = get_db_client()
    design = db.fixturedesign.find_unique(where={"id": design_id})
    if not design:
        return not_found("Fixture design not found")

    data = request.get_json()
    if not data:
        return bad_request("Request body required")

    update_data = {}
    if "name" in data:
        name = (data["name"] or "").strip()
        if name and name != design.name:
            existing = db.fixturedesign.find_unique(where={"name": name})
            if existing:
                return conflict(f"Design '{name}' already exists")
            update_data["name"] = name
    if "revision" in data:
        update_data["revision"] = (data["revision"] or "").strip()
    if "capabilities" in data:
        caps = data["capabilities"]
        if isinstance(caps, str):
            caps = [c.strip() for c in caps.split(",") if c.strip()]
        update_data["capabilities"] = caps
    if "profileTemplate" in data:
        update_data["profileTemplate"] = Json(data["profileTemplate"] or {})
    if "notes" in data:
        update_data["notes"] = (data["notes"] or "").strip() or None
    if "schematicUrl" in data:
        update_data["schematicUrl"] = (data["schematicUrl"] or "").strip() or None
    if "bomUrl" in data:
        update_data["bomUrl"] = (data["bomUrl"] or "").strip() or None

    if not update_data:
        return bad_request("No fields to update")

    updated = db.fixturedesign.update(where={"id": design_id}, data=update_data, include=_DESIGN_INCLUDE)
    log_audit("fixtureDesign.update", "FixtureDesign", design_id, {"fields": list(update_data.keys())})
    return jsonify(ApiResponse.ok(_serialize_design(updated)).to_dict()), 200


@require_permissions(Permissions.FIXTURES_MANAGE)
def delete_design(design_id: str):
    """DELETE /v2/fixtures/designs/<id> — delete fixture design."""
    db = get_db_client()
    design = db.fixturedesign.find_unique(where={"id": design_id}, include={"fixtures": True})
    if not design:
        return not_found("Fixture design not found")

    if design.fixtures and len(design.fixtures) > 0:
        return conflict(f"Cannot delete — {len(design.fixtures)} fixture(s) use this design")

    db.fixturedesign.delete(where={"id": design_id})
    log_audit("fixtureDesign.delete", "FixtureDesign", design_id, {"name": design.name})
    return jsonify(ApiResponse.ok({"deleted": True}).to_dict()), 200


@require_permissions(Permissions.FIXTURES_VIEW)
def get_design_profile(design_id: str):
    """GET /v2/fixtures/designs/<id>/profile — get the raw profile template JSON."""
    db = get_db_client()
    design = db.fixturedesign.find_unique(where={"id": design_id})
    if not design:
        return not_found("Fixture design not found")
    return jsonify(ApiResponse.ok(design.profileTemplate).to_dict()), 200
