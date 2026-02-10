import logging
import math
from typing import Any

from flask import jsonify, request

from src.lib.audit import log_audit
from src.lib.decorators import require_permissions
from src.lib.errors import bad_request, conflict, not_found
from src.lib.permissions import Permissions
from src.lib.types import ApiResponse
from src.services.database.prisma import get_db_client

from .types import ChipsetCreateRequest, ChipsetUpdateRequest

logger = logging.getLogger(__name__)


def _serialize_chipset(c: Any) -> dict:
    return {
        "id": c.id,
        "name": c.name,
        "manufacturer": c.manufacturer,
        "isModem": c.isModem,
        "description": c.description,
        "active": c.active,
        "createdAt": c.createdAt.isoformat(),
        "updatedAt": c.updatedAt.isoformat(),
    }


# ── Chipsets CRUD ─────────────────────────────────────────


@require_permissions(Permissions.ADMIN_CATALOG_VIEW)
def list_chipsets():
    db = get_db_client()

    page = max(1, request.args.get("page", 1, type=int))
    limit = min(max(1, request.args.get("limit", 50, type=int)), 100)
    skip = (page - 1) * limit

    total = db.chipset.count()
    chipsets = db.chipset.find_many(
        skip=skip,
        take=limit,
        order={"name": "asc"},
    )
    return jsonify(ApiResponse.ok({
        "data": [_serialize_chipset(c) for c in chipsets],
        "pagination": {
            "page": page,
            "limit": limit,
            "total": total,
            "pages": math.ceil(total / limit) if limit > 0 else 0,
        },
    }).to_dict()), 200


@require_permissions(Permissions.ADMIN_CATALOG_MANAGE)
def create_chipset():
    data, error = ChipsetCreateRequest.from_json(request.get_json())
    if error:
        return bad_request(error)

    db = get_db_client()

    existing = db.chipset.find_unique(where={"name": data.name})
    if existing:
        return conflict("Chipset with this name already exists")

    chipset = db.chipset.create(
        data={
            "name": data.name,
            "manufacturer": data.manufacturer,
            "isModem": data.isModem,
            "description": data.description,
            "active": data.active,
        }
    )
    log_audit("chipset.create", "Chipset", chipset.id, {"name": data.name})
    return jsonify(ApiResponse.ok(_serialize_chipset(chipset)).to_dict()), 201


@require_permissions(Permissions.ADMIN_CATALOG_VIEW)
def get_chipset(chipset_id: str):
    db = get_db_client()
    chipset = db.chipset.find_unique(where={"id": chipset_id})
    if not chipset:
        return not_found("Chipset not found")
    return jsonify(ApiResponse.ok(_serialize_chipset(chipset)).to_dict()), 200


@require_permissions(Permissions.ADMIN_CATALOG_MANAGE)
def update_chipset(chipset_id: str):
    data, error = ChipsetUpdateRequest.from_json(request.get_json())
    if error:
        return bad_request(error)

    db = get_db_client()
    existing = db.chipset.find_unique(where={"id": chipset_id})
    if not existing:
        return not_found("Chipset not found")

    if data.name and data.name != existing.name:
        dup = db.chipset.find_unique(where={"name": data.name})
        if dup:
            return conflict("Chipset with this name already exists")

    chipset = db.chipset.update(
        where={"id": chipset_id},
        data=data.to_update_data(),
    )
    log_audit("chipset.update", "Chipset", chipset_id, {
        "name": existing.name, "changes": data.to_update_data(),
    })
    return jsonify(ApiResponse.ok(_serialize_chipset(chipset)).to_dict()), 200


@require_permissions(Permissions.ADMIN_CATALOG_MANAGE)
def delete_chipset(chipset_id: str):
    db = get_db_client()
    existing = db.chipset.find_unique(where={"id": chipset_id})
    if not existing:
        return not_found("Chipset not found")

    # Check for references in board revision chipsets
    brc_ref = db.boardrevisionchipset.find_first(
        where={"chipsetId": chipset_id}
    )
    if brc_ref:
        return conflict("Cannot delete chipset: it is used by board revisions")

    # Check for references in firmware builds
    build_ref = db.firmwarebuild.find_first(
        where={"chipsetId": chipset_id}
    )
    if build_ref:
        return conflict("Cannot delete chipset: it is used by firmware builds")

    db.chipset.delete(where={"id": chipset_id})
    log_audit("chipset.delete", "Chipset", chipset_id, {"name": existing.name})
    return jsonify(ApiResponse.ok({"deleted": True}).to_dict()), 200
