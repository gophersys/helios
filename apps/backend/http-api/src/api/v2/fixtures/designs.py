"""FixtureDesign CRUD endpoints for fixture hardware versioning."""

import logging
import math
from typing import Any, Dict

from database import Json
from flask import jsonify, request

from src.lib.audit import log_audit
from src.lib.decorators import require_permissions
from src.lib.errors import bad_request, conflict, internal_error, not_found
from src.lib.permissions import Permissions
from src.lib.types import ApiResponse
from src.services.database.prisma import get_db_client

from .types import FixtureDesignCreateRequest, FixtureDesignUpdateRequest

logger = logging.getLogger(__name__)


def _serialize_design(design) -> Dict[str, Any]:
    """Serialize a FixtureDesign model to API response."""
    data = {
        "id": design.id,
        "name": design.name,
        "product": design.product,
        "revision": design.revision,
        "capabilities": design.capabilities or [],
        "profileTemplate": design.profileTemplate,
        "schematicUrl": design.schematicUrl,
        "bomUrl": design.bomUrl,
        "assemblyGuide": design.assemblyGuide,
        "notes": design.notes,
        "createdAt": design.createdAt.isoformat(),
        "updatedAt": design.updatedAt.isoformat(),
    }

    # Include bench count if loaded
    if hasattr(design, "testBenches") and design.testBenches is not None:
        data["benchCount"] = len(design.testBenches)

    return data


def _serialize_design_summary(design) -> Dict[str, Any]:
    """Serialize a FixtureDesign for list view."""
    return {
        "id": design.id,
        "name": design.name,
        "product": design.product,
        "revision": design.revision,
        "capabilities": design.capabilities or [],
        "benchCount": len(design.testBenches) if hasattr(design, "testBenches") and design.testBenches else 0,
        "createdAt": design.createdAt.isoformat(),
    }


@require_permissions(Permissions.FIXTURES_VIEW)
def list_designs():
    """GET /v2/validation/designs - List all fixture designs."""
    db = get_db_client()

    page = max(1, request.args.get("page", 1, type=int))
    limit = min(max(1, request.args.get("limit", 50, type=int)), 100)
    skip = (page - 1) * limit

    # Filters
    where: Dict[str, Any] = {}
    product = request.args.get("product")
    if product:
        where["product"] = product.lower()

    try:
        total = db.fixturedesign.count(where=where)
        designs = db.fixturedesign.find_many(
            where=where,
            skip=skip,
            take=limit,
            order={"createdAt": "desc"},
            include={"testBenches": True},
        )

        pages = math.ceil(total / limit) if limit > 0 else 0

        return jsonify(ApiResponse.ok({
            "data": [_serialize_design_summary(d) for d in designs],
            "pagination": {
                "page": page,
                "limit": limit,
                "total": total,
                "pages": pages,
            },
        }).to_dict()), 200

    except Exception as e:
        logger.error("Failed to list fixture designs: %s", e)
        return internal_error("Failed to list fixture designs")


@require_permissions(Permissions.FIXTURES_VIEW)
def get_design(design_id: str):
    """GET /v2/validation/designs/<id> - Get fixture design details."""
    db = get_db_client()

    try:
        design = db.fixturedesign.find_unique(
            where={"id": design_id},
            include={"testBenches": True},
        )
        if not design:
            return not_found(f"Fixture design not found: {design_id}")

        return jsonify(ApiResponse.ok(_serialize_design(design)).to_dict()), 200

    except Exception as e:
        logger.error("Failed to get fixture design %s: %s", design_id, e)
        return internal_error("Failed to get fixture design")


@require_permissions(Permissions.FIXTURES_MANAGE)
def create_design():
    """POST /v2/validation/designs - Create a new fixture design."""
    data, error = FixtureDesignCreateRequest.from_json(request.get_json())
    if error:
        return bad_request(error)

    db = get_db_client()

    # Check for duplicate name
    existing = db.fixturedesign.find_unique(where={"name": data.name})
    if existing:
        return conflict(f"Fixture design with name '{data.name}' already exists")

    try:
        design = db.fixturedesign.create(
            data={
                "name": data.name,
                "product": data.product,
                "revision": data.revision,
                "capabilities": data.capabilities,
                "profileTemplate": Json(data.profile_template),
                "schematicUrl": data.schematic_url,
                "bomUrl": data.bom_url,
                "assemblyGuide": data.assembly_guide,
                "notes": data.notes,
            },
        )

        log_audit("validation.design.create", "FixtureDesign", design.id, {
            "name": data.name,
            "product": data.product,
            "revision": data.revision,
        })

        return jsonify(ApiResponse.created(_serialize_design(design)).to_dict()), 201

    except Exception as e:
        logger.error("Failed to create fixture design: %s", e)
        return internal_error("Failed to create fixture design")


@require_permissions(Permissions.FIXTURES_MANAGE)
def update_design(design_id: str):
    """PATCH /v2/validation/designs/<id> - Update a fixture design."""
    data, error = FixtureDesignUpdateRequest.from_json(request.get_json())
    if error:
        return bad_request(error)

    db = get_db_client()

    design = db.fixturedesign.find_unique(where={"id": design_id})
    if not design:
        return not_found(f"Fixture design not found: {design_id}")

    update_data = data.to_update_data()
    if not update_data:
        return bad_request("No valid fields to update")

    # Check name uniqueness if changing
    if "name" in update_data and update_data["name"] != design.name:
        existing = db.fixturedesign.find_unique(where={"name": update_data["name"]})
        if existing:
            return conflict(f"Fixture design with name '{update_data['name']}' already exists")

    # Wrap JSON fields
    if "profileTemplate" in update_data:
        update_data["profileTemplate"] = Json(update_data["profileTemplate"]) if update_data["profileTemplate"] else None

    try:
        updated = db.fixturedesign.update(
            where={"id": design_id},
            data=update_data,
        )

        log_audit("validation.design.update", "FixtureDesign", design_id, update_data)

        return jsonify(ApiResponse.ok(_serialize_design(updated)).to_dict()), 200

    except Exception as e:
        logger.error("Failed to update fixture design %s: %s", design_id, e)
        return internal_error("Failed to update fixture design")


@require_permissions(Permissions.FIXTURES_MANAGE)
def delete_design(design_id: str):
    """DELETE /v2/validation/designs/<id> - Delete a fixture design."""
    db = get_db_client()

    design = db.fixturedesign.find_unique(
        where={"id": design_id},
        include={"testBenches": True},
    )
    if not design:
        return not_found(f"Fixture design not found: {design_id}")

    # Don't allow deletion if benches are using this design
    if design.testBenches:
        bench_ids = [b.stationId for b in design.testBenches[:5]]
        return bad_request(
            f"Cannot delete: {len(design.testBenches)} test bench(es) use this design: {bench_ids}"
        )

    try:
        db.fixturedesign.delete(where={"id": design_id})

        log_audit("validation.design.delete", "FixtureDesign", design_id, {
            "name": design.name,
        })

        return jsonify(ApiResponse.deleted().to_dict()), 200

    except Exception as e:
        logger.error("Failed to delete fixture design %s: %s", design_id, e)
        return internal_error("Failed to delete fixture design")


@require_permissions(Permissions.FIXTURES_VIEW)
def get_design_profile(design_id: str):
    """GET /v2/validation/designs/<id>/profile - Get the fixture profile template.

    Returns the profileTemplate JSON that would be used by test benches
    using this design. This is the raw template without bench-specific overrides.
    """
    db = get_db_client()

    try:
        design = db.fixturedesign.find_unique(where={"id": design_id})
        if not design:
            return not_found(f"Fixture design not found: {design_id}")

        # Return the profile template with metadata
        profile = dict(design.profileTemplate) if design.profileTemplate else {}
        profile["_designId"] = design.id
        profile["_designName"] = design.name
        profile["_designRevision"] = design.revision
        profile["capabilities"] = design.capabilities or []

        return jsonify(ApiResponse.ok(profile).to_dict()), 200

    except Exception as e:
        logger.error("Failed to get design profile %s: %s", design_id, e)
        return internal_error("Failed to get design profile")
