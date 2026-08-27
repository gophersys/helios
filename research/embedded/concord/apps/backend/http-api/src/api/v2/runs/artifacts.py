"""Artifact listing and download endpoints for test runs.

Endpoints:
  GET /v2/runs/<id>/artifacts         — List MinIO objects for a run
  GET /v2/runs/<id>/artifacts/<path>  — Download/proxy a single artifact
"""
import logging

from flask import Response, jsonify

from src.lib.decorators import require_permissions
from src.lib.errors import bad_request, internal_error, not_found
from src.lib.permissions import Permissions
from src.lib.types import ApiResponse
from src.services.database.prisma import get_db_client
from src.services.storage.client import StoragePrefixes, get_bucket_name, get_storage_client, storage_key

logger = logging.getLogger(__name__)


def _get_run_or_404(run_id: str):
    """Look up a TestRun by ID, returning (run, None) or (None, 404 response)."""
    db = get_db_client()
    run = db.testrun.find_unique(where={"id": run_id})
    if not run:
        return None, not_found(f"Run {run_id} not found")
    return run, None


@require_permissions(Permissions.VALIDATION_VIEW)
def list_artifacts(run_id: str):
    """GET /v2/runs/<id>/artifacts — List artifacts from MinIO."""
    run, err = _get_run_or_404(run_id)
    if err:
        return err

    try:
        storage = get_storage_client()
        bucket = get_bucket_name()
        # Keep MinIO path as sessions/{id}/ for backward compat
        prefix = storage_key(StoragePrefixes.SESSIONS, f"{run_id}/")

        objects = storage.list_objects(bucket, prefix=prefix, recursive=True)

        artifacts = []
        for obj in objects:
            if obj.is_dir:
                continue
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
    """GET /v2/runs/<id>/artifacts/<name> — Download artifact content.

    Proxies the file content from MinIO directly instead of redirecting to a
    presigned URL (which would point to an internal K8s service DNS unreachable
    from the browser).
    """
    # Security: reject path traversal attempts
    if '..' in name or name.startswith('/'):
        return bad_request("Invalid artifact name")

    run, err = _get_run_or_404(run_id)
    if err:
        return err

    try:
        storage = get_storage_client()
        bucket = get_bucket_name()
        # Keep MinIO path as sessions/{id}/ for backward compat
        object_name = storage_key(StoragePrefixes.SESSIONS, f"{run_id}/{name}")

        try:
            response = storage.get_object(bucket, object_name)
            data = response.read()
            response.close()
            response.release_conn()
        except Exception:
            return not_found("Artifact not found")

        # Determine content type
        content_type = "application/octet-stream"
        if name.endswith('.log') or name.endswith('.txt'):
            content_type = "text/plain; charset=utf-8"
        elif name.endswith('.jsonl') or name.endswith('.json'):
            content_type = "application/json; charset=utf-8"
        elif name.endswith('.csv'):
            content_type = "text/csv; charset=utf-8"

        return Response(
            data,
            content_type=content_type,
            headers={
                "Content-Disposition": f'attachment; filename="{name.split("/")[-1]}"',
                "Content-Length": str(len(data)),
            },
        )

    except Exception as e:
        logger.error(f"Failed to get artifact {name} for run {run_id}: {e}")
        return internal_error("Failed to download artifact")
