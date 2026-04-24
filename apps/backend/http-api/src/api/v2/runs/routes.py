"""Route registration for /v2/runs and /v2/manufacturing/sessions endpoints.

Keeps router.py clean by consolidating all run-related URL rules into a single
`register_run_routes()` call.
"""

from flask import Blueprint
from flask_socketio import SocketIO

# Run CRUD + listing
from .runs import (
    batch_runs_action,
    create_run,
    list_runs,
    get_run,
    cancel_run,
    rerun_run,
    list_targets,
    list_executions,
)

# Reporter callbacks
from .reporter import (
    init_socketio,
    report_preflight,
    report_start,
    report_test_list,
    report_target_start,
    report_execution_start,
    report_execution_result,
    report_step_start,
    report_step_result,
    report_target_result,
    report_finish,
    report_telemetry,
)

# Artifacts
from .artifacts import list_artifacts, download_artifact

# Logs
from .logs import (
    report_log_chunk,
    get_log_file,
    download_run,
    get_manifest,
)

# Telemetry
from .telemetry import get_telemetry_manifest, get_telemetry_channel

# Executions (dedicated module — adds list_execution_results)
from .executions import (
    list_executions as list_executions_dedicated,
    list_execution_results,
)

# Trigger
from .trigger import trigger_run

# Demo
from .demo import simulate_run

# Queue
from .queue import (
    batch_queue_action,
    list_queue,
    get_queue_entry,
    create_queue_entry,
    update_queue_entry,
    cancel_queue_entry,
    promote_queue_entry,
    demote_queue_entry,
    get_queue_stats,
    trigger_scheduler,
)

# Manual test run
from .manual import run_tests

# WebSocket handlers
from .ws import register_runs_ws_handlers

# Manufacturing sessions (TestRun-based)
from ..manufacturing.sessions import (
    list_manufacturing_fixtures,
    create_manufacturing_session,
    list_manufacturing_sessions,
    get_manufacturing_session,
    add_manufacturing_run,
    resolve_panel,
    redeploy_manufacturing_runner,
    end_manufacturing_session,
    archive_session,
    delete_session,
    batch_sessions_action,
    get_manufacturing_results,
    get_session_report,
    coreops_assign_device_id,
    coreops_upload_key,
    coreops_save_iccid,
    set_manufacturing_socketio as set_mfg_v2_socketio,
)
from ..manufacturing.runner import (
    runner_heartbeat,
    set_runner_socketio,
)


def register_run_routes(api: Blueprint, socketio: SocketIO):
    """Register all /v2/runs/* and /v2/manufacturing/sessions/* URL rules.

    Args:
        api: The v2 Blueprint to attach routes to.
        socketio: The Flask-SocketIO instance for real-time events.
    """

    # ── SocketIO initialization ──────────────────────────────────
    init_socketio(socketio)
    register_runs_ws_handlers(socketio)
    set_mfg_v2_socketio(socketio)
    set_runner_socketio(socketio)

    # ─────────────────────────────────────────────────────────────
    #  Run CRUD
    # ─────────────────────────────────────────────────────────────

    api.add_url_rule(
        "/runs",
        endpoint="create_run",
        view_func=create_run,
        methods=["POST"],
    )
    api.add_url_rule(
        "/runs",
        endpoint="list_runs",
        view_func=list_runs,
        methods=["GET"],
    )
    api.add_url_rule(
        "/runs/<run_id>",
        endpoint="get_run",
        view_func=get_run,
        methods=["GET"],
    )
    api.add_url_rule(
        "/runs/<run_id>/cancel",
        endpoint="cancel_run",
        view_func=cancel_run,
        methods=["POST"],
    )
    api.add_url_rule(
        "/runs/<run_id>/rerun",
        endpoint="rerun_run",
        view_func=rerun_run,
        methods=["POST"],
    )
    api.add_url_rule(
        "/runs/batch",
        endpoint="batch_runs",
        view_func=batch_runs_action,
        methods=["POST"],
    )
    api.add_url_rule(
        "/runs/<run_id>/trigger",
        endpoint="trigger_run",
        view_func=trigger_run,
        methods=["POST"],
    )
    api.add_url_rule(
        "/runs/<run_id>/targets",
        endpoint="list_run_targets",
        view_func=list_targets,
        methods=["GET"],
    )
    api.add_url_rule(
        "/runs/<run_id>/executions",
        endpoint="list_run_executions",
        view_func=list_executions,
        methods=["GET"],
    )
    api.add_url_rule(
        "/runs/<run_id>/executions/<execution_id>/results",
        endpoint="list_run_execution_results",
        view_func=list_execution_results,
        methods=["GET"],
    )

    # ─────────────────────────────────────────────────────────────
    #  Reporter callbacks (called by K8s Jobs via API key auth)
    # ─────────────────────────────────────────────────────────────

    api.add_url_rule(
        "/runs/<run_id>/report/preflight",
        endpoint="run_report_preflight",
        view_func=report_preflight,
        methods=["POST"],
    )
    api.add_url_rule(
        "/runs/<run_id>/report/start",
        endpoint="run_report_start",
        view_func=report_start,
        methods=["POST"],
    )
    api.add_url_rule(
        "/runs/<run_id>/report/test-list",
        endpoint="run_report_test_list",
        view_func=report_test_list,
        methods=["POST"],
    )
    api.add_url_rule(
        "/runs/<run_id>/report/target-start",
        endpoint="run_report_target_start",
        view_func=report_target_start,
        methods=["POST"],
    )
    api.add_url_rule(
        "/runs/<run_id>/report/execution-start",
        endpoint="run_report_execution_start",
        view_func=report_execution_start,
        methods=["POST"],
    )
    api.add_url_rule(
        "/runs/<run_id>/report/execution-result",
        endpoint="run_report_execution_result",
        view_func=report_execution_result,
        methods=["POST"],
    )
    api.add_url_rule(
        "/runs/<run_id>/report/step-start",
        endpoint="run_report_step_start",
        view_func=report_step_start,
        methods=["POST"],
    )
    api.add_url_rule(
        "/runs/<run_id>/report/step-result",
        endpoint="run_report_step_result",
        view_func=report_step_result,
        methods=["POST"],
    )
    api.add_url_rule(
        "/runs/<run_id>/report/target-result",
        endpoint="run_report_target_result",
        view_func=report_target_result,
        methods=["POST"],
    )
    api.add_url_rule(
        "/runs/<run_id>/report/finish",
        endpoint="run_report_finish",
        view_func=report_finish,
        methods=["POST"],
    )
    api.add_url_rule(
        "/runs/<run_id>/report/log-chunk",
        endpoint="run_report_log_chunk",
        view_func=report_log_chunk,
        methods=["POST"],
    )
    api.add_url_rule(
        "/runs/<run_id>/report/telemetry",
        endpoint="run_report_telemetry",
        view_func=report_telemetry,
        methods=["POST"],
    )

    # ─────────────────────────────────────────────────────────────
    #  Artifacts & logs
    # ─────────────────────────────────────────────────────────────

    api.add_url_rule(
        "/runs/<run_id>/artifacts",
        endpoint="list_run_artifacts",
        view_func=list_artifacts,
        methods=["GET"],
    )
    api.add_url_rule(
        "/runs/<run_id>/artifacts/<path:name>",
        endpoint="download_run_artifact",
        view_func=download_artifact,
        methods=["GET"],
    )
    api.add_url_rule(
        "/runs/<run_id>/logs/<path:file_path>",
        endpoint="get_run_log_file",
        view_func=get_log_file,
        methods=["GET"],
    )
    api.add_url_rule(
        "/runs/<run_id>/download",
        endpoint="download_run",
        view_func=download_run,
        methods=["GET"],
    )
    api.add_url_rule(
        "/runs/<run_id>/manifest",
        endpoint="get_run_manifest",
        view_func=get_manifest,
        methods=["GET"],
    )

    # ─────────────────────────────────────────────────────────────
    #  Telemetry (post-analysis)
    # ─────────────────────────────────────────────────────────────

    api.add_url_rule(
        "/runs/<run_id>/telemetry/manifest",
        endpoint="get_run_telemetry_manifest",
        view_func=get_telemetry_manifest,
        methods=["GET"],
    )
    api.add_url_rule(
        "/runs/<run_id>/telemetry/<channel>",
        endpoint="get_run_telemetry_channel",
        view_func=get_telemetry_channel,
        methods=["GET"],
    )

    # ─────────────────────────────────────────────────────────────
    #  Demo (simulate a run via WebSocket events)
    # ─────────────────────────────────────────────────────────────

    api.add_url_rule(
        "/runs/<run_id>/demo/simulate",
        endpoint="simulate_run",
        view_func=simulate_run,
        methods=["POST"],
    )

    # ─────────────────────────────────────────────────────────────
    #  Manual test run
    # ─────────────────────────────────────────────────────────────

    api.add_url_rule(
        "/runs/manual/run",
        endpoint="manual_test_run",
        view_func=run_tests,
        methods=["POST"],
    )

    # ─────────────────────────────────────────────────────────────
    #  Queue (validation queue entries)
    # ─────────────────────────────────────────────────────────────

    api.add_url_rule(
        "/runs/queue",
        endpoint="list_queue",
        view_func=list_queue,
        methods=["GET"],
    )
    api.add_url_rule(
        "/runs/queue",
        endpoint="create_queue_entry",
        view_func=create_queue_entry,
        methods=["POST"],
    )
    api.add_url_rule(
        "/runs/queue/stats",
        endpoint="get_queue_stats",
        view_func=get_queue_stats,
        methods=["GET"],
    )
    api.add_url_rule(
        "/runs/queue/<entry_id>",
        endpoint="get_queue_entry",
        view_func=get_queue_entry,
        methods=["GET"],
    )
    api.add_url_rule(
        "/runs/queue/<entry_id>",
        endpoint="update_queue_entry",
        view_func=update_queue_entry,
        methods=["PATCH"],
    )
    api.add_url_rule(
        "/runs/queue/<entry_id>/cancel",
        endpoint="cancel_queue_entry",
        view_func=cancel_queue_entry,
        methods=["POST"],
    )
    api.add_url_rule(
        "/runs/queue/<entry_id>/promote",
        endpoint="promote_queue_entry",
        view_func=promote_queue_entry,
        methods=["POST"],
    )
    api.add_url_rule(
        "/runs/queue/<entry_id>/demote",
        endpoint="demote_queue_entry",
        view_func=demote_queue_entry,
        methods=["POST"],
    )
    api.add_url_rule(
        "/runs/queue/schedule",
        endpoint="trigger_scheduler",
        view_func=trigger_scheduler,
        methods=["POST"],
    )
    api.add_url_rule(
        "/runs/queue/batch",
        endpoint="batch_queue",
        view_func=batch_queue_action,
        methods=["POST"],
    )

    # ─────────────────────────────────────────────────────────────
    #  Manufacturing fixtures + sessions (TestRun-based)
    # ─────────────────────────────────────────────────────────────

    api.add_url_rule(
        "/manufacturing/fixtures",
        endpoint="list_mfg_fixtures",
        view_func=list_manufacturing_fixtures,
        methods=["GET"],
    )
    api.add_url_rule(
        "/manufacturing/sessions",
        endpoint="create_mfg_session",
        view_func=create_manufacturing_session,
        methods=["POST"],
    )
    api.add_url_rule(
        "/manufacturing/sessions",
        endpoint="list_mfg_sessions",
        view_func=list_manufacturing_sessions,
        methods=["GET"],
    )
    api.add_url_rule(
        "/manufacturing/sessions/<session_id>",
        endpoint="get_mfg_session",
        view_func=get_manufacturing_session,
        methods=["GET"],
    )
    api.add_url_rule(
        "/manufacturing/sessions/<session_id>/runs",
        endpoint="add_mfg_run",
        view_func=add_manufacturing_run,
        methods=["POST"],
    )
    api.add_url_rule(
        "/manufacturing/sessions/<session_id>/resolve-panel",
        endpoint="resolve_mfg_panel",
        view_func=resolve_panel,
        methods=["POST"],
    )
    api.add_url_rule(
        "/manufacturing/sessions/<session_id>/redeploy-runner",
        endpoint="redeploy_mfg_runner",
        view_func=redeploy_manufacturing_runner,
        methods=["POST"],
    )
    api.add_url_rule(
        "/manufacturing/sessions/<session_id>/end",
        endpoint="end_mfg_session",
        view_func=end_manufacturing_session,
        methods=["POST"],
    )
    api.add_url_rule(
        "/manufacturing/sessions/<session_id>/archive",
        endpoint="archive_mfg_session",
        view_func=archive_session,
        methods=["POST"],
    )
    api.add_url_rule(
        "/manufacturing/sessions/<session_id>",
        endpoint="delete_mfg_session",
        view_func=delete_session,
        methods=["DELETE"],
    )
    api.add_url_rule(
        "/manufacturing/sessions/batch",
        endpoint="batch_mfg_sessions",
        view_func=batch_sessions_action,
        methods=["POST"],
    )
    api.add_url_rule(
        "/manufacturing/sessions/<session_id>/results",
        endpoint="get_mfg_results",
        view_func=get_manufacturing_results,
        methods=["GET"],
    )
    api.add_url_rule(
        "/manufacturing/sessions/<session_id>/report",
        endpoint="get_mfg_session_report",
        view_func=get_session_report,
        methods=["GET"],
    )
    api.add_url_rule(
        "/manufacturing/sessions/<session_id>/runner-heartbeat",
        endpoint="mfg_runner_heartbeat",
        view_func=runner_heartbeat,
        methods=["POST"],
    )

    # CoreOps proxy — manufacturing runners call these to personalize devices
    api.add_url_rule(
        "/manufacturing/coreops/devices/assign",
        endpoint="coreops_assign_device_id",
        view_func=coreops_assign_device_id,
        methods=["POST"],
    )
    api.add_url_rule(
        "/manufacturing/coreops/devices/keys",
        endpoint="coreops_upload_key",
        view_func=coreops_upload_key,
        methods=["POST"],
    )
    api.add_url_rule(
        "/manufacturing/coreops/devices/iccids",
        endpoint="coreops_save_iccid",
        view_func=coreops_save_iccid,
        methods=["POST"],
    )
