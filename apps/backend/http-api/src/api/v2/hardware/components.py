from io import BytesIO

from flask import jsonify, request

from src.lib.audit import log_audit
from src.lib.decorators import require_permissions
from src.lib.errors import bad_request, conflict, internal_error, not_found
from src.lib.permissions import Permissions
from src.lib.types import ApiResponse
from src.services.database.prisma import get_db_client
from src.services.storage.client import get_hardware_bucket_name, get_storage_client

from .shared import ALLOWED_IMAGE_EXTENSIONS, MIME_TYPES, presigned_url
from .types import ComponentCreateRequest, ComponentUpdateRequest, RevisionCreateRequest, RevisionUpdateRequest


def _serialize_component(c, include_revisions=False) -> dict:
    data = {
        "id": c.id,
        "name": c.name,
        "description": c.description,
        "category": c.category,
        "manufacturer": c.manufacturer,
        "partNumber": c.partNumber,
        "imageKey": c.imageKey,
        "imageUrl": presigned_url(c.imageKey),
        "createdAt": c.createdAt.isoformat(),
        "updatedAt": c.updatedAt.isoformat(),
    }
    if hasattr(c, "revisions") and c.revisions is not None:
        data["revisionCount"] = len(c.revisions)
        if include_revisions:
            data["revisions"] = [_serialize_revision(r) for r in c.revisions]
    return data


def _serialize_revision(r) -> dict:
    return {
        "id": r.id,
        "componentId": r.componentId,
        "version": r.version,
        "status": r.status,
        "releaseNotes": r.releaseNotes,
        "createdAt": r.createdAt.isoformat(),
        "updatedAt": r.updatedAt.isoformat(),
    }


# ── Components CRUD ─────────────────────────────────────────


@require_permissions(Permissions.ADMIN_HARDWARE_VIEW)
def list_components():
    db = get_db_client()
    components = db.hardwarecomponent.find_many(
        order={"name": "asc"},
        include={"revisions": True},
    )
    return jsonify(ApiResponse.ok([_serialize_component(c) for c in components]).to_dict()), 200


@require_permissions(Permissions.ADMIN_HARDWARE_MANAGE)
def create_component():
    data, error = ComponentCreateRequest.from_json(request.get_json())
    if error:
        return bad_request(error)

    db = get_db_client()

    existing = db.hardwarecomponent.find_first(
        where={"OR": [{"name": data.name}, {"partNumber": data.partNumber}]}
    )
    if existing:
        field = "name" if existing.name == data.name else "part number"
        return conflict(f"Component with this {field} already exists")

    component = db.hardwarecomponent.create(
        data={
            "name": data.name,
            "description": data.description,
            "category": data.category,
            "manufacturer": data.manufacturer,
            "partNumber": data.partNumber,
        },
        include={"revisions": True},
    )
    log_audit("component.create", "HardwareComponent", component.id, {"name": data.name, "category": data.category})
    return jsonify(ApiResponse.ok(_serialize_component(component)).to_dict()), 201


@require_permissions(Permissions.ADMIN_HARDWARE_VIEW)
def get_component(component_id: str):
    db = get_db_client()
    component = db.hardwarecomponent.find_unique(
        where={"id": component_id},
        include={"revisions": {"order_by": {"version": "asc"}}},
    )
    if not component:
        return not_found("Component not found")
    return jsonify(ApiResponse.ok(_serialize_component(component, include_revisions=True)).to_dict()), 200


@require_permissions(Permissions.ADMIN_HARDWARE_MANAGE)
def update_component(component_id: str):
    data, error = ComponentUpdateRequest.from_json(request.get_json())
    if error:
        return bad_request(error)

    db = get_db_client()
    existing = db.hardwarecomponent.find_unique(where={"id": component_id})
    if not existing:
        return not_found("Component not found")

    # Check uniqueness for name/partNumber
    if data.name and data.name != existing.name:
        dup = db.hardwarecomponent.find_unique(where={"name": data.name})
        if dup:
            return conflict("Component with this name already exists")
    if data.partNumber and data.partNumber != existing.partNumber:
        dup = db.hardwarecomponent.find_unique(where={"partNumber": data.partNumber})
        if dup:
            return conflict("Component with this part number already exists")

    component = db.hardwarecomponent.update(
        where={"id": component_id},
        data=data.to_update_data(),
        include={"revisions": True},
    )
    log_audit("component.update", "HardwareComponent", component_id, {"name": existing.name, "changes": data.to_update_data()})
    return jsonify(ApiResponse.ok(_serialize_component(component)).to_dict()), 200


@require_permissions(Permissions.ADMIN_HARDWARE_MANAGE)
def delete_component(component_id: str):
    db = get_db_client()
    existing = db.hardwarecomponent.find_unique(
        where={"id": component_id},
        include={"revisions": True},
    )
    if not existing:
        return not_found("Component not found")

    # Check if any revisions are referenced in assembly BOMs
    if existing.revisions:
        rev_ids = [r.id for r in existing.revisions]
        bom_refs = db.assemblyrevisioncomponent.find_first(
            where={"hardwareRevisionId": {"in": rev_ids}}
        )
        if bom_refs:
            return conflict("Cannot delete component: one or more revisions are referenced in assembly BOMs")

    # Delete image from MinIO if exists
    if existing.imageKey:
        try:
            client = get_storage_client()
            client.remove_object(get_hardware_bucket_name(), existing.imageKey)
        except Exception:
            pass  # Best effort

    db.hardwarecomponent.delete(where={"id": component_id})
    log_audit("component.delete", "HardwareComponent", component_id, {"name": existing.name, "category": existing.category})
    return jsonify(ApiResponse.ok({"deleted": True}).to_dict()), 200


# ── Image upload ─────────────────────────────────────────────


@require_permissions(Permissions.ADMIN_HARDWARE_MANAGE)
def upload_component_image(component_id: str):
    db = get_db_client()
    component = db.hardwarecomponent.find_unique(where={"id": component_id})
    if not component:
        return not_found("Component not found")

    if "file" not in request.files:
        return bad_request("No file provided")

    file = request.files["file"]
    if not file.filename:
        return bad_request("No file selected")

    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        return bad_request(f"Invalid file type. Allowed: {', '.join(ALLOWED_IMAGE_EXTENSIONS)}")

    object_key = f"components/{component_id}/hero.{ext}"

    try:
        client = get_storage_client()
        bucket = get_hardware_bucket_name()

        # Remove old image if exists with different extension
        if component.imageKey and component.imageKey != object_key:
            try:
                client.remove_object(bucket, component.imageKey)
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

        updated = db.hardwarecomponent.update(
            where={"id": component_id},
            data={"imageKey": object_key},
            include={"revisions": True},
        )
        log_audit("component.imageUpload", "HardwareComponent", component_id, {"name": component.name})
        return jsonify(ApiResponse.ok(_serialize_component(updated)).to_dict()), 200
    except Exception as e:
        return internal_error(f"Failed to upload image: {str(e)}")


# ── Revisions ────────────────────────────────────────────────


@require_permissions(Permissions.ADMIN_HARDWARE_MANAGE)
def create_revision(component_id: str):
    db = get_db_client()
    component = db.hardwarecomponent.find_unique(where={"id": component_id})
    if not component:
        return not_found("Component not found")

    data, error = RevisionCreateRequest.from_json(request.get_json())
    if error:
        return bad_request(error)

    # Check duplicate version
    existing = db.hardwarerevision.find_first(
        where={"componentId": component_id, "version": data.version}
    )
    if existing:
        return conflict(f"Revision '{data.version}' already exists for this component")

    revision = db.hardwarerevision.create(
        data={
            "componentId": component_id,
            "version": data.version,
            "status": data.status,
            "releaseNotes": data.releaseNotes,
        }
    )
    log_audit("revision.create", "HardwareRevision", revision.id, {"componentName": component.name, "version": data.version, "status": data.status})
    return jsonify(ApiResponse.ok(_serialize_revision(revision)).to_dict()), 201


@require_permissions(Permissions.ADMIN_HARDWARE_MANAGE)
def update_revision(component_id: str, revision_id: str):
    db = get_db_client()
    revision = db.hardwarerevision.find_first(
        where={"id": revision_id, "componentId": component_id}
    )
    if not revision:
        return not_found("Revision not found")

    data, error = RevisionUpdateRequest.from_json(request.get_json())
    if error:
        return bad_request(error)

    # Check version uniqueness if changing
    if data.version and data.version != revision.version:
        dup = db.hardwarerevision.find_first(
            where={"componentId": component_id, "version": data.version}
        )
        if dup:
            return conflict(f"Revision '{data.version}' already exists for this component")

    updated = db.hardwarerevision.update(
        where={"id": revision_id},
        data=data.to_update_data(),
    )
    log_audit("revision.update", "HardwareRevision", revision_id, {"version": revision.version, "changes": data.to_update_data()})
    return jsonify(ApiResponse.ok(_serialize_revision(updated)).to_dict()), 200


@require_permissions(Permissions.ADMIN_HARDWARE_MANAGE)
def delete_revision(component_id: str, revision_id: str):
    db = get_db_client()
    revision = db.hardwarerevision.find_first(
        where={"id": revision_id, "componentId": component_id}
    )
    if not revision:
        return not_found("Revision not found")

    # Check if revision is referenced in any assembly BOM
    bom_ref = db.assemblyrevisioncomponent.find_first(
        where={"hardwareRevisionId": revision_id}
    )
    if bom_ref:
        return conflict("Cannot delete revision: it is referenced in an assembly BOM")

    db.hardwarerevision.delete(where={"id": revision_id})
    log_audit("revision.delete", "HardwareRevision", revision_id, {"version": revision.version})
    return jsonify(ApiResponse.ok({"deleted": True}).to_dict()), 200
