"""Job notification and control endpoints.

POST /jobs/notify — receive push notifications from HTTP-API (returns 202)
POST /jobs/cancel — cancel the current build (if any)
"""

import logging

from flask import Blueprint, jsonify, request

log = logging.getLogger("build-service")

jobs_bp = Blueprint("jobs", __name__)

# The job queue is injected by main.py after creation
_job_queue = None


def set_job_queue(queue):
    """Set the global job queue (called from main.py)."""
    global _job_queue
    _job_queue = queue


@jobs_bp.route("/notify", methods=["POST"])
def notify():
    """Receive a build job notification from the HTTP-API.

    Accepts: {"jobId": "...", "priority": 50}
    Returns: 202 Accepted (fire-and-forget)
    """
    data = request.get_json(silent=True) or {}
    job_id = data.get("jobId")

    if not job_id:
        return jsonify({"error": "jobId required"}), 400

    if not _job_queue:
        log.warning("Job notification received but queue not initialized")
        return jsonify({"error": "Queue not ready"}), 503

    priority = int(data.get("priority", 50))
    _job_queue.enqueue(job_id, priority=priority)

    return jsonify({"status": "accepted", "jobId": job_id}), 202


@jobs_bp.route("/cancel", methods=["POST"])
def cancel():
    """Request cancellation of the current build.

    Flips the worker's cancel_event. The build's subprocess streaming
    loop (executor.py or docker_runner.py) sees the event on its next
    line read and kills the underlying process / docker container.
    The pipeline then reports the job as CANCELLED to the HTTP-API
    rather than FAILED.

    Cancellation is best-effort: the kill propagates within ~1 second
    of the next stdout line on a healthy build, but a build wedged
    waiting on I/O may take longer. Cancellation does not abort an
    already-running stage transition — only the build subprocess.

    Returns:
      200 — no active build to cancel (idempotent).
      202 — cancellation requested; the worker will tear the build down.
    """
    from src.worker.loop import get_worker_state

    state = get_worker_state()
    if not state or not state.is_busy:
        return jsonify({"status": "no_active_build"}), 200

    data = request.get_json(silent=True) or {}
    reason = (data.get("reason") or "user")[:64]

    state.request_cancel(reason=reason)
    log.info("Cancellation requested for job %s (reason=%s)",
             state.current_job_id, reason)

    return jsonify({
        "status": "cancel_requested",
        "currentJobId": state.current_job_id,
        "reason": reason,
    }), 202
