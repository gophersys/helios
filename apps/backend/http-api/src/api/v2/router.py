import logging
import re

from corekinect.utils import Logger
from flask import Blueprint, Flask
from flask_socketio import SocketIO

# Auth handlers
from .auth.api_keys import create_api_key, delete_api_key, list_api_keys
from .auth.login import login, login_corecloud
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

# Inventory handlers
from .inventory.components import (
    create_component,
    create_revision,
    delete_component,
    delete_revision,
    get_component,
    list_components,
    update_component,
    update_revision,
    upload_component_image,
)
from .inventory.assemblies import (
    create_assembly,
    create_assembly_revision,
    delete_assembly,
    delete_assembly_revision,
    get_assembly,
    list_assemblies,
    update_assembly,
    update_assembly_revision,
    upload_assembly_image,
)
from .inventory.image import get_inventory_image

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
from .system.pods import list_pods, get_pod, delete_pod
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

    # Auth
    v2.add_url_rule("/auth/login",           view_func=login,          methods=["POST"])
    v2.add_url_rule("/auth/login/corecloud", view_func=login_corecloud, methods=["POST"])
    v2.add_url_rule("/auth/me",              view_func=me,             methods=["GET"])
    v2.add_url_rule("/auth/users",           view_func=users_list,     methods=["GET"])
    v2.add_url_rule("/auth/users",           view_func=users_create,   methods=["POST"])
    v2.add_url_rule("/auth/users/<user_id>", view_func=users_update,   methods=["PUT"])
    v2.add_url_rule("/auth/users/<user_id>", view_func=users_delete,   methods=["DELETE"])

    # Permission Sets
    v2.add_url_rule("/auth/permission-sets",          view_func=list_permission_sets,   methods=["GET"])
    v2.add_url_rule("/auth/permission-sets",          view_func=create_permission_set,  methods=["POST"])
    v2.add_url_rule("/auth/permission-sets/<set_id>", view_func=update_permission_set,  methods=["PUT"])
    v2.add_url_rule("/auth/permission-sets/<set_id>", view_func=delete_permission_set,  methods=["DELETE"])

    # API Keys
    v2.add_url_rule("/auth/api-keys",          view_func=list_api_keys,   methods=["GET"])
    v2.add_url_rule("/auth/api-keys",          view_func=create_api_key,  methods=["POST"])
    v2.add_url_rule("/auth/api-keys/<key_id>", view_func=delete_api_key,  methods=["DELETE"])

    # Available Permissions
    v2.add_url_rule("/auth/permissions",        view_func=list_permissions, methods=["GET"])

    # MTIB
    v2.add_url_rule("/mtib/list",            view_func=list_mtibs,      methods=["GET"])
    v2.add_url_rule("/mtib/get",             view_func=get_mtib,        methods=["GET"])
    v2.add_url_rule("/mtib/register",        view_func=register_mtib,   methods=["POST"])
    v2.add_url_rule("/mtib/unregister",      view_func=unregister_mtib, methods=["POST"])

    # Inventory - Components
    v2.add_url_rule("/inventory/components",                                          view_func=list_components,        methods=["GET"])
    v2.add_url_rule("/inventory/components",                                          view_func=create_component,       methods=["POST"])
    v2.add_url_rule("/inventory/components/<component_id>",                           view_func=get_component,          methods=["GET"])
    v2.add_url_rule("/inventory/components/<component_id>",                           view_func=update_component,       methods=["PUT"])
    v2.add_url_rule("/inventory/components/<component_id>",                           view_func=delete_component,       methods=["DELETE"])
    v2.add_url_rule("/inventory/components/<component_id>/image",                     view_func=upload_component_image, methods=["POST"])
    v2.add_url_rule("/inventory/components/<component_id>/revisions",                 view_func=create_revision,        methods=["POST"])
    v2.add_url_rule("/inventory/components/<component_id>/revisions/<revision_id>",   view_func=update_revision,        methods=["PUT"])
    v2.add_url_rule("/inventory/components/<component_id>/revisions/<revision_id>",   view_func=delete_revision,        methods=["DELETE"])

    # Inventory - Assemblies
    v2.add_url_rule("/inventory/assemblies",                                          view_func=list_assemblies,            methods=["GET"])
    v2.add_url_rule("/inventory/assemblies",                                          view_func=create_assembly,            methods=["POST"])
    v2.add_url_rule("/inventory/assemblies/<assembly_id>",                            view_func=get_assembly,               methods=["GET"])
    v2.add_url_rule("/inventory/assemblies/<assembly_id>",                            view_func=update_assembly,            methods=["PUT"])
    v2.add_url_rule("/inventory/assemblies/<assembly_id>",                            view_func=delete_assembly,            methods=["DELETE"])
    v2.add_url_rule("/inventory/assemblies/<assembly_id>/image",                      view_func=upload_assembly_image,      methods=["POST"])
    v2.add_url_rule("/inventory/assemblies/<assembly_id>/revisions",                  view_func=create_assembly_revision,   methods=["POST"])
    v2.add_url_rule("/inventory/assemblies/<assembly_id>/revisions/<revision_id>",    view_func=update_assembly_revision,   methods=["PUT"])
    v2.add_url_rule("/inventory/assemblies/<assembly_id>/revisions/<revision_id>",    view_func=delete_assembly_revision,   methods=["DELETE"])

    # Inventory - Image serving
    v2.add_url_rule("/inventory/image/<path:key>",                                    view_func=get_inventory_image,         methods=["GET"])

    # Codebases
    v2.add_url_rule("/codebases",                                                                     view_func=list_codebases,        methods=["GET"])
    v2.add_url_rule("/codebases",                                                                     view_func=create_codebase,       methods=["POST"])
    v2.add_url_rule("/codebases/<codebase_id>",                                                       view_func=get_codebase,          methods=["GET"])
    v2.add_url_rule("/codebases/<codebase_id>",                                                       view_func=update_codebase,       methods=["PUT"])
    v2.add_url_rule("/codebases/<codebase_id>",                                                       view_func=delete_codebase,       methods=["DELETE"])
    v2.add_url_rule("/codebases/<codebase_id>/image",                                                 view_func=upload_codebase_image, methods=["POST"])
    v2.add_url_rule("/codebases/<codebase_id>/releases",                                              view_func=create_release,        methods=["POST"])
    v2.add_url_rule("/codebases/<codebase_id>/releases/<release_id>",                                 view_func=update_release,        methods=["PUT"])
    v2.add_url_rule("/codebases/<codebase_id>/releases/<release_id>",                                 view_func=delete_release,        methods=["DELETE"])
    v2.add_url_rule("/codebases/<codebase_id>/releases/<release_id>/artifacts",                       view_func=list_artifacts,        methods=["GET"])
    v2.add_url_rule("/codebases/<codebase_id>/releases/<release_id>/artifacts",                       view_func=create_artifact,       methods=["POST"])
    v2.add_url_rule("/codebases/<codebase_id>/releases/<release_id>/artifacts/upload",                view_func=upload_artifact,       methods=["POST"])
    v2.add_url_rule("/codebases/<codebase_id>/releases/<release_id>/artifacts/<artifact_id>",         view_func=delete_artifact,       methods=["DELETE"])
    v2.add_url_rule("/codebases/artifacts/<artifact_id>/download",                                    view_func=download_artifact,     methods=["GET"])

    # Catalog - Chipsets
    v2.add_url_rule("/catalog/chipsets",                                                          view_func=list_chipsets,           methods=["GET"])
    v2.add_url_rule("/catalog/chipsets",                                                          view_func=create_chipset,          methods=["POST"])
    v2.add_url_rule("/catalog/chipsets/<chipset_id>",                                             view_func=get_chipset,             methods=["GET"])
    v2.add_url_rule("/catalog/chipsets/<chipset_id>",                                             view_func=update_chipset,          methods=["PUT"])
    v2.add_url_rule("/catalog/chipsets/<chipset_id>",                                             view_func=delete_chipset,          methods=["DELETE"])

    # Catalog - Products
    v2.add_url_rule("/catalog",                                                                   view_func=list_products,          methods=["GET"])
    v2.add_url_rule("/catalog",                                                                   view_func=create_product,         methods=["POST"])
    v2.add_url_rule("/catalog/<product_id>",                                                      view_func=get_product,            methods=["GET"])
    v2.add_url_rule("/catalog/<product_id>",                                                      view_func=update_product,         methods=["PUT"])
    v2.add_url_rule("/catalog/<product_id>",                                                      view_func=delete_product,         methods=["DELETE"])

    # Catalog - Boards
    v2.add_url_rule("/catalog/<product_id>/boards",                                               view_func=list_boards,            methods=["GET"])
    v2.add_url_rule("/catalog/<product_id>/boards",                                               view_func=create_board,           methods=["POST"])
    v2.add_url_rule("/catalog/<product_id>/boards/<board_id>",                                    view_func=get_board,              methods=["GET"])
    v2.add_url_rule("/catalog/<product_id>/boards/<board_id>",                                    view_func=update_board,           methods=["PUT"])
    v2.add_url_rule("/catalog/<product_id>/boards/<board_id>",                                    view_func=delete_board,           methods=["DELETE"])

    # Catalog - Board Revisions (nested under boards)
    v2.add_url_rule("/catalog/<product_id>/boards/<board_id>/revisions",                          view_func=create_board_revision,  methods=["POST"])
    v2.add_url_rule("/catalog/<product_id>/boards/<board_id>/revisions/<revision_id>",            view_func=update_board_revision,  methods=["PUT"])
    v2.add_url_rule("/catalog/<product_id>/boards/<board_id>/revisions/<revision_id>",            view_func=delete_board_revision,  methods=["DELETE"])

    # Catalog - Firmware Builds
    v2.add_url_rule("/catalog/<product_id>/firmware-builds",                                      view_func=list_firmware_builds,   methods=["GET"])
    v2.add_url_rule("/catalog/<product_id>/firmware-builds/upload",                               view_func=upload_firmware_build,  methods=["POST"])
    v2.add_url_rule("/catalog/<product_id>/firmware-builds/<build_id>",                           view_func=update_firmware_build,  methods=["PUT"])
    v2.add_url_rule("/catalog/<product_id>/firmware-builds/<build_id>",                           view_func=delete_firmware_build,  methods=["DELETE"])
    v2.add_url_rule("/catalog/firmware-builds/<build_id>/download",                               view_func=download_firmware_build, methods=["GET"])

    # Admin - History
    v2.add_url_rule("/admin/history",              view_func=list_history,      methods=["GET"])
    v2.add_url_rule("/admin/history/<entry_id>",   view_func=get_history_entry, methods=["GET"])

    # Validation
    v2.add_url_rule("/validation/tests/run", view_func=run_tests,       methods=["POST"])

    # Dashboard
    v2.add_url_rule("/dashboard/overview",                           endpoint="dashboard_overview",          view_func=dashboard_overview,         methods=["GET"])

    # Deployments (managed MTIB deployments)
    v2.add_url_rule("/deployments",                                 endpoint="list_managed_deployments",    view_func=list_managed_deployments,   methods=["GET"])
    v2.add_url_rule("/deployments",                                 endpoint="create_managed_deployment",   view_func=create_deployment,          methods=["POST"])
    v2.add_url_rule("/deployments/<deployment_id>",                 endpoint="get_managed_deployment",      view_func=get_deployment,             methods=["GET"])
    v2.add_url_rule("/deployments/<deployment_id>",                 endpoint="delete_managed_deployment",   view_func=delete_deployment,          methods=["DELETE"])
    v2.add_url_rule("/deployments/<deployment_id>/deploy",          endpoint="deploy_managed_fixture",      view_func=deploy_fixture,             methods=["POST"])
    v2.add_url_rule("/deployments/<deployment_id>/stop",            endpoint="stop_managed_deployment",     view_func=stop_deployment,            methods=["POST"])
    v2.add_url_rule("/deployments/<deployment_id>/restart",         endpoint="restart_managed_deployment",  view_func=restart_managed_deployment, methods=["POST"])
    v2.add_url_rule("/deployments/<deployment_id>/status",          endpoint="get_managed_deployment_status", view_func=get_deployment_status,    methods=["GET"])

    # MTIBs (managed MTIB test bench nodes)
    v2.add_url_rule("/mtibs",                                            endpoint="list_managed_mtibs",      view_func=list_managed_nodes,   methods=["GET"])
    v2.add_url_rule("/mtibs",                                            endpoint="create_managed_mtib",     view_func=create_node,          methods=["POST"])
    v2.add_url_rule("/mtibs/discover",                                   endpoint="discover_managed_mtibs",  view_func=sync_nodes_from_k8s,  methods=["POST"])
    v2.add_url_rule("/mtibs/<node_id>",                                  endpoint="get_managed_mtib",        view_func=get_managed_node,     methods=["GET"])
    v2.add_url_rule("/mtibs/<node_id>",                                  endpoint="update_managed_mtib",     view_func=update_node,          methods=["PUT"])
    v2.add_url_rule("/mtibs/<node_id>",                                  endpoint="delete_managed_mtib",     view_func=delete_node,          methods=["DELETE"])
    v2.add_url_rule("/mtibs/<node_id>/health",                           endpoint="check_managed_mtib_health", view_func=check_node_health,  methods=["POST"])
    v2.add_url_rule("/mtibs/<node_id>/register",                         endpoint="register_managed_mtib",   view_func=register_node,        methods=["POST"])
    v2.add_url_rule("/mtibs/<node_id>/deploy",                           endpoint="deploy_managed_mtib",     view_func=deploy_node,          methods=["POST"])
    v2.add_url_rule("/mtibs/<node_id>/undeploy",                         endpoint="undeploy_managed_mtib",   view_func=undeploy_node,        methods=["POST"])

    # MTIBs - Observability
    v2.add_url_rule("/mtibs/observability",                                  endpoint="fleet_observability",        view_func=get_fleet_observability,   methods=["GET"])
    v2.add_url_rule("/mtibs/<node_id>/observability",                        endpoint="node_observability",         view_func=get_node_observability,    methods=["GET"])
    v2.add_url_rule("/mtibs/<node_id>/observability/power",                  endpoint="node_observability_power",   view_func=get_node_power,            methods=["GET"])
    v2.add_url_rule("/mtibs/<node_id>/observability/gpio",                   endpoint="node_observability_gpio",    view_func=get_node_gpio,             methods=["GET"])
    v2.add_url_rule("/mtibs/<node_id>/observability/uart",                   endpoint="node_observability_uart",    view_func=get_node_uart,             methods=["GET"])
    v2.add_url_rule("/mtibs/<node_id>/observability/system",                 endpoint="node_observability_system",  view_func=get_node_system,           methods=["GET"])

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

    # Kubernetes: Cluster
    v2.add_url_rule("/kubernetes/cluster",              view_func=get_cluster,     methods=["GET"])
    v2.add_url_rule("/kubernetes/namespaces",            view_func=get_namespaces,  methods=["GET"])
    v2.add_url_rule("/kubernetes/nodes",                 view_func=list_system_nodes,      methods=["GET"])
    v2.add_url_rule("/kubernetes/nodes/<node_name>",     view_func=get_system_node,        methods=["GET"])
    v2.add_url_rule("/kubernetes/events",                view_func=get_events,      methods=["GET"])

    # Kubernetes: Resources
    v2.add_url_rule("/kubernetes/pods",                                      view_func=list_pods,          methods=["GET"])
    v2.add_url_rule("/kubernetes/pods/<namespace>/<name>",                   view_func=get_pod,            methods=["GET"])
    v2.add_url_rule("/kubernetes/pods/<namespace>/<name>",                   view_func=delete_pod,         methods=["DELETE"])

    v2.add_url_rule("/kubernetes/deployments",                               view_func=list_system_deployments,   methods=["GET"])
    v2.add_url_rule("/kubernetes/deployments/<namespace>/<name>",            view_func=get_system_deployment,     methods=["GET"])
    v2.add_url_rule("/kubernetes/deployments/<namespace>/<name>/scale",      view_func=scale_deployment,   methods=["POST"])
    v2.add_url_rule("/kubernetes/deployments/<namespace>/<name>/restart",    view_func=restart_system_deployment, methods=["POST"])

    v2.add_url_rule("/kubernetes/services",                                  view_func=list_services,      methods=["GET"])
    v2.add_url_rule("/kubernetes/services/<namespace>/<name>",               view_func=get_service,        methods=["GET"])

    v2.add_url_rule("/kubernetes/jobs",                                      view_func=list_jobs,          methods=["GET"])
    v2.add_url_rule("/kubernetes/jobs/<namespace>/<name>",                   view_func=get_job,            methods=["GET"])
    v2.add_url_rule("/kubernetes/jobs/<namespace>/<name>",                   view_func=delete_job,         methods=["DELETE"])

    v2.add_url_rule("/kubernetes/configmaps",                                view_func=list_configmaps,    methods=["GET"])
    v2.add_url_rule("/kubernetes/configmaps/<namespace>/<name>",             view_func=get_configmap,      methods=["GET"])
    v2.add_url_rule("/kubernetes/secrets",                                   view_func=list_secrets,       methods=["GET"])
    v2.add_url_rule("/kubernetes/secrets/<namespace>/<name>",                view_func=get_secret,         methods=["GET"])

    # Health
    v2.add_url_rule("/healthcheck",          view_func=healthcheck,     methods=["GET"])

    # Docs
    v2.add_url_rule("/openapi.json",         view_func=openapi_spec,    methods=["GET"])
    v2.add_url_rule("/docs",                 view_func=swagger_ui,      methods=["GET"])

    # Kubernetes: Resource YAML
    v2.add_url_rule("/kubernetes/resources/<kind>/<namespace>/<name>",       view_func=get_resource_yaml,       methods=["GET"])
    v2.add_url_rule("/kubernetes/resources/<kind>/<namespace>/<name>",       view_func=apply_resource_yaml,     methods=["PUT"])
    v2.add_url_rule("/kubernetes/resources/<kind>/<namespace>/<name>",       view_func=delete_resource,         methods=["DELETE"])

    # Kubernetes: RBAC
    v2.add_url_rule("/kubernetes/rbac/roles",                               view_func=list_roles,              methods=["GET"])
    v2.add_url_rule("/kubernetes/rbac/clusterroles",                        view_func=list_cluster_roles,      methods=["GET"])
    v2.add_url_rule("/kubernetes/rbac/bindings",                            view_func=list_role_bindings,      methods=["GET"])
    v2.add_url_rule("/kubernetes/rbac/clusterrolebindings",                 view_func=list_cluster_role_bindings, methods=["GET"])
    v2.add_url_rule("/kubernetes/rbac/serviceaccounts",                     view_func=list_service_accounts,   methods=["GET"])

    # Kubernetes: Log Streaming + Pod Exec
    register_log_handlers(socketio)
    register_exec_handlers(socketio)
    register_uart_handlers(socketio)

    server.register_blueprint(v2)
