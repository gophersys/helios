import logging

from flask import jsonify, redirect

from src.lib.decorators import require_permissions
from src.lib.errors import bad_request, internal_error, not_found
from src.lib.permissions import Permissions
from src.lib.types import ApiResponse
from src.services.database.prisma import get_db_client
from src.services.storage.client import StoragePrefixes, get_bucket_name, get_storage_client, storage_key

logger = logging.getLogger(__name__)


@require_permissions(Permissions.VALIDATION_VIEW)
def list_artifacts(run_id: str):
    """GET /v2/validation/runs/<id>/artifacts — List artifacts from MinIO."""
    db = get_db_client()

    session = db.session.find_unique(where={"id": run_id})
    if not session:
        return not_found("Validation run not found")

    try:
        storage = get_storage_client()
        bucket = get_bucket_name()
        prefix = storage_key(StoragePrefixes.SESSIONS, f"{run_id}/")

        objects = storage.list_objects(bucket, prefix=prefix, recursive=True)

        artifacts = []
        for obj in objects:
            if obj.is_dir:
                continue
            # Strip prefix to get relative name
            name = obj.object_name
            if name.startswith(prefix):
                name = name[len(prefix):]
            artifacts.append({
                "name": name,
                "objectName": obj.object_name,
                "size": obj.size,
                "lastModified": obj.last_modified.isoformat() if obj.last_modified else None,
                "contentType": obj.content_type,
            })

        return jsonify(ApiResponse.ok(artifacts).to_dict()), 200

    except Exception as e:
        logger.error(f"Failed to list artifacts for run {run_id}: {e}")
        return jsonify(ApiResponse.ok([]).to_dict()), 200


@require_permissions(Permissions.VALIDATION_VIEW)
def download_artifact(run_id: str, name: str):
    """GET /v2/validation/runs/<id>/artifacts/<name> — Download artifact via presigned URL."""
    # Security: reject path traversal attempts
    if '..' in name or name.startswith('/'):
        return bad_request("Invalid artifact name")

    db = get_db_client()

    session = db.session.find_unique(where={"id": run_id})
    if not session:
        return not_found("Validation run not found")

    try:
        storage = get_storage_client()
        bucket = get_bucket_name()
        object_name = storage_key(StoragePrefixes.SESSIONS, f"{run_id}/{name}")

        # Verify the object exists
        try:
            storage.stat_object(bucket, object_name)
        except Exception:
            return not_found("Artifact not found")

        from datetime import timedelta
        url = storage.presigned_get_object(
            bucket,
            object_name,
            expires=timedelta(hours=1),
        )

        return redirect(url)

    except Exception as e:
        logger.error(f"Failed to get artifact {name} for run {run_id}: {e}")
        return internal_error("Failed to download artifact")
