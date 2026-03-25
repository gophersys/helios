"""Telemetry API endpoints for post-analysis of validation runs.

Serves telemetry manifest and per-channel JSONL data written by
TelemetryStreamer during test execution.

Endpoints:
  GET /v2/sessions/:id/telemetry/manifest  - Telemetry manifest (JSON)
  GET /v2/sessions/:id/telemetry/:channel  - Channel data (JSONL)
"""
import json
import logging

from flask import Response, jsonify

from src.lib.decorators import require_auth
from src.lib.errors import internal_error, not_found
from src.lib.types import ApiResponse
from src.services.database.prisma import get_db_client
from src.services.storage.client import (
    StoragePrefixes,
    get_bucket_name,
    get_storage_client,
    storage_key,
)

logger = logging.getLogger(__name__)


def _get_session_or_404(db, run_id: str):
    session = db.session.find_unique(where={"id": run_id})
    if not session:
        return None, not_found("Validation run not found")
    return session, None


@require_auth
def get_telemetry_manifest(run_id: str):
    """GET /v2/sessions/<id>/telemetry/manifest

    Read the telemetry manifest.json written by TelemetryStreamer from MinIO
    and return it as JSON inside the standard API envelope.
    """
    db = get_db_client()
    session, err = _get_session_or_404(db, run_id)
    if err:
        return err

    try:
        storage = get_storage_client()
        bucket = get_bucket_name()
        object_name = storage_key(
            StoragePrefixes.SESSIONS,
            f"{run_id}/telemetry/manifest.json",
        )

        try:
            storage.stat_object(bucket, object_name)
        except Exception:
            return not_found("Telemetry manifest not found for this run")

        response = storage.get_object(bucket, object_name)
        content = response.read()
        response.close()
        response.release_conn()

        manifest = json.loads(content.decode("utf-8"))
        return jsonify(ApiResponse.ok(manifest).to_dict()), 200

    except Exception as e:
        logger.error(f"Failed to get telemetry manifest for run {run_id}: {e}")
        return internal_error("Failed to fetch telemetry manifest")


@require_auth
def get_telemetry_channel(run_id: str, channel: str):
    """GET /v2/sessions/<id>/telemetry/<channel>

    Read a telemetry channel JSONL file (e.g. power.jsonl, uart_app.jsonl)
    from MinIO and return the raw content as application/x-ndjson.
    """
    db = get_db_client()
    session, err = _get_session_or_404(db, run_id)
    if err:
        return err

    # Sanitize channel name — only allow alphanumeric, underscore, hyphen
    safe_channel = "".join(c for c in channel if c.isalnum() or c in ("_", "-"))
    if not safe_channel or safe_channel != channel:
        return not_found("Invalid channel name")

    try:
        storage = get_storage_client()
        bucket = get_bucket_name()
        object_name = storage_key(
            StoragePrefixes.SESSIONS,
            f"{run_id}/telemetry/{safe_channel}.jsonl",
        )

        try:
            stat = storage.stat_object(bucket, object_name)
        except Exception:
            return not_found(f"Telemetry channel '{channel}' not found")

        response = storage.get_object(bucket, object_name)
        data = response.read()
        response.close()
        response.release_conn()

        return Response(
            data,
            mimetype="application/x-ndjson",
            headers={
                "Content-Length": str(len(data)),
                "Cache-Control": "public, max-age=3600",
            },
        )

    except Exception as e:
        logger.error(
            f"Failed to get telemetry channel {channel} for run {run_id}: {e}"
        )
        return internal_error("Failed to fetch telemetry channel")
