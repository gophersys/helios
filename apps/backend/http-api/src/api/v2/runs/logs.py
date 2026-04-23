"""Log streaming and artifact download endpoints for test runs.

Endpoints:
  POST /v2/runs/<id>/report/log-chunk — Ingest log chunk from pytest reporter
  GET  /v2/runs/<id>/logs/<path>      — Stream log file with offset support
  GET  /v2/runs/<id>/download         — Generate ZIP and return presigned URL
  GET  /v2/runs/<id>/manifest         — Get/generate telemetry manifest
"""
import atexit
import base64
import io
import json
import logging
import threading
import zipfile
from datetime import timedelta

from flask import Response, jsonify, request

from src.lib.decorators import require_auth, require_permissions
from src.lib.errors import bad_request, internal_error, not_found
from src.lib.permissions import Permissions
from src.lib.types import ApiResponse
from src.services.database.prisma import get_db_client
from src.services.storage.client import (
    StoragePrefixes,
    get_bucket_name,
    get_storage_client,
    storage_key,
)

from src.api.v2.runs.types import ReportLogChunkRequest
from .ws import emit_to_run

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# In-memory log buffer — avoids O(n^2) read-append-write on every chunk
# ---------------------------------------------------------------------------
_log_buffers: dict[str, bytearray] = {}  # key: "run_id/file" -> accumulated bytes
_log_lock = threading.Lock()
_flush_timer: threading.Timer | None = None
_FLUSH_INTERVAL_S = 30.0


def _buffer_key(run_id: str, file: str) -> str:
    """Build the in-memory buffer dict key for a run's log file."""
    return f"{run_id}/{file}"


def _flush_log_buffers() -> None:
    """Flush all buffered log data to MinIO."""
    global _flush_timer
    with _log_lock:
        if not _log_buffers:
            _flush_timer = None
            return
        to_flush = dict(_log_buffers)
        _log_buffers.clear()
        _flush_timer = None

    try:
        storage = get_storage_client()
        bucket = get_bucket_name()
    except Exception as e:
        logger.error(f"Failed to get storage client for log flush: {e}")
        # Put data back so it isn't lost
        with _log_lock:
            for k, v in to_flush.items():
                if k in _log_buffers:
                    _log_buffers[k] = v + _log_buffers[k]
                else:
                    _log_buffers[k] = v
        return

    for buf_key, new_bytes in to_flush.items():
        run_id, file = buf_key.split("/", 1)
        # Keep MinIO path as sessions/{id}/ for backward compat
        object_name = storage_key(StoragePrefixes.SESSIONS, f"{run_id}/logs/{file}")
        try:
            # Fetch existing data (may not exist yet)
            existing_data = b""
            try:
                response = storage.get_object(bucket, object_name)
                existing_data = response.read()
                response.close()
                response.release_conn()
            except Exception:
                pass

            combined = existing_data + bytes(new_bytes)
            storage.put_object(
                bucket,
                object_name,
                io.BytesIO(combined),
                length=len(combined),
                content_type="text/plain",
            )
        except Exception as e:
            logger.error(f"Failed to flush log buffer for {buf_key}: {e}")


def _schedule_flush() -> None:
    """Schedule a periodic flush if not already scheduled."""
    global _flush_timer
    with _log_lock:
        if _flush_timer is None:
            _flush_timer = threading.Timer(_FLUSH_INTERVAL_S, _flush_log_buffers)
            _flush_timer.daemon = True
            _flush_timer.start()


def flush_log_buffers_for_run(run_id: str) -> None:
    """Flush any buffered log data for a specific run (called on run finish)."""
    keys_to_flush: list[str] = []
    buffers_to_flush: dict[str, bytearray] = {}

    with _log_lock:
        for k in list(_log_buffers.keys()):
            if k.startswith(f"{run_id}/"):
                keys_to_flush.append(k)
                buffers_to_flush[k] = _log_buffers.pop(k)

    if not buffers_to_flush:
        return

    try:
        storage = get_storage_client()
        bucket = get_bucket_name()
    except Exception as e:
        logger.error(f"Failed to get storage for run flush {run_id}: {e}")
        return

    for buf_key, new_bytes in buffers_to_flush.items():
        _, file = buf_key.split("/", 1)
        object_name = storage_key(StoragePrefixes.SESSIONS, f"{run_id}/logs/{file}")
        try:
            existing_data = b""
            try:
                response = storage.get_object(bucket, object_name)
                existing_data = response.read()
                response.close()
                response.release_conn()
            except Exception:
                pass

            combined = existing_data + bytes(new_bytes)
            storage.put_object(
                bucket,
                object_name,
                io.BytesIO(combined),
                length=len(combined),
                content_type="text/plain",
            )
        except Exception as e:
            logger.error(f"Failed to flush log buffer for {buf_key}: {e}")


# Ensure buffers are flushed on process exit
atexit.register(_flush_log_buffers)


def _get_run_or_404(run_id: str):
    """Look up a TestRun by ID, returning (run, None) or (None, 404 response)."""
    db = get_db_client()
    run = db.testrun.find_unique(where={"id": run_id})
    if not run:
        return None, not_found(f"Run {run_id} not found")
    return run, None


@require_auth
def report_log_chunk(run_id: str):
    """POST /v2/runs/<id>/report/log-chunk — Receive log chunk from test runner.

    The pytest reporter sends log chunks as tests execute. We:
    1. Buffer the chunk in memory (flushed to MinIO every 30s or on run finish)
    2. Broadcast to WebSocket subscribers immediately for live streaming
    """
    data, error = ReportLogChunkRequest.from_json(request.get_json())
    if error or data is None:
        return bad_request(error)

    run, err = _get_run_or_404(run_id)
    if err:
        return err

    # Decode base64 data
    try:
        chunk_bytes = base64.b64decode(data.data)
    except Exception:
        return bad_request("Invalid base64 data")

    # Buffer chunk in memory — avoids O(n^2) read-append-write per chunk
    buf_key = _buffer_key(run_id, data.file)
    with _log_lock:
        if buf_key not in _log_buffers:
            _log_buffers[buf_key] = bytearray()
        _log_buffers[buf_key].extend(chunk_bytes)

    # Schedule periodic flush to MinIO
    _schedule_flush()

    # Resolve targetId and slotIndex from deviceSerial for per-slot WebSocket routing
    target_id = None
    slot_index = None
    if data.device_serial:
        db = get_db_client()
        target = db.runtarget.find_first(
            where={"runId": run_id, "serialNumber": data.device_serial},
        )
        if target:
            target_id = target.id
            slot_index = target.slotIndex

    # Broadcast to WebSocket subscribers immediately
    ws_payload = {
        "runId": run_id,
        "file": data.file,
        "offset": data.offset,
        "data": data.data,
        "testName": data.test_name,
        "timestamp": data.timestamp,
    }
    if target_id:
        ws_payload["targetId"] = target_id
    if slot_index is not None:
        ws_payload["slotIndex"] = slot_index
    emit_to_run("run_log_chunk", ws_payload, run_id)

    logger.debug(f"Log chunk received for run {run_id}: {data.file} +{len(chunk_bytes)} bytes at offset {data.offset}")
    return jsonify(ApiResponse.ok({"received": True}).to_dict()), 200


@require_permissions(Permissions.VALIDATION_VIEW)
def get_log_file(run_id: str, file_path: str):
    """GET /v2/runs/<id>/logs/<path> — Fetch log file with optional offset.

    Supports partial reads via ?offset=N query param for reconnection scenarios.
    Returns raw bytes with X-Offset and X-Total-Size headers.
    """
    run, err = _get_run_or_404(run_id)
    if err:
        return err

    # Parse offset from query string
    offset = request.args.get("offset", 0, type=int)
    if offset < 0:
        offset = 0

    try:
        storage = get_storage_client()
        bucket = get_bucket_name()
        object_name = storage_key(StoragePrefixes.SESSIONS, f"{run_id}/logs/{file_path}")

        # Check if object exists and get its size
        try:
            stat = storage.stat_object(bucket, object_name)
        except Exception:
            return not_found("Log file not found")

        total_size = stat.size

        # If offset is beyond file size, return empty
        if offset >= total_size:
            return Response(
                b"",
                mimetype="text/plain",
                headers={
                    "X-Offset": str(total_size),
                    "X-Total-Size": str(total_size),
                },
            )

        # Fetch with range if offset > 0
        if offset > 0:
            response = storage.get_object(
                bucket,
                object_name,
                offset=offset,
                length=total_size - offset,
            )
        else:
            response = storage.get_object(bucket, object_name)

        data = response.read()
        response.close()
        response.release_conn()

        return Response(
            data,
            mimetype="text/plain",
            headers={
                "X-Offset": str(offset),
                "X-Total-Size": str(total_size),
            },
        )

    except Exception as e:
        logger.error(f"Failed to get log file {file_path} for run {run_id}: {e}")
        return internal_error("Failed to fetch log file")


@require_permissions(Permissions.VALIDATION_VIEW)
def download_run(run_id: str):
    """GET /v2/runs/<id>/download — Generate ZIP and return presigned URL.

    Checks if ZIP already exists at sessions/{run_id}/run.zip.
    If not, generates it from all files in the run folder.
    """
    run, err = _get_run_or_404(run_id)
    if err:
        return err

    try:
        storage = get_storage_client()
        bucket = get_bucket_name()
        prefix = storage_key(StoragePrefixes.SESSIONS, f"{run_id}/")
        zip_object_name = storage_key(StoragePrefixes.SESSIONS, f"{run_id}/run.zip")

        # Check if ZIP already exists
        zip_exists = False
        try:
            storage.stat_object(bucket, zip_object_name)
            zip_exists = True
        except Exception:
            pass

        if not zip_exists:
            # Generate ZIP from all files in the run folder
            objects = list(storage.list_objects(bucket, prefix=prefix, recursive=True))
            if not objects:
                return not_found("No artifacts found for this run")

            # Create ZIP in memory
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
                for obj in objects:
                    if obj.is_dir:
                        continue
                    if obj.object_name.endswith("/run.zip"):
                        continue

                    rel_path = obj.object_name
                    if rel_path.startswith(prefix):
                        rel_path = rel_path[len(prefix):]

                    try:
                        response = storage.get_object(bucket, obj.object_name)
                        content = response.read()
                        response.close()
                        response.release_conn()
                        zf.writestr(rel_path, content)
                    except Exception as e:
                        logger.warning(f"Failed to add {obj.object_name} to ZIP: {e}")
                        continue

            # Upload ZIP
            zip_buffer.seek(0)
            zip_data = zip_buffer.getvalue()
            storage.put_object(
                bucket,
                zip_object_name,
                io.BytesIO(zip_data),
                length=len(zip_data),
                content_type="application/zip",
            )

        # Generate presigned URL
        url = storage.presigned_get_object(
            bucket,
            zip_object_name,
            expires=timedelta(hours=1),
        )

        return jsonify(ApiResponse.ok({"url": url}).to_dict()), 200

    except Exception as e:
        logger.error(f"Failed to generate download for run {run_id}: {e}")
        return internal_error("Failed to generate download")


@require_permissions(Permissions.VALIDATION_VIEW)
def get_manifest(run_id: str):
    """GET /v2/runs/<id>/manifest — Return the manifest.json for the run.

    The manifest contains metadata about the run configuration, test list,
    and artifact locations.
    """
    run, err = _get_run_or_404(run_id)
    if err:
        return err

    try:
        storage = get_storage_client()
        bucket = get_bucket_name()
        object_name = storage_key(StoragePrefixes.SESSIONS, f"{run_id}/manifest.json")

        # Check if manifest exists
        try:
            storage.stat_object(bucket, object_name)
        except Exception:
            # Generate manifest from run data if it doesn't exist
            manifest = _generate_manifest(run, run_id)
            return jsonify(ApiResponse.ok(manifest).to_dict()), 200

        # Fetch existing manifest
        response = storage.get_object(bucket, object_name)
        content = response.read()
        response.close()
        response.release_conn()

        manifest = json.loads(content.decode("utf-8"))
        return jsonify(ApiResponse.ok(manifest).to_dict()), 200

    except Exception as e:
        logger.error(f"Failed to get manifest for run {run_id}: {e}")
        return internal_error("Failed to fetch manifest")


def _generate_manifest(run, run_id: str) -> dict:
    """Generate a manifest from run data when no stored manifest exists."""
    db = get_db_client()

    # Get the first target for this run
    target = db.runtarget.find_first(where={"runId": run_id})

    # Get test executions
    executions_data = []
    if target:
        execs = db.testexecution.find_many(
            where={"targetId": target.id},
            order={"executionIndex": "asc"},
        )
        for ex in execs:
            executions_data.append({
                "executionId": ex.id,
                "name": ex.name,
                "module": ex.module,
                "status": ex.status,
            })

    return {
        "runId": run_id,
        "name": run.name,
        "status": run.status,
        "productId": run.productId,
        "config": run.config if hasattr(run, "config") and run.config else {},
        "startedAt": run.startedAt.isoformat() if run.startedAt else None,
        "completedAt": run.completedAt.isoformat() if run.completedAt else None,
        "target": {
            "id": target.id if target else None,
            "serialNumber": target.serialNumber if target else None,
            "status": target.status if target else None,
        } if target else None,
        "executions": executions_data,
        "passedCount": run.passedCount,
        "failedCount": run.failedCount,
        "completedCount": run.completedCount,
    }
