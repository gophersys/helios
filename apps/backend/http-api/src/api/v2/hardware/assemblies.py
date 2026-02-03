from io import BytesIO

from flask import jsonify, request

from src.lib.decorators import require_permissions
from src.lib.errors import bad_request, conflict, internal_error, not_found
from src.lib.permissions import Permissions
from src.lib.types import ApiResponse
from src.services.database.prisma import get_db_client
from src.services.storage.client import get_hardware_bucket_name, get_storage_client

from .shared import ALLOWED_IMAGE_EXTENSIONS, MIME_TYPES, presigned_url
from .types import (
    AssemblyCreateRequest,
    AssemblyRevisionCreateRequest,
    AssemblyRevisionUpdateRequest,
    AssemblyUpdateRequest,
)


def _serialize_assembly(a, include_revisions=False) -> dict:
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


def _serialize_assembly_revision(r) -> dict:
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


def _serialize_bom_item(item) -> dict:
    data = {
        "id": item.id,
        "hardwareRevisionId": item.hardwareRevisionId,
        "quantity": item.quantity,
    }
    if hasattr(item, "hardwareRevision") and item.hardwareRevision is not None:
        hr = item.hardwareRevision
        data["hardwareRevision"] = {
            "id": hr.id,
            "version": hr.version,
            "status": hr.status,
            "componentId": hr.componentId,
        }
        if hasattr(hr, "component") and hr.component is not None:
            data["hardwareRevision"]["component"] = {
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
            "hardwareRevision": {
                "include": {
                    "component": True,
                }
            }
        }
    }
}


# ── Assembly CRUD ────────────────────────────────────────────


@require_permissions(Permissions.ADMIN_HARDWARE_VIEW)
def list_assemblies():
    db = get_db_client()
    assemblies = db.assembly.find_many(
        order={"name": "asc"},
        include={"revisions": True},
    )
    return jsonify(ApiResponse.ok([_serialize_assembly(a) for a in assemblies]).to_dict()), 200


@require_permissions(Permissions.ADMIN_HARDWARE_MANAGE)
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
    return jsonify(ApiResponse.ok(_serialize_assembly(assembly)).to_dict()), 201


@require_permissions(Permissions.ADMIN_HARDWARE_VIEW)
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


@require_permissions(Permissions.ADMIN_HARDWARE_MANAGE)
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
    return jsonify(ApiResponse.ok(_serialize_assembly(assembly)).to_dict()), 200


@require_permissions(Permissions.ADMIN_HARDWARE_MANAGE)
def delete_assembly(assembly_id: str):
    db = get_db_client()
    existing = db.assembly.find_unique(where={"id": assembly_id})
    if not existing:
        return not_found("Assembly not found")

    if existing.imageKey:
        try:
            client = get_storage_client()
            client.remove_object(get_hardware_bucket_name(), existing.imageKey)
        except Exception:
            pass

    db.assembly.delete(where={"id": assembly_id})
    return jsonify(ApiResponse.ok({"deleted": True}).to_dict()), 200


# ── Image upload ─────────────────────────────────────────────


@require_permissions(Permissions.ADMIN_HARDWARE_MANAGE)
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

    object_key = f"assemblies/{assembly_id}/hero.{ext}"

    try:
        client = get_storage_client()
        bucket = get_hardware_bucket_name()

        if assembly.imageKey and assembly.imageKey != object_key:
            try:
                client.remove_object(bucket, assembly.imageKey)
            except Exception:
                pass

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
        return jsonify(ApiResponse.ok(_serialize_assembly(updated)).to_dict()), 200
    except Exception as e:
        return internal_error(f"Failed to upload image: {str(e)}")


# ── Assembly Revisions ───────────────────────────────────────


@require_permissions(Permissions.ADMIN_HARDWARE_MANAGE)
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

    # Validate BOM hardware revision IDs exist
    if data.bom:
        hr_ids = [item.hardwareRevisionId for item in data.bom]
        found = db.hardwarerevision.find_many(where={"id": {"in": hr_ids}})
        found_ids = {r.id for r in found}
        missing = [rid for rid in hr_ids if rid not in found_ids]
        if missing:
            return bad_request(f"Hardware revision(s) not found: {', '.join(missing)}")

    revision = db.assemblyrevision.create(
        data={
            "assemblyId": assembly_id,
            "version": data.version,
            "status": data.status,
            "releaseNotes": data.releaseNotes,
            "components": {
                "create": [
                    {
                        "hardwareRevisionId": item.hardwareRevisionId,
                        "quantity": item.quantity,
                    }
                    for item in (data.bom or [])
                ]
            },
        },
        include=_REVISION_INCLUDE,
    )
    return jsonify(ApiResponse.ok(_serialize_assembly_revision(revision)).to_dict()), 201


@require_permissions(Permissions.ADMIN_HARDWARE_MANAGE)
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
        hr_ids = [item.hardwareRevisionId for item in data.bom]
        if hr_ids:
            found = db.hardwarerevision.find_many(where={"id": {"in": hr_ids}})
            found_ids = {r.id for r in found}
            missing = [rid for rid in hr_ids if rid not in found_ids]
            if missing:
                return bad_request(f"Hardware revision(s) not found: {', '.join(missing)}")

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
                    "hardwareRevisionId": item.hardwareRevisionId,
                    "quantity": item.quantity,
                }
            )

    updated = db.assemblyrevision.find_unique(
        where={"id": revision_id},
        include=_REVISION_INCLUDE,
    )
    return jsonify(ApiResponse.ok(_serialize_assembly_revision(updated)).to_dict()), 200


@require_permissions(Permissions.ADMIN_HARDWARE_MANAGE)
def delete_assembly_revision(assembly_id: str, revision_id: str):
    db = get_db_client()
    revision = db.assemblyrevision.find_first(
        where={"id": revision_id, "assemblyId": assembly_id}
    )
    if not revision:
        return not_found("Assembly revision not found")

    db.assemblyrevision.delete(where={"id": revision_id})
    return jsonify(ApiResponse.ok({"deleted": True}).to_dict()), 200
