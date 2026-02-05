import logging
import math
from io import BytesIO

from flask import jsonify, request

from src.lib.audit import log_audit
from src.lib.decorators import require_permissions
from src.lib.errors import bad_request, conflict, internal_error, not_found
from src.lib.permissions import Permissions
from src.lib.types import ApiResponse
from src.services.database.prisma import get_db_client
from src.services.storage.client import get_bucket_name, get_storage_client, StoragePrefixes, storage_key

logger = logging.getLogger(__name__)

from .shared import ALLOWED_IMAGE_EXTENSIONS, MIME_TYPES, presigned_url
from .types import (
    AssemblyCreateRequest,
    AssemblyRevisionCreateRequest,
    AssemblyRevisionUpdateRequest,
    AssemblyUpdateRequest,
)

from typing import Any


def _serialize_assembly(a: Any, include_revisions: bool = False) -> dict:
    data = {
        "id": a.id,
        "name": a.name,
        "description": a.description,
        "imageKey": a.imageKey,
        "imageUrl": presigned_url(a.imageKey),
        "createdAt": a.createdAt.isoformat(),
        "updatedAt": a.updatedAt.isoformat(),
    }
    if hasattr(a, "revisions") and a.revisions is not None:
        data["revisionCount"] = len(a.revisions)
        if include_revisions:
            data["revisions"] = [_serialize_assembly_revision(r) for r in a.revisions]
    return data


def _serialize_assembly_revision(r: Any) -> dict:
    data = {
        "id": r.id,
        "assemblyId": r.assemblyId,
        "version": r.version,
        "status": r.status,
        "releaseNotes": r.releaseNotes,
        "createdAt": r.createdAt.isoformat(),
        "updatedAt": r.updatedAt.isoformat(),
    }
    if hasattr(r, "components") and r.components is not None:
        data["bom"] = [_serialize_bom_item(item) for item in r.components]
    return data


def _serialize_bom_item(item: Any) -> dict:
    data = {
        "id": item.id,
        "inventoryRevisionId": item.inventoryRevisionId,
        "quantity": item.quantity,
    }
    if hasattr(item, "inventoryRevision") and item.inventoryRevision is not None:
        hr = item.inventoryRevision
        data["inventoryRevision"] = {
            "id": hr.id,
            "version": hr.version,
            "status": hr.status,
            "componentId": hr.componentId,
        }
        if hasattr(hr, "component") and hr.component is not None:
            data["inventoryRevision"]["component"] = {
                "id": hr.component.id,
                "name": hr.component.name,
                "category": hr.component.category,
                "manufacturer": hr.component.manufacturer,
                "partNumber": hr.component.partNumber,
            }
    return data


_REVISION_INCLUDE = {
    "components": {
        "include": {
            "inventoryRevision": {
                "include": {
                    "component": True,
                }
            }
        }
    }
}


# ── Assembly CRUD ────────────────────────────────────────────


@require_permissions(Permissions.ADMIN_INVENTORY_VIEW)
def list_assemblies():
    db = get_db_client()

    page = max(1, request.args.get("page", 1, type=int))
    limit = min(max(1, request.args.get("limit", 50, type=int)), 100)
    skip = (page - 1) * limit

    total = db.assembly.count()
    assemblies = db.assembly.find_many(
        skip=skip,
        take=limit,
        order={"name": "asc"},
        include={"revisions": True},
    )
    return jsonify(ApiResponse.ok({
        "data": [_serialize_assembly(a) for a in assemblies],
        "pagination": {
            "page": page,
            "limit": limit,
            "total": total,
            "pages": math.ceil(total / limit) if limit > 0 else 0,
        },
    }).to_dict()), 200


@require_permissions(Permissions.ADMIN_INVENTORY_MANAGE)
def create_assembly():
    data, error = AssemblyCreateRequest.from_json(request.get_json())
    if error:
        return bad_request(error)

    db = get_db_client()
    existing = db.assembly.find_unique(where={"name": data.name})
    if existing:
        return conflict("Assembly with this name already exists")

    assembly = db.assembly.create(
        data={
            "name": data.name,
            "description": data.description,
        },
        include={"revisions": True},
    )
    log_audit("assembly.create", "Assembly", assembly.id, {"name": data.name})
    return jsonify(ApiResponse.ok(_serialize_assembly(assembly)).to_dict()), 201


@require_permissions(Permissions.ADMIN_INVENTORY_VIEW)
def get_assembly(assembly_id: str):
    db = get_db_client()
    assembly = db.assembly.find_unique(
        where={"id": assembly_id},
        include={
            "revisions": {
                "order_by": {"version": "asc"},
                "include": _REVISION_INCLUDE,
            }
        },
    )
    if not assembly:
        return not_found("Assembly not found")
    return jsonify(ApiResponse.ok(_serialize_assembly(assembly, include_revisions=True)).to_dict()), 200


@require_permissions(Permissions.ADMIN_INVENTORY_MANAGE)
def update_assembly(assembly_id: str):
    data, error = AssemblyUpdateRequest.from_json(request.get_json())
    if error:
        return bad_request(error)

    db = get_db_client()
    existing = db.assembly.find_unique(where={"id": assembly_id})
    if not existing:
        return not_found("Assembly not found")

    if data.name and data.name != existing.name:
        dup = db.assembly.find_unique(where={"name": data.name})
        if dup:
            return conflict("Assembly with this name already exists")

    assembly = db.assembly.update(
        where={"id": assembly_id},
        data=data.to_update_data(),
        include={"revisions": True},
    )
    log_audit("assembly.update", "Assembly", assembly_id, {"name": existing.name, "changes": data.to_update_data()})
    return jsonify(ApiResponse.ok(_serialize_assembly(assembly)).to_dict()), 200


@require_permissions(Permissions.ADMIN_INVENTORY_MANAGE)
def delete_assembly(assembly_id: str):
    db = get_db_client()
    existing = db.assembly.find_unique(where={"id": assembly_id})
    if not existing:
        return not_found("Assembly not found")

    if existing.imageKey:
        try:
            client = get_storage_client()
            client.remove_object(get_bucket_name(), existing.imageKey)
        except Exception as e:
            logger.warning("Failed to remove assembly image %s: %s", existing.imageKey, e)

    db.assembly.delete(where={"id": assembly_id})
    log_audit("assembly.delete", "Assembly", assembly_id, {"name": existing.name})
    return jsonify(ApiResponse.ok({"deleted": True}).to_dict()), 200


# ── Image upload ─────────────────────────────────────────────


@require_permissions(Permissions.ADMIN_INVENTORY_MANAGE)
def upload_assembly_image(assembly_id: str):
    db = get_db_client()
    assembly = db.assembly.find_unique(where={"id": assembly_id})
    if not assembly:
        return not_found("Assembly not found")

    if "file" not in request.files:
        return bad_request("No file provided")

    file = request.files["file"]
    if not file.filename:
        return bad_request("No file selected")

    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        return bad_request(f"Invalid file type. Allowed: {', '.join(ALLOWED_IMAGE_EXTENSIONS)}")

    object_key = storage_key(StoragePrefixes.INVENTORY, f"assemblies/{assembly_id}/hero.{ext}")

    try:
        client = get_storage_client()
        bucket = get_bucket_name()

        if assembly.imageKey and assembly.imageKey != object_key:
            try:
                client.remove_object(bucket, assembly.imageKey)
            except Exception as e:
                logger.warning("Failed to remove old assembly image %s: %s", assembly.imageKey, e)

        file_data = file.read()
        client.put_object(
            bucket,
            object_key,
            BytesIO(file_data),
            length=len(file_data),
            content_type=MIME_TYPES.get(ext, "application/octet-stream"),
        )

        updated = db.assembly.update(
            where={"id": assembly_id},
            data={"imageKey": object_key},
            include={"revisions": True},
        )
        log_audit("assembly.imageUpload", "Assembly", assembly_id, {"name": assembly.name})
        return jsonify(ApiResponse.ok(_serialize_assembly(updated)).to_dict()), 200
    except Exception as e:
        logger.error("Failed to upload assembly image: %s", e)
        return internal_error("Failed to upload image")


# ── Assembly Revisions ───────────────────────────────────────


@require_permissions(Permissions.ADMIN_INVENTORY_MANAGE)
def create_assembly_revision(assembly_id: str):
    db = get_db_client()
    assembly = db.assembly.find_unique(where={"id": assembly_id})
    if not assembly:
        return not_found("Assembly not found")

    data, error = AssemblyRevisionCreateRequest.from_json(request.get_json())
    if error:
        return bad_request(error)

    existing = db.assemblyrevision.find_first(
        where={"assemblyId": assembly_id, "version": data.version}
    )
    if existing:
        return conflict(f"Revision '{data.version}' already exists for this assembly")

    # Validate BOM inventory revision IDs exist
    if data.bom:
        hr_ids = [item.inventoryRevisionId for item in data.bom]
        found = db.inventoryrevision.find_many(where={"id": {"in": hr_ids}})
        found_ids = {r.id for r in found}
        missing = [rid for rid in hr_ids if rid not in found_ids]
        if missing:
            return bad_request(f"Inventory revision(s) not found: {', '.join(missing)}")

    revision = db.assemblyrevision.create(
        data={
            "assemblyId": assembly_id,
            "version": data.version,
            "status": data.status,
            "releaseNotes": data.releaseNotes,
            "components": {
                "create": [
                    {
                        "inventoryRevisionId": item.inventoryRevisionId,
                        "quantity": item.quantity,
                    }
                    for item in (data.bom or [])
                ]
            },
        },
        include=_REVISION_INCLUDE,
    )
    log_audit("assemblyRevision.create", "AssemblyRevision", revision.id, {"assemblyName": assembly.name, "version": data.version, "status": data.status})
    return jsonify(ApiResponse.ok(_serialize_assembly_revision(revision)).to_dict()), 201


@require_permissions(Permissions.ADMIN_INVENTORY_MANAGE)
def update_assembly_revision(assembly_id: str, revision_id: str):
    db = get_db_client()
    revision = db.assemblyrevision.find_first(
        where={"id": revision_id, "assemblyId": assembly_id}
    )
    if not revision:
        return not_found("Assembly revision not found")

    data, error = AssemblyRevisionUpdateRequest.from_json(request.get_json())
    if error:
        return bad_request(error)

    if data.version and data.version != revision.version:
        dup = db.assemblyrevision.find_first(
            where={"assemblyId": assembly_id, "version": data.version}
        )
        if dup:
            return conflict(f"Revision '{data.version}' already exists for this assembly")

    # Validate BOM before any writes
    if data._has_bom and data.bom is not None:
        hr_ids = [item.inventoryRevisionId for item in data.bom]
        if hr_ids:
            found = db.inventoryrevision.find_many(where={"id": {"in": hr_ids}})
            found_ids = {r.id for r in found}
            missing = [rid for rid in hr_ids if rid not in found_ids]
            if missing:
                return bad_request(f"Inventory revision(s) not found: {', '.join(missing)}")

    # Update revision fields
    update_data = data.to_update_data()
    if update_data:
        db.assemblyrevision.update(
            where={"id": revision_id},
            data=update_data,
        )

    # Replace BOM after validation
    if data._has_bom and data.bom is not None:
        db.assemblyrevisioncomponent.delete_many(
            where={"assemblyRevisionId": revision_id}
        )
        for item in data.bom:
            db.assemblyrevisioncomponent.create(
                data={
                    "assemblyRevisionId": revision_id,
                    "inventoryRevisionId": item.inventoryRevisionId,
                    "quantity": item.quantity,
                }
            )

    updated = db.assemblyrevision.find_unique(
        where={"id": revision_id},
        include=_REVISION_INCLUDE,
    )
    log_audit("assemblyRevision.update", "AssemblyRevision", revision_id, {"version": revision.version, "changes": data.to_update_data()})
    return jsonify(ApiResponse.ok(_serialize_assembly_revision(updated)).to_dict()), 200


@require_permissions(Permissions.ADMIN_INVENTORY_MANAGE)
def delete_assembly_revision(assembly_id: str, revision_id: str):
    db = get_db_client()
    revision = db.assemblyrevision.find_first(
        where={"id": revision_id, "assemblyId": assembly_id}
    )
    if not revision:
        return not_found("Assembly revision not found")

    db.assemblyrevision.delete(where={"id": revision_id})
    log_audit("assemblyRevision.delete", "AssemblyRevision", revision_id, {"version": revision.version})
    return jsonify(ApiResponse.ok({"deleted": True}).to_dict()), 200
