"""Prometheus-compatible metrics endpoint."""

from flask import Blueprint, Response

metrics_bp = Blueprint("metrics", __name__)

ACTIVE_STATUSES = ["CLAIMED", "CLONING", "CONFIGURING", "COMPILING", "PACKAGING", "UPLOADING"]
WORKER_STATUSES = ["IDLE", "BUILDING", "OFFLINE", "DRAINING"]
JOB_STATUSES = ["CLAIMED", "CLONING", "CONFIGURING", "COMPILING", "PACKAGING", "UPLOADING", "SUCCESS", "FAILED"]


@metrics_bp.route("")
def prometheus_metrics():
    """Prometheus-compatible text format metrics."""
    lines = []

    try:
        from src.db.client import get_db

        db = get_db()

        # Worker counts by status
        lines.append("# HELP build_service_workers_total Number of registered workers")
        lines.append("# TYPE build_service_workers_total gauge")
        for status in WORKER_STATUSES:
            count = db.worker.count(where={"status": status})
            lines.append(f'build_service_workers_total{{status="{status}"}} {count}')

        lines.append("")

        # Job counts by status
        lines.append("# HELP build_service_jobs_total Total jobs by status")
        lines.append("# TYPE build_service_jobs_total counter")
        for status in JOB_STATUSES:
            count = db.localjob.count(where={"status": status})
            lines.append(f'build_service_jobs_total{{status="{status}"}} {count}')

        lines.append("")

        # Active jobs gauge
        active = db.localjob.count(where={"status": {"in": ACTIVE_STATUSES}})
        lines.append("# HELP build_service_active_jobs Currently active jobs")
        lines.append("# TYPE build_service_active_jobs gauge")
        lines.append(f"build_service_active_jobs {active}")

        lines.append("")

    except Exception:
        # Return empty metrics if DB is unavailable
        lines.append("# HELP build_service_workers_total Number of registered workers")
        lines.append("# TYPE build_service_workers_total gauge")
        lines.append("")
        lines.append("# HELP build_service_jobs_total Total jobs by status")
        lines.append("# TYPE build_service_jobs_total counter")
        lines.append("")
        lines.append("# HELP build_service_active_jobs Currently active jobs")
        lines.append("# TYPE build_service_active_jobs gauge")
        lines.append("build_service_active_jobs 0")
        lines.append("")

    return Response(
        "\n".join(lines) + "\n",
        content_type="text/plain; version=0.0.4; charset=utf-8",
    )
