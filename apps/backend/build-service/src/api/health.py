"""Health and readiness endpoints."""

from datetime import datetime, timezone

from flask import Blueprint, current_app, jsonify

health_bp = Blueprint("health", __name__)


@health_bp.route("/health")
def health():
    """Basic health check with worker status summary."""
    from src.worker.loop import get_worker_state

    state = get_worker_state()
    config = current_app.config.get("BUILD_SERVICE_CONFIG")

    return jsonify({
        "status": "healthy",
        "service": "build-service",
        "worker_id": state.worker_id if state else (config.worker_id if config else "unknown"),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "worker": state.to_dict() if state else None,
    })


@health_bp.route("/ready")
def ready():
    """Readiness probe — returns 503 if worker not initialized."""
    from src.worker.loop import get_worker_state

    state = get_worker_state()
    if state:
        return jsonify({"ready": True}), 200
    else:
        return jsonify({"ready": False, "reason": "worker not initialized"}), 503
