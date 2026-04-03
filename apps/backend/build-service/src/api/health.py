"""Health and readiness endpoints."""

from flask import Blueprint, current_app, jsonify
from datetime import datetime, timezone

health_bp = Blueprint("health", __name__)


@health_bp.route("/health")
def health():
    """Basic health check with service status summary."""
    try:
        from src.db.client import get_db

        db = get_db()
        workers = db.worker.count()
        active_jobs = db.localjob.count(
            where={
                "status": {
                    "in": [
                        "CLAIMED",
                        "CLONING",
                        "CONFIGURING",
                        "COMPILING",
                        "PACKAGING",
                        "UPLOADING",
                    ]
                }
            }
        )
        db_ok = True
    except Exception:
        workers = 0
        active_jobs = 0
        db_ok = False

    return jsonify(
        {
            "status": "healthy",
            "service": "build-service",
            "worker_id": getattr(current_app.config.get("BUILD_SERVICE_CONFIG"), "worker_id", "unknown"),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "database": "connected" if db_ok else "unavailable",
            "workers": workers,
            "activeJobs": active_jobs,
        }
    )


@health_bp.route("/ready")
def ready():
    """Readiness probe - returns 503 if not ready."""
    try:
        from src.db.client import get_db

        db = get_db()
        db.worker.count()
        return jsonify({"ready": True}), 200
    except Exception as e:
        return jsonify({"ready": False, "error": str(e)}), 503
