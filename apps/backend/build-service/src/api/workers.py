"""Worker management endpoints."""

from flask import Blueprint, jsonify, request

workers_bp = Blueprint("workers", __name__)


@workers_bp.route("")
def list_workers():
    """List this worker's state."""
    from src.worker.loop import get_worker_state

    state = get_worker_state()
    if not state:
        return jsonify({"data": []}), 200

    return jsonify({"data": [state.to_dict()]}), 200


@workers_bp.route("/<worker_id>")
def get_worker(worker_id):
    """Get worker detail."""
    from src.worker.loop import get_worker_state

    state = get_worker_state()
    if not state or state.worker_id != worker_id:
        return jsonify({"error": "Worker not found"}), 404

    return jsonify({"data": state.to_dict()}), 200


@workers_bp.route("/<worker_id>", methods=["PATCH"])
def update_worker(worker_id):
    """Update worker status (e.g., set to DRAINING)."""
    from src.worker.loop import get_worker_state

    state = get_worker_state()
    if not state or state.worker_id != worker_id:
        return jsonify({"error": "Worker not found"}), 404

    body = request.get_json()
    if not body:
        return jsonify({"error": "JSON body required"}), 400

    new_status = body.get("status")
    if new_status and new_status.lower() == "draining":
        state.set_draining()

    return jsonify({"data": state.to_dict()}), 200
