"""Worker management endpoints."""

from flask import Blueprint, jsonify, request

workers_bp = Blueprint("workers", __name__)

ACTIVE_STATUSES = ["CLAIMED", "CLONING", "CONFIGURING", "COMPILING", "PACKAGING", "UPLOADING"]


def _serialize_worker(w, include_recent_jobs=False):
    """Serialize a Worker model to JSON-safe dict."""
    result = {
        "id": w.id,
        "name": w.name,
        "ncsVersion": w.ncsVersion,
        "status": w.status,
        "lastHeartbeat": w.lastHeartbeat.isoformat() if w.lastHeartbeat else None,
        "registeredAt": w.registeredAt.isoformat() if w.registeredAt else None,
        "currentJobId": w.currentJobId,
        "capabilities": w.capabilities,
    }

    if include_recent_jobs and hasattr(w, "jobs") and w.jobs is not None:
        result["recentJobs"] = [_serialize_job(j) for j in w.jobs]
    elif not include_recent_jobs:
        result["recentJobs"] = len(w.jobs) if hasattr(w, "jobs") and w.jobs is not None else 0

    return result


def _serialize_job(j):
    """Serialize a LocalJob model to JSON-safe dict."""
    return {
        "id": j.id,
        "externalJobId": j.externalJobId,
        "status": j.status,
        "step": j.step,
        "stepProgress": j.stepProgress,
        "stepMessage": j.stepMessage,
        "product": j.product,
        "board": j.board,
        "variant": j.variant,
        "branch": j.branch,
        "commitSha": j.commitSha,
        "errorStep": j.errorStep,
        "errorMessage": j.errorMessage,
        "retryCount": j.retryCount,
        "timeline": {
            "claimed": j.claimedAt.isoformat() if j.claimedAt else None,
            "cloneStarted": j.cloneStartedAt.isoformat() if j.cloneStartedAt else None,
            "buildStarted": j.buildStartedAt.isoformat() if j.buildStartedAt else None,
            "uploadStarted": j.uploadStartedAt.isoformat() if j.uploadStartedAt else None,
            "completed": j.completedAt.isoformat() if j.completedAt else None,
        },
    }


@workers_bp.route("")
def list_workers():
    """List all workers with status, last heartbeat, and active job count."""
    try:
        from src.db.client import get_db

        db = get_db()
        workers = db.worker.find_many(
            include={"jobs": {"where": {"status": {"in": ACTIVE_STATUSES}}}},
            order={"name": "asc"},
        )
        return jsonify({"workers": [_serialize_worker(w) for w in workers]})
    except Exception as e:
        return jsonify({"error": f"Database unavailable: {e}", "workers": []}), 503


@workers_bp.route("/<worker_id>")
def get_worker(worker_id):
    """Single worker detail with recent jobs (last 20)."""
    try:
        from src.db.client import get_db

        db = get_db()
        worker = db.worker.find_unique(
            where={"id": worker_id},
            include={
                "jobs": {
                    "take": 20,
                    "order": {"claimedAt": "desc"},
                }
            },
        )

        if not worker:
            return jsonify({"error": "Worker not found"}), 404

        return jsonify({"worker": _serialize_worker(worker, include_recent_jobs=True)})
    except Exception as e:
        return jsonify({"error": f"Database unavailable: {e}"}), 503


@workers_bp.route("/<worker_id>", methods=["PATCH"])
def update_worker(worker_id):
    """Update worker status (e.g., set to DRAINING)."""
    try:
        from src.db.client import get_db

        db = get_db()

        body = request.get_json()
        if not body:
            return jsonify({"error": "Request body required"}), 400

        allowed_fields = {"status"}
        update_data = {k: v for k, v in body.items() if k in allowed_fields}

        if not update_data:
            return jsonify({"error": f"No valid fields to update. Allowed: {allowed_fields}"}), 400

        if "status" in update_data:
            valid_statuses = ["IDLE", "BUILDING", "OFFLINE", "DRAINING"]
            if update_data["status"] not in valid_statuses:
                return jsonify({"error": f"Invalid status. Must be one of: {valid_statuses}"}), 400

        worker = db.worker.update(
            where={"id": worker_id},
            data=update_data,
        )

        if not worker:
            return jsonify({"error": "Worker not found"}), 404

        return jsonify({"worker": _serialize_worker(worker)})
    except Exception as e:
        error_msg = str(e)
        if "Record to update not found" in error_msg:
            return jsonify({"error": "Worker not found"}), 404
        return jsonify({"error": f"Database unavailable: {e}"}), 503
