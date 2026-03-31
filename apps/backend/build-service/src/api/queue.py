"""Queue visibility and job detail endpoints."""

from flask import Blueprint, jsonify, request

queue_bp = Blueprint("queue", __name__)

ACTIVE_STATUSES = ["CLAIMED", "CLONING", "CONFIGURING", "COMPILING", "PACKAGING", "UPLOADING"]
ALL_STATUSES = ACTIVE_STATUSES + ["SUCCESS", "FAILED"]


def _serialize_job(j, include_worker_name=False):
    """Serialize a LocalJob model to JSON-safe dict."""
    result = {
        "id": j.id,
        "externalJobId": j.externalJobId,
        "worker": j.worker.name if include_worker_name and hasattr(j, "worker") and j.worker else j.workerId,
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
    return result


@queue_bp.route("")
def queue_overview():
    """Show current queue state: active count, status breakdown, recent failures."""
    try:
        from src.db.client import get_db

        db = get_db()

        # Count active jobs
        active = db.localjob.count(where={"status": {"in": ACTIVE_STATUSES}})

        # Count by status
        by_status = {}
        for status in ALL_STATUSES:
            count = db.localjob.count(where={"status": status})
            if count > 0:
                by_status[status] = count

        # Recent failures (last 10)
        recent_failures = db.localjob.find_many(
            where={"status": "FAILED"},
            order={"completedAt": "desc"},
            take=10,
            include={"worker": True},
        )

        return jsonify(
            {
                "active": active,
                "byStatus": by_status,
                "recentFailures": [
                    {
                        "id": j.id,
                        "externalJobId": j.externalJobId,
                        "worker": j.worker.name if j.worker else j.workerId,
                        "product": j.product,
                        "variant": j.variant,
                        "errorStep": j.errorStep,
                        "errorMessage": j.errorMessage,
                        "completedAt": j.completedAt.isoformat() if j.completedAt else None,
                    }
                    for j in recent_failures
                ],
            }
        )
    except Exception as e:
        return jsonify({"error": f"Database unavailable: {e}", "active": 0, "byStatus": {}, "recentFailures": []}), 503


@queue_bp.route("/jobs")
def list_jobs():
    """List recent local jobs with step-level progress. Pagination: ?page=1&limit=20"""
    try:
        from src.db.client import get_db

        db = get_db()

        page = max(1, int(request.args.get("page", 1)))
        limit = min(100, max(1, int(request.args.get("limit", 20))))
        skip = (page - 1) * limit

        total = db.localjob.count()
        jobs = db.localjob.find_many(
            order={"claimedAt": "desc"},
            skip=skip,
            take=limit,
            include={"worker": True},
        )

        return jsonify(
            {
                "jobs": [_serialize_job(j, include_worker_name=True) for j in jobs],
                "pagination": {
                    "page": page,
                    "limit": limit,
                    "total": total,
                    "pages": (total + limit - 1) // limit if total > 0 else 0,
                },
            }
        )
    except Exception as e:
        return jsonify({"error": f"Database unavailable: {e}", "jobs": [], "pagination": {}}), 503


@queue_bp.route("/jobs/<job_id>")
def get_job(job_id):
    """Single job detail with full step timeline."""
    try:
        from src.db.client import get_db

        db = get_db()

        job = db.localjob.find_unique(
            where={"id": job_id},
            include={"worker": True},
        )

        if not job:
            return jsonify({"error": "Job not found"}), 404

        return jsonify({"job": _serialize_job(job, include_worker_name=True)})
    except Exception as e:
        return jsonify({"error": f"Database unavailable: {e}"}), 503
