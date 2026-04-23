"""Health, readiness, and drain endpoints."""

from datetime import datetime, timezone

from flask import Blueprint, current_app, jsonify

health_bp = Blueprint("health", __name__)


@health_bp.route("/health")
def health():
    """Liveness probe — always returns 200 (even during drain).

    K8s must NOT restart the pod during graceful drain. The build
    may still be running. Only /ready should return 503.
    """
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
    """Readiness probe — returns 503 when draining or not initialized.

    When draining, K8s removes the pod from Service endpoints so no
    new job notifications or traffic arrives. The pod stays alive
    (liveness still 200) until the in-progress build finishes.
    """
    from src.worker.loop import get_worker_state

    state = get_worker_state()
    if not state:
        return jsonify({"ready": False, "reason": "worker not initialized"}), 503

    if state.status == "draining":
        return jsonify({"ready": False, "reason": "draining — finishing current build"}), 503

    return jsonify({"ready": True}), 200


@health_bp.route("/drain", methods=["POST"])
def drain():
    """PreStop hook target — marks the worker as draining.

    Called by K8s preStop lifecycle hook before SIGTERM. This:
    1. Sets worker status to "draining"
    2. /ready starts returning 503 → removed from Service endpoints
    3. Worker loop finishes current build, then exits
    4. K8s waits up to terminationGracePeriodSeconds (2400s)
    """
    from src.worker.loop import get_worker_state

    state = get_worker_state()
    if state:
        state.set_draining()
        return jsonify(state.to_dict()), 200
    else:
        return jsonify({"error": "worker not initialized"}), 503
