"""Prometheus-compatible metrics endpoint."""

from flask import Blueprint, Response

metrics_bp = Blueprint("metrics", __name__)


@metrics_bp.route("")
def prometheus_metrics():
    """Prometheus-compatible text format metrics."""
    from src.worker.loop import get_worker_state

    lines = []
    state = get_worker_state()

    if state:
        status_map = {"idle": 1, "building": 2, "draining": 3, "offline": 0}

        lines.append("# HELP build_service_worker_status Worker status (0=offline, 1=idle, 2=building, 3=draining)")
        lines.append("# TYPE build_service_worker_status gauge")
        lines.append(f'build_service_worker_status{{worker="{state.worker_id}"}} {status_map.get(state.status, 0)}')
        lines.append("")

        lines.append("# HELP build_service_jobs_completed_total Total successful builds")
        lines.append("# TYPE build_service_jobs_completed_total counter")
        lines.append(f"build_service_jobs_completed_total {state.jobs_completed}")
        lines.append("")

        lines.append("# HELP build_service_jobs_failed_total Total failed builds")
        lines.append("# TYPE build_service_jobs_failed_total counter")
        lines.append(f"build_service_jobs_failed_total {state.jobs_failed}")
        lines.append("")

        lines.append("# HELP build_service_uptime_seconds Worker uptime in seconds")
        lines.append("# TYPE build_service_uptime_seconds gauge")
        lines.append(f"build_service_uptime_seconds {state.uptime_seconds}")
        lines.append("")

        lines.append("# HELP build_service_busy Is the worker currently processing a build (0/1)")
        lines.append("# TYPE build_service_busy gauge")
        lines.append(f"build_service_busy {1 if state.is_busy else 0}")
        lines.append("")

    return Response(
        "\n".join(lines) + "\n",
        content_type="text/plain; version=0.0.4; charset=utf-8",
    )
