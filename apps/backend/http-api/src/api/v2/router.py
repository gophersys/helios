import logging
import re

from corekinect.utils import Logger
from flask import Blueprint, Flask
from flask_socketio import SocketIO

# Auth handlers
from .auth.api_keys import create_api_key, delete_api_key, list_api_keys
from .auth.login import login
from .auth.me import me
from .auth.permission_sets import (
    create_permission_set,
    delete_permission_set,
    list_permission_sets,
    update_permission_set,
)
from .auth.permissions_list import list_permissions
from .auth.users import users_create, users_delete, users_list, users_update

# Health
from .healthcheck import healthcheck

# MTIB handlers
from .mtib.get import get_mtib
from .mtib.list import list_mtibs
from .mtib.register import register_mtib
from .mtib.unregister import unregister_mtib

# Codebases handlers
from .codebases.codebases import (
    create_codebase,
    delete_codebase,
    get_codebase,
    list_codebases,
    update_codebase,
    upload_codebase_image,
)
from .codebases.releases import (
    create_release,
    delete_release,
    update_release,
)
from .codebases.artifacts import (
    create_artifact,
    delete_artifact,
    download_artifact,
    list_artifacts,
    upload_artifact,
)

# Catalog handlers
from .catalog.chipsets import (
    create_chipset,
    delete_chipset,
    get_chipset,
    list_chipsets,
    update_chipset,
)
from .catalog.products import (
    create_product,
    delete_product,
    get_product,
    get_product_by_repo,
    get_product_by_slug,
    list_products,
    update_product,
)
from .catalog.boards import (
    create_board,
    delete_board,
    get_board,
    list_boards,
    update_board,
)
from .catalog.board_revisions import (
    create_board_revision,
    delete_board_revision,
    update_board_revision,
)
from .catalog.firmware_builds import (
    delete_firmware_build,
    download_firmware_build,
    list_firmware_builds,
    update_firmware_build,
    upload_firmware_build,
)

# Admin handlers
from .admin.history import get_history_entry, list_history

# System Monitor handlers
from .system.info import get_system_info
from .system.cluster import get_cluster, get_namespaces
from .system.nodes import list_nodes as list_system_nodes, get_node as get_system_node
from .system.events import get_events
from .system.pods import list_pods, get_pod, get_pod_logs, delete_pod
from .system.deployments import (
    list_deployments as list_system_deployments,
    get_deployment as get_system_deployment,
    scale_deployment,
    restart_deployment as restart_system_deployment,
)
from .system.services_api import list_services, get_service
from .system.jobs import list_jobs, get_job, delete_job
from .system.config import list_configmaps, get_configmap, list_secrets, get_secret
from .system.logs import register_log_handlers
from .system.resources import get_resource_yaml, apply_resource_yaml, delete_resource
from .system.rbac import list_roles, list_cluster_roles, list_role_bindings, list_cluster_role_bindings, list_service_accounts
from .system.exec import register_exec_handlers
from .system.uart import register_uart_handlers
from .system.analyzer_stream import register_analyzer_handlers
from .system.observability_ws import register_observability_handlers, register_icle_handlers
from .system.retention import cleanup_validation_runs, get_validation_storage_usage

# Validation WebSocket handlers
from .validation.runs.validation_ws import register_validation_ws_handlers

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

# Node management handlers
from .nodes.nodes import (
    list_nodes as list_managed_nodes,
    create_node,
    sync_nodes_from_k8s,
    get_node as get_managed_node,
    update_node,
    delete_node,
    check_node_health,
    register_node,
    deploy_node,
    undeploy_node,
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
)

# Deployment management handlers
from .deployments.deployments import (
    create_deployment,
    delete_deployment,
    deploy_fixture,
    get_deployment,
    get_deployment_status,
    list_deployments as list_managed_deployments,
    restart_deployment as restart_managed_deployment,
    stop_deployment,
)

# Observability handlers
from .observability.observability import (
    get_fleet_observability,
    get_node_observability,
    get_node_power,
    get_node_gpio,
    get_node_uart,
    get_node_system,
)

# Docs
from .docs import openapi_spec, swagger_ui

# Validation handlers
from .validation.tests.run import run_tests

# Validation runs handlers
from .validation.runs.runs import (
    create_run,
    list_runs,
    get_run,
    cancel_run,
)
from .validation.runs.executions import (
    list_executions,
    list_execution_results,
)
from .validation.runs.artifacts import (
    list_artifacts as list_run_artifacts,
    download_artifact as download_run_artifact,
)
from .validation.runs.reporter import (
    report_start,
    report_test_start,
    report_test_result,
    report_finish,
)
from .validation.runs.trigger import trigger_run
from .validation.runs.demo import simulate_run
from .validation.runs.reporter import set_validation_socketio
from .validation.runs.logs import (
    report_log_chunk,
    get_log_file,
    download_run,
    get_manifest,
)

# Validation — Test Benches
from .validation.benches.benches import (
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

# Validation — Fixture Designs
from .validation.designs.designs import (
    list_designs,
    get_design,
    create_design,
    update_design,
    delete_design,
    get_design_profile,
)

# Validation — Test Catalog (source of truth for test definitions)
from .validation.catalog import (
    list_catalogs,
    get_catalog,
    get_catalog_stages,
    get_catalog_tests,
    get_catalog_test,
    sync_catalog,
    get_catalog_sync_status,
)

# CI / Build handlers
from .ci.webhook import webhook_bitbucket, trigger_pipeline, set_ci_socketio, list_ci_repos
from .ci.builds import (
    list_builds as list_ci_builds,
    get_build as get_ci_build,
    list_build_artifacts as list_ci_build_artifacts,
    download_build_artifacts as download_ci_build_artifacts,
    get_build_log as get_ci_build_log,
    stream_build_log as stream_ci_build_log,
    create_build as create_ci_build,
    update_build as update_ci_build,
    upload_build_artifact as upload_ci_build_artifact,
    reset_build as reset_ci_build,
)
from .ci.pipelines import (
    list_pipelines as list_ci_pipelines,
    get_pipeline as get_ci_pipeline,
    create_pipeline as create_ci_pipeline,
    cancel_pipeline as cancel_ci_pipeline,
    download_pipeline_artifacts as download_ci_pipeline_artifacts,
)
from .ci.scripts import (
    list_build_scripts,
    get_build_script,
    upload_build_script,
    delete_build_script,
)
from .ci.overlays import (
    get_overlays,
    list_overlays,
)


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
    # Add a log filter to avoid spamming the logs with commonly hit routes
    logger.add_filter(LogFilter())

    # Auth (login + me only — stays under /auth)
    v2.add_url_rule("/auth/login",           view_func=login,          methods=["POST"])
    v2.add_url_rule("/auth/me",              view_func=me,             methods=["GET"])

    # Users (was /auth/users)
    v2.add_url_rule("/users",           view_func=users_list,     methods=["GET"])
    v2.add_url_rule("/users",           view_func=users_create,   methods=["POST"])
    v2.add_url_rule("/users/<user_id>", view_func=users_update,   methods=["PUT"])
    v2.add_url_rule("/users/<user_id>", view_func=users_delete,   methods=["DELETE"])

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

    # MTIB (legacy — moved under /devices/mtib)
    v2.add_url_rule("/devices/mtib/list",            view_func=list_mtibs,      methods=["GET"])
    v2.add_url_rule("/devices/mtib/get",             view_func=get_mtib,        methods=["GET"])
    v2.add_url_rule("/devices/mtib/register",        view_func=register_mtib,   methods=["POST"])
    v2.add_url_rule("/devices/mtib/unregister",      view_func=unregister_mtib, methods=["POST"])

    # Codebases (moved under /builds/codebases)
    v2.add_url_rule("/builds/codebases",                                                                     view_func=list_codebases,        methods=["GET"])
    v2.add_url_rule("/builds/codebases",                                                                     view_func=create_codebase,       methods=["POST"])
    v2.add_url_rule("/builds/codebases/<codebase_id>",                                                       view_func=get_codebase,          methods=["GET"])
    v2.add_url_rule("/builds/codebases/<codebase_id>",                                                       view_func=update_codebase,       methods=["PUT"])
    v2.add_url_rule("/builds/codebases/<codebase_id>",                                                       view_func=delete_codebase,       methods=["DELETE"])
    v2.add_url_rule("/builds/codebases/<codebase_id>/image",                                                 view_func=upload_codebase_image, methods=["POST"])
    v2.add_url_rule("/builds/codebases/<codebase_id>/releases",                                              view_func=create_release,        methods=["POST"])
    v2.add_url_rule("/builds/codebases/<codebase_id>/releases/<release_id>",                                 view_func=update_release,        methods=["PUT"])
    v2.add_url_rule("/builds/codebases/<codebase_id>/releases/<release_id>",                                 view_func=delete_release,        methods=["DELETE"])
    v2.add_url_rule("/builds/codebases/<codebase_id>/releases/<release_id>/artifacts",                       view_func=list_artifacts,        methods=["GET"])
    v2.add_url_rule("/builds/codebases/<codebase_id>/releases/<release_id>/artifacts",                       view_func=create_artifact,       methods=["POST"])
    v2.add_url_rule("/builds/codebases/<codebase_id>/releases/<release_id>/artifacts/upload",                view_func=upload_artifact,       methods=["POST"])
    v2.add_url_rule("/builds/codebases/<codebase_id>/releases/<release_id>/artifacts/<artifact_id>",         view_func=delete_artifact,       methods=["DELETE"])
    v2.add_url_rule("/builds/codebases/artifacts/<artifact_id>/download",                                    view_func=download_artifact,     methods=["GET"])

    # Products - Chipsets (was /catalog/chipsets)
    v2.add_url_rule("/products/chipsets",                                                          view_func=list_chipsets,           methods=["GET"])
    v2.add_url_rule("/products/chipsets",                                                          view_func=create_chipset,          methods=["POST"])
    v2.add_url_rule("/products/chipsets/<chipset_id>",                                             view_func=get_chipset,             methods=["GET"])
    v2.add_url_rule("/products/chipsets/<chipset_id>",                                             view_func=update_chipset,          methods=["PUT"])
    v2.add_url_rule("/products/chipsets/<chipset_id>",                                             view_func=delete_chipset,          methods=["DELETE"])

    # Products (was /catalog)
    v2.add_url_rule("/products",                                                                   view_func=list_products,          methods=["GET"])
    v2.add_url_rule("/products",                                                                   view_func=create_product,         methods=["POST"])
    v2.add_url_rule("/products/by-slug/<slug>",                                                    view_func=get_product_by_slug,    methods=["GET"])
    v2.add_url_rule("/products/by-repo/<repo_slug>",                                               view_func=get_product_by_repo,    methods=["GET"])
    v2.add_url_rule("/products/<product_id>",                                                      view_func=get_product,            methods=["GET"])
    v2.add_url_rule("/products/<product_id>",                                                      view_func=update_product,         methods=["PUT"])
    v2.add_url_rule("/products/<product_id>",                                                      view_func=delete_product,         methods=["DELETE"])

    # Products - Boards (was /catalog/<id>/boards)
    v2.add_url_rule("/products/<product_id>/boards",                                               view_func=list_boards,            methods=["GET"])
    v2.add_url_rule("/products/<product_id>/boards",                                               view_func=create_board,           methods=["POST"])
    v2.add_url_rule("/products/<product_id>/boards/<board_id>",                                    view_func=get_board,              methods=["GET"])
    v2.add_url_rule("/products/<product_id>/boards/<board_id>",                                    view_func=update_board,           methods=["PUT"])
    v2.add_url_rule("/products/<product_id>/boards/<board_id>",                                    view_func=delete_board,           methods=["DELETE"])

    # Products - Board Revisions (was /catalog/<id>/boards/<id>/revisions)
    v2.add_url_rule("/products/<product_id>/boards/<board_id>/revisions",                          view_func=create_board_revision,  methods=["POST"])
    v2.add_url_rule("/products/<product_id>/boards/<board_id>/revisions/<revision_id>",            view_func=update_board_revision,  methods=["PUT"])
    v2.add_url_rule("/products/<product_id>/boards/<board_id>/revisions/<revision_id>",            view_func=delete_board_revision,  methods=["DELETE"])

    # Products - Firmware (was /catalog/<id>/firmware-builds)
    v2.add_url_rule("/products/<product_id>/firmware",                                             view_func=list_firmware_builds,   methods=["GET"])
    v2.add_url_rule("/products/<product_id>/firmware/upload",                                      view_func=upload_firmware_build,  methods=["POST"])
    v2.add_url_rule("/products/<product_id>/firmware/<build_id>",                                  view_func=update_firmware_build,  methods=["PUT"])
    v2.add_url_rule("/products/<product_id>/firmware/<build_id>",                                  view_func=delete_firmware_build,  methods=["DELETE"])
    v2.add_url_rule("/products/firmware/<build_id>/download",                                      view_func=download_firmware_build, methods=["GET"])

    # System - History (was /admin/history)
    v2.add_url_rule("/system/history",              view_func=list_history,      methods=["GET"])
    v2.add_url_rule("/system/history/<entry_id>",   view_func=get_history_entry, methods=["GET"])

    # Validation — legacy manufacturing test run
    v2.add_url_rule("/validation/tests/run", view_func=run_tests,       methods=["POST"])

    # Validation — Runs (Stage 4)
    v2.add_url_rule("/validation/runs",                                                                    endpoint="list_validation_runs",         view_func=list_runs,                methods=["GET"])
    v2.add_url_rule("/validation/runs",                                                                    endpoint="create_validation_run",        view_func=create_run,               methods=["POST"])
    v2.add_url_rule("/validation/runs/<run_id>",                                                           endpoint="get_validation_run",           view_func=get_run,                  methods=["GET"])
    v2.add_url_rule("/validation/runs/<run_id>/cancel",                                                    endpoint="cancel_validation_run",        view_func=cancel_run,               methods=["POST"])
    v2.add_url_rule("/validation/runs/<run_id>/executions",                                                endpoint="list_validation_executions",   view_func=list_executions,          methods=["GET"])
    v2.add_url_rule("/validation/runs/<run_id>/executions/<execution_id>/results",                         endpoint="list_execution_results",       view_func=list_execution_results,   methods=["GET"])
    v2.add_url_rule("/validation/runs/<run_id>/artifacts",                                                 endpoint="list_run_artifacts",           view_func=list_run_artifacts,       methods=["GET"])
    v2.add_url_rule("/validation/runs/<run_id>/artifacts/<path:name>",                                     endpoint="download_run_artifact",        view_func=download_run_artifact,    methods=["GET"])

    # Validation — Trigger
    v2.add_url_rule("/validation/runs/<run_id>/trigger",                                                    endpoint="trigger_validation_run",       view_func=trigger_run,              methods=["POST"])

    # Validation — Reporter callbacks (called by pytest plugin in K8s Jobs)
    v2.add_url_rule("/validation/runs/<run_id>/report/start",                                              endpoint="report_run_start",             view_func=report_start,             methods=["POST"])
    v2.add_url_rule("/validation/runs/<run_id>/report/test-start",                                         endpoint="report_test_start",            view_func=report_test_start,        methods=["POST"])
    v2.add_url_rule("/validation/runs/<run_id>/report/test-result",                                        endpoint="report_test_result",           view_func=report_test_result,       methods=["POST"])
    v2.add_url_rule("/validation/runs/<run_id>/report/finish",                                             endpoint="report_run_finish",            view_func=report_finish,            methods=["POST"])
    v2.add_url_rule("/validation/runs/<run_id>/report/log-chunk",                                          endpoint="report_log_chunk",             view_func=report_log_chunk,         methods=["POST"])

    # Validation — Log & artifact retrieval
    v2.add_url_rule("/validation/runs/<run_id>/logs/<path:file_path>",                                     endpoint="get_run_log_file",             view_func=get_log_file,             methods=["GET"])
    v2.add_url_rule("/validation/runs/<run_id>/download",                                                  endpoint="download_validation_run",      view_func=download_run,             methods=["GET"])
    v2.add_url_rule("/validation/runs/<run_id>/manifest",                                                  endpoint="get_run_manifest",             view_func=get_manifest,             methods=["GET"])

    # Validation — Demo (simulate a run via WebSocket events)
    v2.add_url_rule("/validation/runs/<run_id>/demo/simulate",                                            endpoint="simulate_validation_run",      view_func=simulate_run,             methods=["POST"])

    # Benches (was /validation/benches)
    v2.add_url_rule("/benches",                                                                endpoint="list_benches",                 view_func=list_benches,             methods=["GET"])
    v2.add_url_rule("/benches",                                                                endpoint="create_bench",                 view_func=create_bench,             methods=["POST"])
    v2.add_url_rule("/benches/discover",                                                       endpoint="discover_mtibs",               view_func=discover_mtibs,           methods=["GET"])
    v2.add_url_rule("/benches/<bench_id>",                                                     endpoint="get_bench",                    view_func=get_bench,                methods=["GET"])
    v2.add_url_rule("/benches/<bench_id>",                                                     endpoint="update_bench",                 view_func=update_bench,             methods=["PATCH"])
    v2.add_url_rule("/benches/<bench_id>",                                                     endpoint="delete_bench",                 view_func=delete_bench,             methods=["DELETE"])
    v2.add_url_rule("/benches/<bench_id>/lock",                                                endpoint="lock_bench",                   view_func=lock_bench,               methods=["POST"])
    v2.add_url_rule("/benches/<bench_id>/unlock",                                              endpoint="unlock_bench",                 view_func=unlock_bench,             methods=["POST"])
    v2.add_url_rule("/benches/<bench_id>/profile",                                             endpoint="get_bench_profile",            view_func=get_bench_profile,        methods=["GET"])

    # Benches — Fixture Designs (was /validation/designs)
    v2.add_url_rule("/benches/designs",                                                                endpoint="list_designs",                 view_func=list_designs,             methods=["GET"])
    v2.add_url_rule("/benches/designs",                                                                endpoint="create_design",                view_func=create_design,            methods=["POST"])
    v2.add_url_rule("/benches/designs/<design_id>",                                                    endpoint="get_design",                   view_func=get_design,               methods=["GET"])
    v2.add_url_rule("/benches/designs/<design_id>",                                                    endpoint="update_design",                view_func=update_design,            methods=["PATCH"])
    v2.add_url_rule("/benches/designs/<design_id>",                                                    endpoint="delete_design",                view_func=delete_design,            methods=["DELETE"])
    v2.add_url_rule("/benches/designs/<design_id>/profile",                                            endpoint="get_design_profile",           view_func=get_design_profile,       methods=["GET"])

    # Validation — Test Catalog (source of truth for test definitions)
    v2.add_url_rule("/validation/catalog",                                                                endpoint="list_catalogs",                view_func=list_catalogs,            methods=["GET"])
    v2.add_url_rule("/validation/catalog/<product>",                                                      endpoint="get_catalog",                  view_func=get_catalog,              methods=["GET"])
    v2.add_url_rule("/validation/catalog/<product>/stages",                                               endpoint="get_catalog_stages",           view_func=get_catalog_stages,       methods=["GET"])
    v2.add_url_rule("/validation/catalog/<product>/tests",                                                endpoint="get_catalog_tests",            view_func=get_catalog_tests,        methods=["GET"])
    v2.add_url_rule("/validation/catalog/<product>/tests/<test_id>",                                      endpoint="get_catalog_test",             view_func=get_catalog_test,         methods=["GET"])
    v2.add_url_rule("/validation/catalog/<product>/sync",                                                 endpoint="sync_catalog",                 view_func=sync_catalog,             methods=["POST"])
    v2.add_url_rule("/validation/catalog/<product>/sync",                                                 endpoint="get_catalog_sync_status",      view_func=get_catalog_sync_status,  methods=["GET"])

    # Dashboard
    v2.add_url_rule("/dashboard/overview",                           endpoint="dashboard_overview",          view_func=dashboard_overview,         methods=["GET"])

    # Cluster — Managed Deployments (was /deployments)
    v2.add_url_rule("/cluster/managed-deployments",                                 endpoint="list_managed_deployments",    view_func=list_managed_deployments,   methods=["GET"])
    v2.add_url_rule("/cluster/managed-deployments",                                 endpoint="create_managed_deployment",   view_func=create_deployment,          methods=["POST"])
    v2.add_url_rule("/cluster/managed-deployments/<deployment_id>",                 endpoint="get_managed_deployment",      view_func=get_deployment,             methods=["GET"])
    v2.add_url_rule("/cluster/managed-deployments/<deployment_id>",                 endpoint="delete_managed_deployment",   view_func=delete_deployment,          methods=["DELETE"])
    v2.add_url_rule("/cluster/managed-deployments/<deployment_id>/deploy",          endpoint="deploy_managed_fixture",      view_func=deploy_fixture,             methods=["POST"])
    v2.add_url_rule("/cluster/managed-deployments/<deployment_id>/stop",            endpoint="stop_managed_deployment",     view_func=stop_deployment,            methods=["POST"])
    v2.add_url_rule("/cluster/managed-deployments/<deployment_id>/restart",         endpoint="restart_managed_deployment",  view_func=restart_managed_deployment, methods=["POST"])
    v2.add_url_rule("/cluster/managed-deployments/<deployment_id>/status",          endpoint="get_managed_deployment_status", view_func=get_deployment_status,    methods=["GET"])

    # Devices — MTIBs (was /mtibs)
    v2.add_url_rule("/devices/mtibs",                                            endpoint="list_managed_mtibs",      view_func=list_managed_nodes,   methods=["GET"])
    v2.add_url_rule("/devices/mtibs",                                            endpoint="create_managed_mtib",     view_func=create_node,          methods=["POST"])
    v2.add_url_rule("/devices/mtibs/discover",                                   endpoint="discover_managed_mtibs",  view_func=sync_nodes_from_k8s,  methods=["POST"])
    v2.add_url_rule("/devices/mtibs/<node_id>",                                  endpoint="get_managed_mtib",        view_func=get_managed_node,     methods=["GET"])
    v2.add_url_rule("/devices/mtibs/<node_id>",                                  endpoint="update_managed_mtib",     view_func=update_node,          methods=["PUT"])
    v2.add_url_rule("/devices/mtibs/<node_id>",                                  endpoint="delete_managed_mtib",     view_func=delete_node,          methods=["DELETE"])
    v2.add_url_rule("/devices/mtibs/<node_id>/health",                           endpoint="check_managed_mtib_health", view_func=check_node_health,  methods=["POST"])
    v2.add_url_rule("/devices/mtibs/<node_id>/register",                         endpoint="register_managed_mtib",   view_func=register_node,        methods=["POST"])
    v2.add_url_rule("/devices/mtibs/<node_id>/deploy",                           endpoint="deploy_managed_mtib",     view_func=deploy_node,          methods=["POST"])
    v2.add_url_rule("/devices/mtibs/<node_id>/undeploy",                         endpoint="undeploy_managed_mtib",   view_func=undeploy_node,        methods=["POST"])

    # Devices — MTIBs Observability (was /mtibs/observability)
    v2.add_url_rule("/devices/mtibs/observability",                                  endpoint="fleet_observability",        view_func=get_fleet_observability,   methods=["GET"])
    v2.add_url_rule("/devices/mtibs/<node_id>/observability",                        endpoint="node_observability",         view_func=get_node_observability,    methods=["GET"])
    v2.add_url_rule("/devices/mtibs/<node_id>/observability/power",                  endpoint="node_observability_power",   view_func=get_node_power,            methods=["GET"])
    v2.add_url_rule("/devices/mtibs/<node_id>/observability/gpio",                   endpoint="node_observability_gpio",    view_func=get_node_gpio,             methods=["GET"])
    v2.add_url_rule("/devices/mtibs/<node_id>/observability/uart",                   endpoint="node_observability_uart",    view_func=get_node_uart,             methods=["GET"])
    v2.add_url_rule("/devices/mtibs/<node_id>/observability/system",                 endpoint="node_observability_system",  view_func=get_node_system,           methods=["GET"])

    # Fixtures (managed fixtures)
    v2.add_url_rule("/fixtures",                                         endpoint="list_fixtures",           view_func=list_fixtures,            methods=["GET"])
    v2.add_url_rule("/fixtures",                                         endpoint="create_fixture",          view_func=create_managed_fixture,   methods=["POST"])
    v2.add_url_rule("/fixtures/<fixture_id>",                            endpoint="get_fixture",             view_func=get_fixture,              methods=["GET"])
    v2.add_url_rule("/fixtures/<fixture_id>",                            endpoint="update_fixture",          view_func=update_fixture,           methods=["PUT"])
    v2.add_url_rule("/fixtures/<fixture_id>",                            endpoint="delete_fixture",          view_func=delete_fixture,           methods=["DELETE"])
    v2.add_url_rule("/fixtures/<fixture_id>/slots",                      endpoint="create_slot",             view_func=create_slot,              methods=["POST"])
    v2.add_url_rule("/fixtures/<fixture_id>/slots/<slot_id>",            endpoint="update_slot",             view_func=update_slot,              methods=["PUT"])
    v2.add_url_rule("/fixtures/<fixture_id>/slots/<slot_id>",            endpoint="delete_slot",             view_func=delete_slot,              methods=["DELETE"])
    v2.add_url_rule("/fixtures/<fixture_id>/slots/<slot_id>/assign",     endpoint="assign_slot_node",        view_func=assign_slot_node,         methods=["POST"])

    # System: Build info (no auth required — useful for debugging)
    v2.add_url_rule("/system/info",                 view_func=get_system_info, methods=["GET"])

    # System: Retention management (admin only)
    v2.add_url_rule("/system/retention/validation/cleanup",   endpoint="cleanup_validation_runs",     view_func=cleanup_validation_runs,      methods=["POST"])
    v2.add_url_rule("/system/retention/validation/usage",     endpoint="get_validation_storage_usage", view_func=get_validation_storage_usage, methods=["GET"])

    # Cluster (was /kubernetes)
    v2.add_url_rule("/cluster/info",                    view_func=get_cluster,     methods=["GET"])
    v2.add_url_rule("/cluster/namespaces",              view_func=get_namespaces,  methods=["GET"])
    v2.add_url_rule("/cluster/nodes",                   view_func=list_system_nodes,      methods=["GET"])
    v2.add_url_rule("/cluster/nodes/<node_name>",       view_func=get_system_node,        methods=["GET"])
    v2.add_url_rule("/cluster/events",                  view_func=get_events,      methods=["GET"])

    # Cluster — Pods (was /kubernetes/pods)
    v2.add_url_rule("/cluster/pods",                                      view_func=list_pods,          methods=["GET"])
    v2.add_url_rule("/cluster/pods/<namespace>/<name>",                   view_func=get_pod,            methods=["GET"])
    v2.add_url_rule("/cluster/pods/<namespace>/<name>/logs",              view_func=get_pod_logs,       methods=["GET"])
    v2.add_url_rule("/cluster/pods/<namespace>/<name>",                   view_func=delete_pod,         methods=["DELETE"])

    # Cluster — Deployments (was /kubernetes/deployments)
    v2.add_url_rule("/cluster/deployments",                               view_func=list_system_deployments,   methods=["GET"])
    v2.add_url_rule("/cluster/deployments/<namespace>/<name>",            view_func=get_system_deployment,     methods=["GET"])
    v2.add_url_rule("/cluster/deployments/<namespace>/<name>/scale",      view_func=scale_deployment,   methods=["POST"])
    v2.add_url_rule("/cluster/deployments/<namespace>/<name>/restart",    view_func=restart_system_deployment, methods=["POST"])

    # Cluster — Services (was /kubernetes/services)
    v2.add_url_rule("/cluster/services",                                  view_func=list_services,      methods=["GET"])
    v2.add_url_rule("/cluster/services/<namespace>/<name>",               view_func=get_service,        methods=["GET"])

    # Cluster — Jobs (was /kubernetes/jobs)
    v2.add_url_rule("/cluster/jobs",                                      view_func=list_jobs,          methods=["GET"])
    v2.add_url_rule("/cluster/jobs/<namespace>/<name>",                   view_func=get_job,            methods=["GET"])
    v2.add_url_rule("/cluster/jobs/<namespace>/<name>",                   view_func=delete_job,         methods=["DELETE"])

    # Cluster — ConfigMaps & Secrets (was /kubernetes/configmaps + /kubernetes/secrets)
    v2.add_url_rule("/cluster/configmaps",                                view_func=list_configmaps,    methods=["GET"])
    v2.add_url_rule("/cluster/configmaps/<namespace>/<name>",             view_func=get_configmap,      methods=["GET"])
    v2.add_url_rule("/cluster/secrets",                                   view_func=list_secrets,       methods=["GET"])
    v2.add_url_rule("/cluster/secrets/<namespace>/<name>",                view_func=get_secret,         methods=["GET"])

    # Health
    v2.add_url_rule("/healthcheck",          view_func=healthcheck,     methods=["GET"])

    # Docs
    v2.add_url_rule("/openapi.json",         view_func=openapi_spec,    methods=["GET"])
    v2.add_url_rule("/docs",                 view_func=swagger_ui,      methods=["GET"])

    # Cluster — Resource YAML (was /kubernetes/resources)
    v2.add_url_rule("/cluster/resources/<kind>/<namespace>/<name>",       view_func=get_resource_yaml,       methods=["GET"])
    v2.add_url_rule("/cluster/resources/<kind>/<namespace>/<name>",       view_func=apply_resource_yaml,     methods=["PUT"])
    v2.add_url_rule("/cluster/resources/<kind>/<namespace>/<name>",       view_func=delete_resource,         methods=["DELETE"])

    # Cluster — RBAC (was /kubernetes/rbac)
    v2.add_url_rule("/cluster/rbac/roles",                               view_func=list_roles,              methods=["GET"])
    v2.add_url_rule("/cluster/rbac/clusterroles",                        view_func=list_cluster_roles,      methods=["GET"])
    v2.add_url_rule("/cluster/rbac/bindings",                            view_func=list_role_bindings,      methods=["GET"])
    v2.add_url_rule("/cluster/rbac/clusterrolebindings",                 view_func=list_cluster_role_bindings, methods=["GET"])
    v2.add_url_rule("/cluster/rbac/serviceaccounts",                     view_func=list_service_accounts,   methods=["GET"])

    # Devices — ICLE (was /icle)
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

    # Kubernetes: Log Streaming + Pod Exec (all use /kubernetes namespace)
    register_log_handlers(socketio)
    register_exec_handlers(socketio)
    register_uart_handlers(socketio)
    register_analyzer_handlers(socketio)
    register_observability_handlers(socketio)
    register_icle_handlers(socketio)

    # Validation: WebSocket handlers for /validation namespace
    register_validation_ws_handlers(socketio)

    # Set SocketIO instance for ICLE WebSocket events
    set_icle_socketio(socketio)

    # Set SocketIO instance for validation WebSocket events (reporter.py)
    set_validation_socketio(socketio)

    # Set SocketIO instance for CI WebSocket events
    set_ci_socketio(socketio)

    # Builds — Webhooks & Triggers (was /ci)
    v2.add_url_rule("/builds/webhooks/bitbucket",                                               endpoint="ci_webhook_bitbucket",     view_func=webhook_bitbucket,     methods=["POST"])
    v2.add_url_rule("/builds/trigger",                                                          endpoint="ci_trigger_pipeline",      view_func=trigger_pipeline,      methods=["POST"])

    # Builds (was /ci/builds)
    v2.add_url_rule("/builds",                                                                  endpoint="list_ci_builds",           view_func=list_ci_builds,        methods=["GET"])
    v2.add_url_rule("/builds",                                                                  endpoint="create_ci_build",          view_func=create_ci_build,       methods=["POST"])
    v2.add_url_rule("/builds/<build_id>",                                                       endpoint="get_ci_build",             view_func=get_ci_build,          methods=["GET"])
    v2.add_url_rule("/builds/<build_id>",                                                       endpoint="update_ci_build",          view_func=update_ci_build,       methods=["PATCH"])
    v2.add_url_rule("/builds/<build_id>/artifacts",                                             endpoint="list_ci_build_artifacts",  view_func=list_ci_build_artifacts, methods=["GET"])
    v2.add_url_rule("/builds/<build_id>/artifacts",                                             endpoint="upload_ci_build_artifact", view_func=upload_ci_build_artifact, methods=["POST"])
    v2.add_url_rule("/builds/<build_id>/artifacts/download",                                    endpoint="download_ci_build_artifacts", view_func=download_ci_build_artifacts, methods=["GET"])
    v2.add_url_rule("/builds/<build_id>/log",                                                   endpoint="get_ci_build_log",         view_func=get_ci_build_log,      methods=["GET"])
    v2.add_url_rule("/builds/<build_id>/log",                                                   endpoint="stream_ci_build_log",      view_func=stream_ci_build_log,   methods=["POST"])
    v2.add_url_rule("/builds/<build_id>/reset",                                                 endpoint="reset_ci_build",           view_func=reset_ci_build,        methods=["POST"])

    # Builds — Pipelines (was /ci/pipelines)
    v2.add_url_rule("/builds/pipelines",                                                        endpoint="list_ci_pipelines",        view_func=list_ci_pipelines,     methods=["GET"])
    v2.add_url_rule("/builds/pipelines",                                                        endpoint="create_ci_pipeline",       view_func=create_ci_pipeline,    methods=["POST"])
    v2.add_url_rule("/builds/pipelines/<pipeline_id>",                                          endpoint="get_ci_pipeline",          view_func=get_ci_pipeline,       methods=["GET"])
    v2.add_url_rule("/builds/pipelines/<pipeline_id>/cancel",                                   endpoint="cancel_ci_pipeline",       view_func=cancel_ci_pipeline,    methods=["POST"])
    v2.add_url_rule("/builds/pipelines/<pipeline_id>/artifacts/download",                       endpoint="download_ci_pipeline_artifacts", view_func=download_ci_pipeline_artifacts, methods=["GET"])

    # Builds — Settings (was /ci/settings)
    v2.add_url_rule("/builds/settings/repos",                                                   endpoint="list_ci_repos",            view_func=list_ci_repos,         methods=["GET"])

    # Builds — Scripts (was /ci/scripts)
    v2.add_url_rule("/builds/scripts",                                                          endpoint="list_build_scripts",       view_func=list_build_scripts,    methods=["GET"])
    v2.add_url_rule("/builds/scripts/<product>",                                                endpoint="get_build_script",         view_func=get_build_script,      methods=["GET"])
    v2.add_url_rule("/builds/scripts/<product>",                                                endpoint="upload_build_script",      view_func=upload_build_script,   methods=["PUT"])
    v2.add_url_rule("/builds/scripts/<product>",                                                endpoint="delete_build_script",      view_func=delete_build_script,   methods=["DELETE"])

    # Builds — Overlays (was /ci/overlays)
    v2.add_url_rule("/builds/overlays/<product>",                                               endpoint="get_overlays",             view_func=get_overlays,          methods=["GET"])
    v2.add_url_rule("/builds/overlays/<product>/list",                                          endpoint="list_overlays",            view_func=list_overlays,         methods=["GET"])

    server.register_blueprint(v2)
