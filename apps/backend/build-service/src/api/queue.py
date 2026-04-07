"""Queue visibility and job detail endpoints."""

from flask import Blueprint, jsonify

queue_bp = Blueprint("queue", __name__)


@queue_bp.route("")
def queue_overview():
    """Show current worker state and active job info."""
    from src.worker.loop import get_worker_state

    state = get_worker_state()
    if not state:
        return jsonify({"error": "Worker not initialized"}), 503

    return jsonify({
        "worker": state.to_dict(),
        "currentJob": {
            "id": state.current_job_id,
            "product": state.current_job_product,
            "step": state.current_step,
        } if state.is_busy else None,
    }), 200


@queue_bp.route("/jobs")
def list_jobs():
    """List current job info. Only tracks the active job in-memory."""
    from src.worker.loop import get_worker_state

    state = get_worker_state()
    if not state:
        return jsonify({"error": "Worker not initialized"}), 503

    jobs = []
    if state.is_busy:
        jobs.append({
            "id": state.current_job_id,
            "product": state.current_job_product,
            "step": state.current_step,
            "status": "active",
        })

    return jsonify({
        "data": jobs,
        "summary": {
            "completed": state.jobs_completed,
            "failed": state.jobs_failed,
        },
    }), 200
