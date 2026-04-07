import logging
import re

from corekinect.utils import Logger
from flask import Blueprint, Flask
from flask_socketio import SocketIO

# Auth handlers
from .auth.api_keys import create_api_key, delete_api_key, list_api_keys
from .auth.dev_login import dev_login, dev_users
from .auth.login import login
from .auth.me import me
from .auth.permission_sets import (
    create_permission_set,
    delete_permission_set,
    list_permission_sets,
    update_permission_set,
)
from .auth.permissions_list import list_permissions
from .auth.users import (
    users_create,
    users_delete,
    users_get_product_access,
    users_list,
    users_set_product_access,
    users_set_role,
    users_update,
)

# Health
from .system.healthcheck import healthcheck

# Products handlers (was catalog/)
from .products.board_discovery import (
    check_repo,
    discover_board_detail,
    discover_boards,
    list_board_branches,
    list_repo_branches,
)
from .products.products import (
    create_product,
    delete_product,
    get_product,
    get_product_by_slug,
    list_products,
    update_product,
    sync_product_revisions,
)
from .products.boards import (
    create_board,
    delete_board,
    get_board,
    list_boards,
    update_board,
)
from .products.board_revisions import (
    get_board_revision,
    create_board_revision,
    create_target,
    delete_board_revision,
    delete_modem_firmware,
    delete_target,
    download_modem_firmware,
    update_board_revision,
    update_target,
    upload_modem_firmware,
)
from .products.firmware_builds import (
    list_firmware_sets,
    get_firmware_set,
    create_firmware_set,
    update_firmware_set,
    delete_firmware_set,
    upload_firmware_build,
    download_firmware_build,
)
from .products.test_packages import (
    upload_test_package,
    list_test_packages,
    get_latest_test_package,
    download_test_package,
)

# System handlers
from .system.info import get_system_info
from .system.history import get_history_entry, list_history
from .system.logs import register_log_handlers
from .system.exec import register_exec_handlers
from .system.observability_ws import register_observability_handlers, register_icle_handlers
from .system.retention import cleanup_validation_runs, get_validation_storage_usage
from .system.secrets import list_secrets as list_platform_secrets, create_secret as create_platform_secret, update_secret as update_platform_secret, delete_secret as delete_platform_secret
from .system.poller_state import list_poller_state, upsert_poller_state, delete_poller_state

# Kubernetes handlers (was system/ cluster endpoints)
from .kubernetes.cluster import get_cluster, get_namespaces
from .kubernetes.nodes import list_nodes as list_system_nodes, get_node as get_system_node
from .kubernetes.events import get_events
from .kubernetes.pods import list_pods, get_pod, get_pod_logs, delete_pod
from .kubernetes.deployments import (
    list_deployments as list_system_deployments,
    get_deployment as get_system_deployment,
    scale_deployment,
    restart_deployment as restart_system_deployment,
)
from .kubernetes.services_api import list_services, get_service
from .kubernetes.jobs import list_jobs, get_job, delete_job
from .kubernetes.config import list_configmaps, get_configmap, list_secrets, get_secret
from .kubernetes.resources import get_resource_yaml, apply_resource_yaml, delete_resource
from .kubernetes.rbac import list_roles, list_cluster_roles, list_role_bindings, list_cluster_role_bindings, list_service_accounts

# Session handlers (was validation/runs/)
from .sessions.validation_ws import register_validation_ws_handlers
from .sessions.runs import (
    create_run,
    list_runs,
    get_run,
    get_run_job,
    cancel_run,
    rerun_session,
)
from .sessions.executions import (
    list_executions,
    list_execution_results,
)
from .sessions.artifacts import (
    list_artifacts as list_run_artifacts,
    download_artifact as download_run_artifact,
)
from .sessions.reporter import (
    report_start,
    report_test_list,
    report_test_start,
    report_test_result,
    report_finish,
    report_telemetry,
    report_step_start,
    report_step_result,
)
from .sessions.trigger import trigger_run
from .sessions.demo import simulate_run
from .sessions.reporter import set_validation_socketio
from .sessions.logs import (
    report_log_chunk,
    get_log_file,
    download_run,
    get_manifest,
)
from .sessions.telemetry_api import (
    get_telemetry_manifest,
    get_telemetry_channel,
)
from .sessions.manual import run_tests
from .sessions.queue import (
    list_queue,
    get_queue_entry,
    create_queue_entry,
    update_queue_entry,
    cancel_queue_entry,
    promote_queue_entry,
    get_queue_stats,
    trigger_scheduler,
)

# ICLE device handlers
from .icle.heartbeat import heartbeat as icle_heartbeat, set_socketio as set_icle_socketio
from .icle.devices import (
    list_devices as list_icle_devices,
    get_device as get_icle_device,
    update_device as update_icle_device,
    delete_device as delete_icle_device,
)
from .icle.commands import acknowledge_command as ack_icle_command
from .icle.config import push_config as push_icle_config
from .icle.ota import trigger_ota as trigger_icle_ota
from .icle.logs import list_device_logs as list_icle_logs, upload_device_log as upload_icle_log

# Node management handlers (MTIBs)
from .nodes.nodes import (
    list_nodes as list_managed_nodes,
    create_node,
    sync_nodes_from_k8s,
    get_node as get_managed_node,
    update_node,
    delete_node,
    check_node_health,
    register_node,
)

# Fixture management handlers
from .fixtures.fixtures import (
    dashboard_overview,
    list_fixtures,
    create_fixture as create_managed_fixture,
    get_fixture,
    update_fixture,
    delete_fixture,
    create_slot,
    update_slot,
    delete_slot,
    assign_slot_node,
    deploy_fixture,
    undeploy_fixture,
    get_fixture_deploy_status,
)

# Fixture — Benches (merged from validation/benches/)
from .fixtures.benches import (
    list_benches,
    get_bench,
    create_bench,
    update_bench,
    delete_bench,
    lock_bench,
    unlock_bench,
    discover_mtibs,
    get_bench_profile,
)

# Fixture — Designs (merged from validation/designs/)
from .fixtures.designs import (
    list_designs,
    get_design,
    create_design,
    update_design,
    delete_design,
    get_design_profile,
)

# MTIB observability handlers (gRPC proxy for power/GPIO/UART snapshots)
from .system.mtib_observability import (
    get_fleet_observability,
    get_node_observability,
    get_node_power,
    get_node_gpio,
    get_node_uart,
    get_node_system,
)

# Docs
from .docs import openapi_spec, swagger_ui

# Builds handlers (was ci/)
from .builds.webhook import webhook_bitbucket, trigger_build_run, receive_repo_event, set_ci_socketio, list_ci_repos
from .builds.builds import (
    list_builds as list_ci_builds,
    get_build as get_ci_build,
    list_build_artifacts as list_ci_build_artifacts,
    download_build_artifacts as download_ci_build_artifacts,
    download_single_artifact as download_ci_single_artifact,
    get_build_log as get_ci_build_log,
    stream_build_log as stream_ci_build_log,
    report_build_progress as report_ci_build_progress,
    create_build as create_ci_build,
    update_build as update_ci_build,
    upload_build_artifact as upload_ci_build_artifact,
    reset_build as reset_ci_build,
)
from .builds.build_runs import (
    list_build_runs as list_ci_build_runs,
    get_build_run as get_ci_build_run,
    create_build_run as create_ci_build_run,
    cancel_build_run as cancel_ci_build_run,
    retrigger_build_run as retrigger_ci_build_run,
    download_build_run_artifacts as download_ci_build_run_artifacts,
    validate_build_run as validate_ci_build_run,
    validate_build_run_artifacts_endpoint as validate_ci_build_run_artifacts,
    list_build_run_sessions as list_ci_build_run_sessions,
)
from .builds.scripts import (
    list_build_scripts,
    get_build_script,
)
from .builds.overlays import (
    get_overlays,
    list_overlays,
)

# Stage config handlers (product validation stages)
from .builds.stage_config import (
    list_stage_configs,
    get_stage_config,
    create_stage_config,
    update_stage_config,
    delete_stage_config,
    initialize_stages,
    get_stage_build_matrix,
    update_stage_build_matrix,
    reset_stage_build_matrix,
)

# Asset set handlers (unified firmware asset containers)
from .assets.asset_sets import (
    list_asset_sets,
    create_asset_set,
    create_external_asset_set,
    get_asset_set,
    complete_asset_set,
    delete_asset_set,
)
from .assets.assets import upload_asset

# PR pipeline + summary endpoints
from .builds.pr_builds import list_pr_pipelines, get_build_summary

# Build recipes (product build scripts stored in MinIO)
from .builds.recipes import (
    get_recipe, update_recipe, validate_recipe,
    list_recipe_versions, get_recipe_version, get_recipe_version_by_id,
    save_recipe_version,
    publish_recipe, diff_recipe_versions, test_recipe_build,
    get_stage_defs,
    list_recipe_templates, get_recipe_template,
)

# Run manifest (execution graph for validation pipeline stages)
from .builds.manifest import get_run_manifest


# -------------------------------------------------
#                                        Log Filter
# -------------------------------------------------
class LogFilter(logging.Filter):
    """
    This filter omits the logs for frequently accessed routes such as healthcheck and deployment routes,
    as well as logs generated by accepted connections.
    """

    def __init__(self):
        super().__init__()
        # Compile regular expressions only once for efficiency
        self.healthcheck_pattern = re.compile(r"GET /v2/healthcheck HTTP")
        self.accepted_pattern = re.compile(r"\(.*\) accepted \(.*\)")

    def filter(self, record):
        """Return False for healthcheck and connection-accepted log messages."""
        # Convert the log record's message to string if it isn't already
        log_message = str(record.msg)
        # Check if the log record matches any of the specified patterns
        if self.healthcheck_pattern.search(log_message) or self.accepted_pattern.search(log_message):
            return False  # Do not log if the message matches any of the patterns
        return True  # Log other messages


# -------------------------------------------------
#                                     V2 API Routes
# -------------------------------------------------
v2 = Blueprint("v2", __name__, url_prefix="/v2")


def register_v2_routes(logger: Logger, server: Flask, socketio: SocketIO):
    """Register all v2 API routes, WebSocket handlers, and log filters."""
    # Add a log filter to avoid spamming the logs with commonly hit routes
    logger.add_filter(LogFilter())

    # Auth (login + me only — stays under /auth)
    v2.add_url_rule("/auth/login",           view_func=login,          methods=["POST"])
    v2.add_url_rule("/auth/me",              view_func=me,             methods=["GET"])

    # Dev-only auth (no-password login, only works when AUTH_ENABLED=false)
    v2.add_url_rule("/auth/dev-users",       view_func=dev_users,      methods=["GET"])
    v2.add_url_rule("/auth/dev-login",       view_func=dev_login,      methods=["POST"])

    # Users (was /auth/users)
    v2.add_url_rule("/users",           view_func=users_list,     methods=["GET"])
    v2.add_url_rule("/users",           view_func=users_create,   methods=["POST"])
    v2.add_url_rule("/users/<user_id>", view_func=users_update,   methods=["PUT"])
    v2.add_url_rule("/users/<user_id>", view_func=users_delete,   methods=["DELETE"])
    v2.add_url_rule("/users/<user_id>/role",           view_func=users_set_role,            methods=["PUT"])
    v2.add_url_rule("/users/<user_id>/product-access", view_func=users_get_product_access, methods=["GET"])
    v2.add_url_rule("/users/<user_id>/product-access", view_func=users_set_product_access, methods=["PUT"])

    # Permissions (was /auth/permission-sets + /auth/permissions)
    v2.add_url_rule("/permissions",          view_func=list_permission_sets,   methods=["GET"])
    v2.add_url_rule("/permissions",          view_func=create_permission_set,  methods=["POST"])
    v2.add_url_rule("/permissions/<set_id>", view_func=update_permission_set,  methods=["PUT"])
    v2.add_url_rule("/permissions/<set_id>", view_func=delete_permission_set,  methods=["DELETE"])
    v2.add_url_rule("/permissions/available", view_func=list_permissions,      methods=["GET"])

    # API Keys (was /auth/api-keys)
    v2.add_url_rule("/api-keys",          view_func=list_api_keys,   methods=["GET"])
    v2.add_url_rule("/api-keys",          view_func=create_api_key,  methods=["POST"])
    v2.add_url_rule("/api-keys/<key_id>", view_func=delete_api_key,  methods=["DELETE"])

    # Products - Board Discovery (ck_boards)
    v2.add_url_rule("/products/boards/branches",                                                  endpoint="list_board_branches",    view_func=list_board_branches,    methods=["GET"])
    v2.add_url_rule("/products/boards/discover",                                                  endpoint="discover_boards",        view_func=discover_boards,        methods=["GET"])
    v2.add_url_rule("/products/boards/discover/<board_name>",                                     endpoint="discover_board_detail",  view_func=discover_board_detail,  methods=["GET"])
    v2.add_url_rule("/products/repos/check",                                                      endpoint="check_repo",             view_func=check_repo,             methods=["GET"])
    v2.add_url_rule("/products/repos/branches",                                                  endpoint="list_repo_branches",     view_func=list_repo_branches,     methods=["GET"])

    # Products
    v2.add_url_rule("/products",                                                                   view_func=list_products,          methods=["GET"])
    v2.add_url_rule("/products",                                                                   view_func=create_product,         methods=["POST"])
    v2.add_url_rule("/products/by-slug/<slug>",                                                    view_func=get_product_by_slug,    methods=["GET"])
    v2.add_url_rule("/products/<product_id>",                                                      view_func=get_product,            methods=["GET"])
    v2.add_url_rule("/products/<product_id>",                                                      view_func=update_product,         methods=["PUT"])
    v2.add_url_rule("/products/<product_id>",                                                      view_func=delete_product,         methods=["DELETE"])
    v2.add_url_rule("/products/<product_id>/sync-revisions",                                       view_func=sync_product_revisions, methods=["POST"])

    # Products - Boards
    v2.add_url_rule("/products/<product_id>/boards",                                               view_func=list_boards,            methods=["GET"])
    v2.add_url_rule("/products/<product_id>/boards",                                               view_func=create_board,           methods=["POST"])
    v2.add_url_rule("/products/<product_id>/boards/<board_id>",                                    view_func=get_board,              methods=["GET"])
    v2.add_url_rule("/products/<product_id>/boards/<board_id>",                                    view_func=update_board,           methods=["PUT"])
    v2.add_url_rule("/products/<product_id>/boards/<board_id>",                                    view_func=delete_board,           methods=["DELETE"])

    # Products - Board Revisions
    v2.add_url_rule("/products/<product_id>/boards/<board_id>/revisions",                          view_func=create_board_revision,  methods=["POST"])
    v2.add_url_rule("/products/<product_id>/boards/<board_id>/revisions/<revision_id>",            view_func=get_board_revision,     methods=["GET"])
    v2.add_url_rule("/products/<product_id>/boards/<board_id>/revisions/<revision_id>",            view_func=update_board_revision,  methods=["PUT"])
    v2.add_url_rule("/products/<product_id>/boards/<board_id>/revisions/<revision_id>",            view_func=delete_board_revision,  methods=["DELETE"])

    # Products - Revision Modem Firmware
    v2.add_url_rule("/products/<product_id>/boards/<board_id>/revisions/<revision_id>/modem-firmware",  view_func=upload_modem_firmware,    methods=["POST"])
    v2.add_url_rule("/products/<product_id>/boards/<board_id>/revisions/<revision_id>/modem-firmware",  view_func=download_modem_firmware,  methods=["GET"])
    v2.add_url_rule("/products/<product_id>/boards/<board_id>/revisions/<revision_id>/modem-firmware",  view_func=delete_modem_firmware,    methods=["DELETE"])

    # Products - Revision Targets
    v2.add_url_rule("/products/<product_id>/boards/<board_id>/revisions/<revision_id>/targets",              view_func=create_target,  methods=["POST"])
    v2.add_url_rule("/products/<product_id>/boards/<board_id>/revisions/<revision_id>/targets/<target_id>",  view_func=update_target,  methods=["PUT"])
    v2.add_url_rule("/products/<product_id>/boards/<board_id>/revisions/<revision_id>/targets/<target_id>",  view_func=delete_target,  methods=["DELETE"])

    # Products - Firmware Sets + Builds
    v2.add_url_rule("/products/<product_id>/firmware",                                             view_func=list_firmware_sets,      methods=["GET"])
    v2.add_url_rule("/products/<product_id>/firmware",                                             view_func=create_firmware_set,     methods=["POST"])
    v2.add_url_rule("/products/<product_id>/firmware/<set_id>",                                    view_func=get_firmware_set,        methods=["GET"])
    v2.add_url_rule("/products/<product_id>/firmware/<set_id>",                                    view_func=update_firmware_set,     methods=["PUT"])
    v2.add_url_rule("/products/<product_id>/firmware/<set_id>",                                    view_func=delete_firmware_set,     methods=["DELETE"])
    v2.add_url_rule("/products/<product_id>/firmware/<set_id>/builds",                             view_func=upload_firmware_build,   methods=["POST"])
    v2.add_url_rule("/firmware/builds/<build_id>/download",                                        view_func=download_firmware_build, methods=["GET"])

    # Products - Test Packages
    v2.add_url_rule("/products/<product_id>/test-packages",                                        endpoint="upload_test_package",      view_func=upload_test_package,       methods=["POST"])
    v2.add_url_rule("/products/<product_id>/test-packages",                                        endpoint="list_test_packages",       view_func=list_test_packages,        methods=["GET"])
    v2.add_url_rule("/products/<product_id>/test-packages/latest",                                 endpoint="get_latest_test_package",  view_func=get_latest_test_package,   methods=["GET"])
    v2.add_url_rule("/products/<product_id>/test-packages/<version>/download",                     endpoint="download_test_package",    view_func=download_test_package,     methods=["GET"])

    # Products - Stage Configs (validation stage configuration per product)
    v2.add_url_rule("/products/<product_id>/stages",                                            endpoint="list_stage_configs",       view_func=list_stage_configs,    methods=["GET"])
    v2.add_url_rule("/products/<product_id>/stages",                                            endpoint="create_stage_config",      view_func=create_stage_config,   methods=["POST"])
    v2.add_url_rule("/products/<product_id>/stages/initialize",                                 endpoint="initialize_stages",        view_func=initialize_stages,     methods=["POST"])
    v2.add_url_rule("/products/<product_id>/stages/<stage>",                                    endpoint="get_stage_config",         view_func=get_stage_config,      methods=["GET"])
    v2.add_url_rule("/products/<product_id>/stages/<stage>",                                    endpoint="update_stage_config",      view_func=update_stage_config,   methods=["PUT"])
    v2.add_url_rule("/products/<product_id>/stages/<stage>",                                    endpoint="delete_stage_config",      view_func=delete_stage_config,   methods=["DELETE"])

    # Products - Stage Build Matrix (per-stage build definitions)
    v2.add_url_rule("/products/<product_id>/stages/<stage>/build-matrix",                       endpoint="get_stage_build_matrix",   view_func=get_stage_build_matrix,    methods=["GET"])
    v2.add_url_rule("/products/<product_id>/stages/<stage>/build-matrix",                       endpoint="update_stage_build_matrix", view_func=update_stage_build_matrix, methods=["PUT"])
    v2.add_url_rule("/products/<product_id>/stages/<stage>/build-matrix/reset",                 endpoint="reset_stage_build_matrix", view_func=reset_stage_build_matrix,  methods=["POST"])

    # Products - Asset Sets (unified firmware asset containers)
    v2.add_url_rule("/products/<product_id>/asset-sets",                                        endpoint="list_asset_sets",          view_func=list_asset_sets,           methods=["GET"])
    v2.add_url_rule("/products/<product_id>/asset-sets",                                        endpoint="create_asset_set",         view_func=create_asset_set,          methods=["POST"])
    v2.add_url_rule("/products/<product_id>/asset-sets/external",                               endpoint="create_external_asset_set", view_func=create_external_asset_set, methods=["POST"])

    # Asset Sets (top-level — not nested under product)
    v2.add_url_rule("/asset-sets/<asset_set_id>",                                               endpoint="get_asset_set",            view_func=get_asset_set,             methods=["GET"])
    v2.add_url_rule("/asset-sets/<asset_set_id>",                                               endpoint="delete_asset_set",         view_func=delete_asset_set,          methods=["DELETE"])
    v2.add_url_rule("/asset-sets/<asset_set_id>/assets",                                        endpoint="upload_asset",             view_func=upload_asset,              methods=["POST"])
    v2.add_url_rule("/asset-sets/<asset_set_id>/complete",                                      endpoint="complete_asset_set",       view_func=complete_asset_set,        methods=["POST"])

    # Products - Build Recipe (product build script stored in MinIO)
    v2.add_url_rule("/products/<product_id>/recipe",                                             endpoint="get_recipe",               view_func=get_recipe,            methods=["GET"])
    v2.add_url_rule("/products/<product_id>/recipe",                                             endpoint="update_recipe",            view_func=update_recipe,         methods=["PUT"])
    v2.add_url_rule("/products/<product_id>/recipe/validate",                                    endpoint="validate_recipe",          view_func=validate_recipe,       methods=["POST"])
    v2.add_url_rule("/products/<product_id>/recipe/test-build",                                  endpoint="test_recipe_build",        view_func=test_recipe_build,     methods=["POST"])
    v2.add_url_rule("/products/<product_id>/recipe/versions",                                    endpoint="list_recipe_versions",     view_func=list_recipe_versions,  methods=["GET"])
    v2.add_url_rule("/products/<product_id>/recipe/versions/<int:version_num>",                   endpoint="get_recipe_version",       view_func=get_recipe_version,    methods=["GET"])
    v2.add_url_rule("/products/<product_id>/recipe/versions/by-id/<version_id>",                 endpoint="get_recipe_version_by_id", view_func=get_recipe_version_by_id, methods=["GET"])
    v2.add_url_rule("/products/<product_id>/recipe/save",                                        endpoint="save_recipe_version",      view_func=save_recipe_version,   methods=["POST"])
    v2.add_url_rule("/products/<product_id>/recipe/publish",                                     endpoint="publish_recipe",           view_func=publish_recipe,        methods=["POST"])
    v2.add_url_rule("/products/<product_id>/recipe/diff",                                        endpoint="diff_recipe_versions",     view_func=diff_recipe_versions,  methods=["GET"])

    # Products - Run Manifest (execution graph for validation pipeline)
    v2.add_url_rule("/products/<product_id>/manifest",                                           endpoint="get_product_manifest",     view_func=get_run_manifest,      methods=["GET"])

    # System - History
    v2.add_url_rule("/system/history",              view_func=list_history,      methods=["GET"])
    v2.add_url_rule("/system/history/<entry_id>",   view_func=get_history_entry, methods=["GET"])

    # System: Build info (no auth required)
    v2.add_url_rule("/system/info",                 view_func=get_system_info, methods=["GET"])

    # System: Retention management
    v2.add_url_rule("/system/retention/validation/cleanup",   endpoint="cleanup_validation_runs",     view_func=cleanup_validation_runs,      methods=["POST"])
    v2.add_url_rule("/system/retention/validation/usage",     endpoint="get_validation_storage_usage", view_func=get_validation_storage_usage, methods=["GET"])

    # Secrets
    v2.add_url_rule("/system/secrets",              endpoint="list_platform_secrets",   view_func=list_platform_secrets,   methods=["GET"])
    v2.add_url_rule("/system/secrets",              endpoint="create_platform_secret",  view_func=create_platform_secret,  methods=["POST"])
    v2.add_url_rule("/system/secrets/<secret_id>",  endpoint="update_platform_secret",  view_func=update_platform_secret,  methods=["PUT"])
    v2.add_url_rule("/system/secrets/<secret_id>",  endpoint="delete_platform_secret",  view_func=delete_platform_secret,  methods=["DELETE"])

    # Poller state (git-poller branch/PR SHA cache)
    v2.add_url_rule("/system/poller-state",  endpoint="list_poller_state",    view_func=list_poller_state,    methods=["GET"])
    v2.add_url_rule("/system/poller-state",  endpoint="upsert_poller_state",  view_func=upsert_poller_state,  methods=["PUT"])
    v2.add_url_rule("/system/poller-state",  endpoint="delete_poller_state",  view_func=delete_poller_state,  methods=["DELETE"])

    # Storage download
    from .assets.storage_download import download_storage_file
    v2.add_url_rule("/storage/download",                                                               endpoint="download_storage_file",        view_func=download_storage_file,    methods=["GET"])

    # Sessions (was /validation/runs)
    v2.add_url_rule("/sessions",                                                                    endpoint="list_sessions",                view_func=list_runs,                methods=["GET"])
    v2.add_url_rule("/sessions",                                                                    endpoint="create_session",               view_func=create_run,               methods=["POST"])
    v2.add_url_rule("/sessions/<run_id>",                                                           endpoint="get_session",                  view_func=get_run,                  methods=["GET"])
    v2.add_url_rule("/sessions/<run_id>/cancel",                                                    endpoint="cancel_session",               view_func=cancel_run,               methods=["POST"])
    v2.add_url_rule("/sessions/<run_id>/job",                                                       endpoint="get_session_job",              view_func=get_run_job,              methods=["GET"])
    v2.add_url_rule("/sessions/<run_id>/executions",                                                endpoint="list_session_executions",      view_func=list_executions,          methods=["GET"])
    v2.add_url_rule("/sessions/<run_id>/executions/<execution_id>/results",                         endpoint="list_execution_results",       view_func=list_execution_results,   methods=["GET"])
    v2.add_url_rule("/sessions/<run_id>/artifacts",                                                 endpoint="list_run_artifacts",           view_func=list_run_artifacts,       methods=["GET"])
    v2.add_url_rule("/sessions/<run_id>/artifacts/<path:name>",                                     endpoint="download_run_artifact",        view_func=download_run_artifact,    methods=["GET"])

    # Sessions - Trigger & Rerun
    v2.add_url_rule("/sessions/<run_id>/trigger",                                                    endpoint="trigger_session",              view_func=trigger_run,              methods=["POST"])
    v2.add_url_rule("/sessions/<session_id>/rerun",                                                  endpoint="rerun_session",                view_func=rerun_session,            methods=["POST"])

    # Sessions - Reporter callbacks (called by pytest plugin in K8s Jobs)
    v2.add_url_rule("/sessions/<run_id>/report/start",                                              endpoint="report_run_start",             view_func=report_start,             methods=["POST"])
    v2.add_url_rule("/sessions/<run_id>/report/test-start",                                         endpoint="report_test_start",            view_func=report_test_start,        methods=["POST"])
    v2.add_url_rule("/sessions/<run_id>/report/test-result",                                        endpoint="report_test_result",           view_func=report_test_result,       methods=["POST"])
    v2.add_url_rule("/sessions/<run_id>/report/finish",                                             endpoint="report_run_finish",            view_func=report_finish,            methods=["POST"])
    v2.add_url_rule("/sessions/<run_id>/report/test-list",                                          endpoint="report_test_list",             view_func=report_test_list,         methods=["POST"])
    v2.add_url_rule("/sessions/<run_id>/report/log-chunk",                                          endpoint="report_log_chunk",             view_func=report_log_chunk,         methods=["POST"])
    v2.add_url_rule("/sessions/<run_id>/report/telemetry",                                         endpoint="report_telemetry",             view_func=report_telemetry,         methods=["POST"])
    v2.add_url_rule("/sessions/<run_id>/report/step-start",                                        endpoint="report_step_start",            view_func=report_step_start,        methods=["POST"])
    v2.add_url_rule("/sessions/<run_id>/report/step-result",                                       endpoint="report_step_result",           view_func=report_step_result,       methods=["POST"])

    # Sessions - Log & artifact retrieval
    v2.add_url_rule("/sessions/<run_id>/logs/<path:file_path>",                                     endpoint="get_run_log_file",             view_func=get_log_file,             methods=["GET"])
    v2.add_url_rule("/sessions/<run_id>/download",                                                  endpoint="download_session",             view_func=download_run,             methods=["GET"])
    v2.add_url_rule("/sessions/<run_id>/manifest",                                                  endpoint="get_run_manifest",             view_func=get_manifest,             methods=["GET"])

    # Sessions - Telemetry (post-analysis)
    v2.add_url_rule("/sessions/<run_id>/telemetry/manifest",                                       endpoint="get_telemetry_manifest",       view_func=get_telemetry_manifest,   methods=["GET"])
    v2.add_url_rule("/sessions/<run_id>/telemetry/<channel>",                                      endpoint="get_telemetry_channel",        view_func=get_telemetry_channel,    methods=["GET"])

    # Sessions - Demo (simulate a run via WebSocket events)
    v2.add_url_rule("/sessions/<run_id>/demo/simulate",                                            endpoint="simulate_session",             view_func=simulate_run,             methods=["POST"])

    # Sessions - Legacy manufacturing test run
    v2.add_url_rule("/sessions/manual/run",                                                         endpoint="manual_test_run",              view_func=run_tests,                methods=["POST"])

    # Sessions - Queue (was /validation/queue)
    v2.add_url_rule("/sessions/queue",                                                        endpoint="list_queue",               view_func=list_queue,            methods=["GET"])
    v2.add_url_rule("/sessions/queue",                                                        endpoint="create_queue_entry",       view_func=create_queue_entry,    methods=["POST"])
    v2.add_url_rule("/sessions/queue/stats",                                                  endpoint="get_queue_stats",          view_func=get_queue_stats,       methods=["GET"])
    v2.add_url_rule("/sessions/queue/<entry_id>",                                             endpoint="get_queue_entry",          view_func=get_queue_entry,       methods=["GET"])
    v2.add_url_rule("/sessions/queue/<entry_id>",                                             endpoint="update_queue_entry",       view_func=update_queue_entry,    methods=["PATCH"])
    v2.add_url_rule("/sessions/queue/<entry_id>/cancel",                                      endpoint="cancel_queue_entry",       view_func=cancel_queue_entry,    methods=["POST"])
    v2.add_url_rule("/sessions/queue/<entry_id>/promote",                                     endpoint="promote_queue_entry",      view_func=promote_queue_entry,   methods=["POST"])
    v2.add_url_rule("/sessions/queue/schedule",                                               endpoint="trigger_scheduler",        view_func=trigger_scheduler,     methods=["POST"])

    # Fixtures
    v2.add_url_rule("/fixtures",                                         endpoint="list_fixtures",           view_func=list_fixtures,            methods=["GET"])
    v2.add_url_rule("/fixtures",                                         endpoint="create_fixture",          view_func=create_managed_fixture,   methods=["POST"])
    v2.add_url_rule("/fixtures/<fixture_id>",                            endpoint="get_fixture",             view_func=get_fixture,              methods=["GET"])
    v2.add_url_rule("/fixtures/<fixture_id>",                            endpoint="update_fixture",          view_func=update_fixture,           methods=["PUT"])
    v2.add_url_rule("/fixtures/<fixture_id>",                            endpoint="delete_fixture",          view_func=delete_fixture,           methods=["DELETE"])
    v2.add_url_rule("/fixtures/<fixture_id>/slots",                      endpoint="create_slot",             view_func=create_slot,              methods=["POST"])
    v2.add_url_rule("/fixtures/<fixture_id>/slots/<slot_id>",            endpoint="update_slot",             view_func=update_slot,              methods=["PUT"])
    v2.add_url_rule("/fixtures/<fixture_id>/slots/<slot_id>",            endpoint="delete_slot",             view_func=delete_slot,              methods=["DELETE"])
    v2.add_url_rule("/fixtures/<fixture_id>/slots/<slot_id>/assign",     endpoint="assign_slot_node",        view_func=assign_slot_node,         methods=["POST"])
    v2.add_url_rule("/fixtures/<fixture_id>/deploy",                    endpoint="deploy_fixture",          view_func=deploy_fixture,           methods=["POST"])
    v2.add_url_rule("/fixtures/<fixture_id>/undeploy",                  endpoint="undeploy_fixture",        view_func=undeploy_fixture,         methods=["POST"])
    v2.add_url_rule("/fixtures/<fixture_id>/deploy-status",            endpoint="fixture_deploy_status",   view_func=get_fixture_deploy_status, methods=["GET"])

    # Fixtures - Benches (legacy compat, backed by Fixture model)
    v2.add_url_rule("/fixtures/benches",                                                                endpoint="list_benches",                 view_func=list_benches,             methods=["GET"])
    v2.add_url_rule("/fixtures/benches",                                                                endpoint="create_bench",                 view_func=create_bench,             methods=["POST"])
    v2.add_url_rule("/fixtures/benches/discover",                                                       endpoint="discover_mtibs",               view_func=discover_mtibs,           methods=["GET"])
    v2.add_url_rule("/fixtures/benches/<bench_id>",                                                     endpoint="get_bench",                    view_func=get_bench,                methods=["GET"])
    v2.add_url_rule("/fixtures/benches/<bench_id>",                                                     endpoint="update_bench",                 view_func=update_bench,             methods=["PATCH"])
    v2.add_url_rule("/fixtures/benches/<bench_id>",                                                     endpoint="delete_bench",                 view_func=delete_bench,             methods=["DELETE"])
    v2.add_url_rule("/fixtures/benches/<bench_id>/lock",                                                endpoint="lock_bench",                   view_func=lock_bench,               methods=["POST"])
    v2.add_url_rule("/fixtures/benches/<bench_id>/unlock",                                              endpoint="unlock_bench",                 view_func=unlock_bench,             methods=["POST"])
    v2.add_url_rule("/fixtures/benches/<bench_id>/profile",                                             endpoint="get_bench_profile",            view_func=get_bench_profile,        methods=["GET"])

    # Fixtures - Designs
    v2.add_url_rule("/fixtures/designs",                                                                endpoint="list_designs",                 view_func=list_designs,             methods=["GET"])
    v2.add_url_rule("/fixtures/designs",                                                                endpoint="create_design",                view_func=create_design,            methods=["POST"])
    v2.add_url_rule("/fixtures/designs/<design_id>",                                                    endpoint="get_design",                   view_func=get_design,               methods=["GET"])
    v2.add_url_rule("/fixtures/designs/<design_id>",                                                    endpoint="update_design",                view_func=update_design,            methods=["PATCH"])
    v2.add_url_rule("/fixtures/designs/<design_id>",                                                    endpoint="delete_design",                view_func=delete_design,            methods=["DELETE"])
    v2.add_url_rule("/fixtures/designs/<design_id>/profile",                                            endpoint="get_design_profile",           view_func=get_design_profile,       methods=["GET"])

    # Dashboard
    v2.add_url_rule("/dashboard/overview",                           endpoint="dashboard_overview",          view_func=dashboard_overview,         methods=["GET"])

    # Devices - MTIBs (was /mtibs)
    v2.add_url_rule("/devices/mtibs",                                            endpoint="list_managed_mtibs",      view_func=list_managed_nodes,   methods=["GET"])
    v2.add_url_rule("/devices/mtibs",                                            endpoint="create_managed_mtib",     view_func=create_node,          methods=["POST"])
    v2.add_url_rule("/devices/mtibs/discover",                                   endpoint="discover_managed_mtibs",  view_func=sync_nodes_from_k8s,  methods=["POST"])
    v2.add_url_rule("/devices/mtibs/<node_id>",                                  endpoint="get_managed_mtib",        view_func=get_managed_node,     methods=["GET"])
    v2.add_url_rule("/devices/mtibs/<node_id>",                                  endpoint="update_managed_mtib",     view_func=update_node,          methods=["PUT"])
    v2.add_url_rule("/devices/mtibs/<node_id>",                                  endpoint="delete_managed_mtib",     view_func=delete_node,          methods=["DELETE"])
    v2.add_url_rule("/devices/mtibs/<node_id>/health",                           endpoint="check_managed_mtib_health", view_func=check_node_health,  methods=["POST"])
    v2.add_url_rule("/devices/mtibs/<node_id>/register",                         endpoint="register_managed_mtib",   view_func=register_node,        methods=["POST"])

    # Devices - MTIBs Observability
    v2.add_url_rule("/devices/mtibs/observability",                                  endpoint="fleet_observability",        view_func=get_fleet_observability,   methods=["GET"])
    v2.add_url_rule("/devices/mtibs/<node_id>/observability",                        endpoint="node_observability",         view_func=get_node_observability,    methods=["GET"])
    v2.add_url_rule("/devices/mtibs/<node_id>/observability/power",                  endpoint="node_observability_power",   view_func=get_node_power,            methods=["GET"])
    v2.add_url_rule("/devices/mtibs/<node_id>/observability/gpio",                   endpoint="node_observability_gpio",    view_func=get_node_gpio,             methods=["GET"])
    v2.add_url_rule("/devices/mtibs/<node_id>/observability/uart",                   endpoint="node_observability_uart",    view_func=get_node_uart,             methods=["GET"])
    v2.add_url_rule("/devices/mtibs/<node_id>/observability/system",                 endpoint="node_observability_system",  view_func=get_node_system,           methods=["GET"])

    # Devices - ICLE
    v2.add_url_rule("/devices/icle/heartbeat",                              endpoint="icle_heartbeat",           view_func=icle_heartbeat,       methods=["POST"])
    v2.add_url_rule("/devices/icle",                                        endpoint="list_icle_devices",        view_func=list_icle_devices,    methods=["GET"])
    v2.add_url_rule("/devices/icle/<device_id>",                            endpoint="get_icle_device",          view_func=get_icle_device,      methods=["GET"])
    v2.add_url_rule("/devices/icle/<device_id>",                            endpoint="update_icle_device",       view_func=update_icle_device,   methods=["PUT"])
    v2.add_url_rule("/devices/icle/<device_id>",                            endpoint="delete_icle_device",       view_func=delete_icle_device,   methods=["DELETE"])
    v2.add_url_rule("/devices/icle/<device_id>/config",                     endpoint="push_icle_config",         view_func=push_icle_config,     methods=["PUT"])
    v2.add_url_rule("/devices/icle/<device_id>/ota",                        endpoint="trigger_icle_ota",         view_func=trigger_icle_ota,     methods=["POST"])
    v2.add_url_rule("/devices/icle/<device_id>/logs",                       endpoint="list_icle_logs",           view_func=list_icle_logs,       methods=["GET"])
    v2.add_url_rule("/devices/icle/<device_id>/logs",                       endpoint="upload_icle_log",          view_func=upload_icle_log,      methods=["POST"])
    v2.add_url_rule("/devices/icle/commands/<command_id>/ack",              endpoint="ack_icle_command",         view_func=ack_icle_command,     methods=["POST"])

    # Kubernetes (was /cluster)
    v2.add_url_rule("/kubernetes/info",                    view_func=get_cluster,     methods=["GET"])
    v2.add_url_rule("/kubernetes/namespaces",              view_func=get_namespaces,  methods=["GET"])
    v2.add_url_rule("/kubernetes/nodes",                   view_func=list_system_nodes,      methods=["GET"])
    v2.add_url_rule("/kubernetes/nodes/<node_name>",       view_func=get_system_node,        methods=["GET"])
    v2.add_url_rule("/kubernetes/events",                  view_func=get_events,      methods=["GET"])

    # Kubernetes - Pods
    v2.add_url_rule("/kubernetes/pods",                                      view_func=list_pods,          methods=["GET"])
    v2.add_url_rule("/kubernetes/pods/<namespace>/<name>",                   view_func=get_pod,            methods=["GET"])
    v2.add_url_rule("/kubernetes/pods/<namespace>/<name>/logs",              view_func=get_pod_logs,       methods=["GET"])
    v2.add_url_rule("/kubernetes/pods/<namespace>/<name>",                   view_func=delete_pod,         methods=["DELETE"])

    # Kubernetes - Deployments
    v2.add_url_rule("/kubernetes/deployments",                               view_func=list_system_deployments,   methods=["GET"])
    v2.add_url_rule("/kubernetes/deployments/<namespace>/<name>",            view_func=get_system_deployment,     methods=["GET"])
    v2.add_url_rule("/kubernetes/deployments/<namespace>/<name>/scale",      view_func=scale_deployment,   methods=["POST"])
    v2.add_url_rule("/kubernetes/deployments/<namespace>/<name>/restart",    view_func=restart_system_deployment, methods=["POST"])

    # Kubernetes - Services
    v2.add_url_rule("/kubernetes/services",                                  view_func=list_services,      methods=["GET"])
    v2.add_url_rule("/kubernetes/services/<namespace>/<name>",               view_func=get_service,        methods=["GET"])

    # Kubernetes - Jobs
    v2.add_url_rule("/kubernetes/jobs",                                      view_func=list_jobs,          methods=["GET"])
    v2.add_url_rule("/kubernetes/jobs/<namespace>/<name>",                   view_func=get_job,            methods=["GET"])
    v2.add_url_rule("/kubernetes/jobs/<namespace>/<name>",                   view_func=delete_job,         methods=["DELETE"])

    # Kubernetes - ConfigMaps & Secrets
    v2.add_url_rule("/kubernetes/configmaps",                                view_func=list_configmaps,    methods=["GET"])
    v2.add_url_rule("/kubernetes/configmaps/<namespace>/<name>",             view_func=get_configmap,      methods=["GET"])
    v2.add_url_rule("/kubernetes/secrets",                                   view_func=list_secrets,       methods=["GET"])
    v2.add_url_rule("/kubernetes/secrets/<namespace>/<name>",                view_func=get_secret,         methods=["GET"])

    # Health
    v2.add_url_rule("/healthcheck",          view_func=healthcheck,     methods=["GET"])

    # Docs
    v2.add_url_rule("/openapi.json",         view_func=openapi_spec,    methods=["GET"])
    v2.add_url_rule("/docs",                 view_func=swagger_ui,      methods=["GET"])

    # Kubernetes - Resource YAML
    v2.add_url_rule("/kubernetes/resources/<kind>/<namespace>/<name>",       view_func=get_resource_yaml,       methods=["GET"])
    v2.add_url_rule("/kubernetes/resources/<kind>/<namespace>/<name>",       view_func=apply_resource_yaml,     methods=["PUT"])
    v2.add_url_rule("/kubernetes/resources/<kind>/<namespace>/<name>",       view_func=delete_resource,         methods=["DELETE"])

    # Kubernetes - RBAC
    v2.add_url_rule("/kubernetes/rbac/roles",                               view_func=list_roles,              methods=["GET"])
    v2.add_url_rule("/kubernetes/rbac/cluster-roles",                       view_func=list_cluster_roles,      methods=["GET"])
    v2.add_url_rule("/kubernetes/rbac/role-bindings",                       view_func=list_role_bindings,      methods=["GET"])
    v2.add_url_rule("/kubernetes/rbac/cluster-role-bindings",               view_func=list_cluster_role_bindings, methods=["GET"])
    v2.add_url_rule("/kubernetes/rbac/service-accounts",                    view_func=list_service_accounts,   methods=["GET"])

    # Builds - Webhooks & Triggers
    v2.add_url_rule("/builds/webhooks/bitbucket",                                               endpoint="ci_webhook_bitbucket",     view_func=webhook_bitbucket,     methods=["POST"])
    v2.add_url_rule("/builds/trigger",                                                          endpoint="ci_trigger_build_run",      view_func=trigger_build_run,      methods=["POST"])
    v2.add_url_rule("/builds/events",                                                           endpoint="ci_receive_repo_event",     view_func=receive_repo_event,     methods=["POST"])

    # Builds
    v2.add_url_rule("/builds",                                                                  endpoint="list_ci_builds",           view_func=list_ci_builds,        methods=["GET"])
    v2.add_url_rule("/builds",                                                                  endpoint="create_ci_build",          view_func=create_ci_build,       methods=["POST"])
    v2.add_url_rule("/builds/<build_id>",                                                       endpoint="get_ci_build",             view_func=get_ci_build,          methods=["GET"])
    v2.add_url_rule("/builds/<build_id>",                                                       endpoint="update_ci_build",          view_func=update_ci_build,       methods=["PATCH"])
    v2.add_url_rule("/builds/<build_id>/artifacts",                                             endpoint="list_ci_build_artifacts",  view_func=list_ci_build_artifacts, methods=["GET"])
    v2.add_url_rule("/builds/<build_id>/artifacts",                                             endpoint="upload_ci_build_artifact", view_func=upload_ci_build_artifact, methods=["POST"])
    v2.add_url_rule("/builds/<build_id>/artifacts/download",                                    endpoint="download_ci_build_artifacts", view_func=download_ci_build_artifacts, methods=["GET"])
    v2.add_url_rule("/builds/<build_id>/artifacts/<artifact_name>",                             endpoint="download_ci_single_artifact", view_func=download_ci_single_artifact, methods=["GET"])
    v2.add_url_rule("/builds/<build_id>/log",                                                   endpoint="get_ci_build_log",         view_func=get_ci_build_log,      methods=["GET"])
    v2.add_url_rule("/builds/<build_id>/log",                                                   endpoint="stream_ci_build_log",      view_func=stream_ci_build_log,   methods=["POST"])
    v2.add_url_rule("/builds/<build_id>/progress",                                              endpoint="report_ci_build_progress", view_func=report_ci_build_progress, methods=["POST"])
    v2.add_url_rule("/builds/<build_id>/reset",                                                 endpoint="reset_ci_build",           view_func=reset_ci_build,        methods=["POST"])

    # Builds - PR Pipelines & Summary
    v2.add_url_rule("/builds/prs",                                                         endpoint="list_pr_pipelines",        view_func=list_pr_pipelines,      methods=["GET"])
    v2.add_url_rule("/builds/summary",                                                     endpoint="get_build_summary",        view_func=get_build_summary,      methods=["GET"])

    # Builds - Pipelines
    v2.add_url_rule("/builds/runs",                                                        endpoint="list_ci_pipelines",        view_func=list_ci_build_runs,     methods=["GET"])
    v2.add_url_rule("/builds/runs",                                                        endpoint="create_ci_pipeline",       view_func=create_ci_build_run,    methods=["POST"])
    v2.add_url_rule("/builds/runs/<run_id>",                                          endpoint="get_ci_pipeline",          view_func=get_ci_build_run,       methods=["GET"])
    v2.add_url_rule("/builds/runs/<run_id>/cancel",                                   endpoint="cancel_ci_pipeline",       view_func=cancel_ci_build_run,    methods=["POST"])
    v2.add_url_rule("/builds/runs/<run_id>/retrigger",                               endpoint="retrigger_ci_pipeline",    view_func=retrigger_ci_build_run, methods=["POST"])
    v2.add_url_rule("/builds/runs/<run_id>/validate",                                endpoint="validate_ci_pipeline",     view_func=validate_ci_build_run,  methods=["POST"])
    v2.add_url_rule("/builds/runs/<run_id>/artifacts/download",                       endpoint="download_ci_pipeline_artifacts", view_func=download_ci_build_run_artifacts, methods=["GET"])
    v2.add_url_rule("/builds/runs/<run_id>/sessions",                               endpoint="list_ci_pipeline_sessions",view_func=list_ci_build_run_sessions, methods=["GET"])
    v2.add_url_rule("/builds/runs/<run_id>/validate-artifacts",                     endpoint="validate_ci_pipeline_artifacts", view_func=validate_ci_build_run_artifacts, methods=["POST"])

    # Builds - Settings
    v2.add_url_rule("/builds/settings/repos",                                                   endpoint="list_ci_repos",            view_func=list_ci_repos,         methods=["GET"])

    # Builds - Scripts
    v2.add_url_rule("/builds/scripts",                                                          endpoint="list_build_scripts",       view_func=list_build_scripts,    methods=["GET"])
    v2.add_url_rule("/builds/scripts/<product>",                                                endpoint="get_build_script",         view_func=get_build_script,      methods=["GET"])

    # Builds - Overlays
    v2.add_url_rule("/builds/overlays/<product>",                                               endpoint="get_overlays",             view_func=get_overlays,          methods=["GET"])
    v2.add_url_rule("/builds/overlays/<product>/list",                                          endpoint="list_overlays",            view_func=list_overlays,         methods=["GET"])

    # Builds - Stage Definitions
    v2.add_url_rule("/builds/stage-defs",                                                       endpoint="get_stage_defs",           view_func=get_stage_defs,        methods=["GET"])

    # Builds - Recipe Templates
    v2.add_url_rule("/builds/recipe-templates",                                                 endpoint="list_recipe_templates",    view_func=list_recipe_templates, methods=["GET"])
    v2.add_url_rule("/builds/recipe-templates/<template_id>",                                   endpoint="get_recipe_template",      view_func=get_recipe_template,   methods=["GET"])

    # WebSocket handlers
    register_log_handlers(socketio)
    register_exec_handlers(socketio)
    register_observability_handlers(socketio)
    register_icle_handlers(socketio)
    register_validation_ws_handlers(socketio)

    # Set SocketIO instances
    set_icle_socketio(socketio)
    set_validation_socketio(socketio)
    set_ci_socketio(socketio)

    server.register_blueprint(v2)
