"""Route registration for /v2/kubernetes endpoints."""

from flask import Blueprint

from .cluster import get_cluster, get_namespaces
from .nodes import list_nodes, get_node
from .events import get_events
from .pods import list_pods, get_pod, get_pod_logs, delete_pod
from .deployments import list_deployments, get_deployment, scale_deployment, restart_deployment
from .services_api import list_services, get_service
from .jobs import list_jobs, get_job, delete_job
from .config import list_configmaps, get_configmap, list_secrets, get_secret
from .resources import get_resource_yaml, apply_resource_yaml, delete_resource
from .rbac import (
    list_roles, list_cluster_roles, list_role_bindings,
    list_cluster_role_bindings, list_service_accounts,
)


def register_kubernetes_routes(api: Blueprint):
    api.add_url_rule("/kubernetes/info",                    view_func=get_cluster,     methods=["GET"])
    api.add_url_rule("/kubernetes/namespaces",              view_func=get_namespaces,  methods=["GET"])
    api.add_url_rule("/kubernetes/nodes",                   view_func=list_nodes,      methods=["GET"])
    api.add_url_rule("/kubernetes/nodes/<node_name>",       view_func=get_node,        methods=["GET"])
    api.add_url_rule("/kubernetes/events",                  view_func=get_events,      methods=["GET"])

    api.add_url_rule("/kubernetes/pods",                                      view_func=list_pods,          methods=["GET"])
    api.add_url_rule("/kubernetes/pods/<namespace>/<name>",                   view_func=get_pod,            methods=["GET"])
    api.add_url_rule("/kubernetes/pods/<namespace>/<name>/logs",              view_func=get_pod_logs,       methods=["GET"])
    api.add_url_rule("/kubernetes/pods/<namespace>/<name>",                   view_func=delete_pod,         methods=["DELETE"])

    api.add_url_rule("/kubernetes/deployments",                               view_func=list_deployments,   methods=["GET"])
    api.add_url_rule("/kubernetes/deployments/<namespace>/<name>",            view_func=get_deployment,     methods=["GET"])
    api.add_url_rule("/kubernetes/deployments/<namespace>/<name>/scale",      view_func=scale_deployment,   methods=["POST"])
    api.add_url_rule("/kubernetes/deployments/<namespace>/<name>/restart",    view_func=restart_deployment, methods=["POST"])

    api.add_url_rule("/kubernetes/services",                                  view_func=list_services,      methods=["GET"])
    api.add_url_rule("/kubernetes/services/<namespace>/<name>",               view_func=get_service,        methods=["GET"])

    api.add_url_rule("/kubernetes/jobs",                                      view_func=list_jobs,          methods=["GET"])
    api.add_url_rule("/kubernetes/jobs/<namespace>/<name>",                   view_func=get_job,            methods=["GET"])
    api.add_url_rule("/kubernetes/jobs/<namespace>/<name>",                   view_func=delete_job,         methods=["DELETE"])

    api.add_url_rule("/kubernetes/configmaps",                                view_func=list_configmaps,    methods=["GET"])
    api.add_url_rule("/kubernetes/configmaps/<namespace>/<name>",             view_func=get_configmap,      methods=["GET"])
    api.add_url_rule("/kubernetes/secrets",                                   view_func=list_secrets,       methods=["GET"])
    api.add_url_rule("/kubernetes/secrets/<namespace>/<name>",                view_func=get_secret,         methods=["GET"])

    api.add_url_rule("/kubernetes/resources/<kind>/<namespace>/<name>",       view_func=get_resource_yaml,       methods=["GET"])
    api.add_url_rule("/kubernetes/resources/<kind>/<namespace>/<name>",       view_func=apply_resource_yaml,     methods=["PUT"])
    api.add_url_rule("/kubernetes/resources/<kind>/<namespace>/<name>",       view_func=delete_resource,         methods=["DELETE"])

    api.add_url_rule("/kubernetes/rbac/roles",                               view_func=list_roles,              methods=["GET"])
    api.add_url_rule("/kubernetes/rbac/cluster-roles",                       view_func=list_cluster_roles,      methods=["GET"])
    api.add_url_rule("/kubernetes/rbac/role-bindings",                       view_func=list_role_bindings,      methods=["GET"])
    api.add_url_rule("/kubernetes/rbac/cluster-role-bindings",               view_func=list_cluster_role_bindings, methods=["GET"])
    api.add_url_rule("/kubernetes/rbac/service-accounts",                    view_func=list_service_accounts,   methods=["GET"])
