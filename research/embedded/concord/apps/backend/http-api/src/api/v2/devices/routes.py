"""Route registration for /v2/devices endpoints (MTIBs + ICLE)."""

from flask import Blueprint
from flask_socketio import SocketIO

from ..nodes.nodes import (
    list_nodes as list_managed_nodes,
    create_node,
    sync_nodes_from_k8s,
    get_node as get_managed_node,
    update_node,
    delete_node,
    check_node_health,
    register_node,
)
from ..system.mtib_observability import (
    get_fleet_observability,
    get_node_observability,
    get_node_power,
    get_node_gpio,
    get_node_uart,
    get_node_system,
)
from ..system.observability_ws import register_icle_handlers
from ..icle.heartbeat import heartbeat as icle_heartbeat, set_socketio as set_icle_socketio
from ..icle.devices import (
    list_devices as list_icle_devices,
    get_device as get_icle_device,
    update_device as update_icle_device,
    delete_device as delete_icle_device,
)
from ..icle.commands import acknowledge_command as ack_icle_command
from ..icle.config import push_config as push_icle_config
from ..icle.ota import trigger_ota as trigger_icle_ota
from ..icle.logs import list_device_logs as list_icle_logs, upload_device_log as upload_icle_log


def register_device_routes(api: Blueprint, socketio: SocketIO):
    # MTIBs
    api.add_url_rule("/devices/mtibs",                                            endpoint="list_managed_mtibs",      view_func=list_managed_nodes,   methods=["GET"])
    api.add_url_rule("/devices/mtibs",                                            endpoint="create_managed_mtib",     view_func=create_node,          methods=["POST"])
    api.add_url_rule("/devices/mtibs/discover",                                   endpoint="discover_managed_mtibs",  view_func=sync_nodes_from_k8s,  methods=["POST"])
    api.add_url_rule("/devices/mtibs/<node_id>",                                  endpoint="get_managed_mtib",        view_func=get_managed_node,     methods=["GET"])
    api.add_url_rule("/devices/mtibs/<node_id>",                                  endpoint="update_managed_mtib",     view_func=update_node,          methods=["PUT"])
    api.add_url_rule("/devices/mtibs/<node_id>",                                  endpoint="delete_managed_mtib",     view_func=delete_node,          methods=["DELETE"])
    api.add_url_rule("/devices/mtibs/<node_id>/health",                           endpoint="check_managed_mtib_health", view_func=check_node_health,  methods=["POST"])
    api.add_url_rule("/devices/mtibs/<node_id>/register",                         endpoint="register_managed_mtib",   view_func=register_node,        methods=["POST"])

    # MTIB Observability
    api.add_url_rule("/devices/mtibs/observability",                                  endpoint="fleet_observability",        view_func=get_fleet_observability,   methods=["GET"])
    api.add_url_rule("/devices/mtibs/<node_id>/observability",                        endpoint="node_observability",         view_func=get_node_observability,    methods=["GET"])
    api.add_url_rule("/devices/mtibs/<node_id>/observability/power",                  endpoint="node_observability_power",   view_func=get_node_power,            methods=["GET"])
    api.add_url_rule("/devices/mtibs/<node_id>/observability/gpio",                   endpoint="node_observability_gpio",    view_func=get_node_gpio,             methods=["GET"])
    api.add_url_rule("/devices/mtibs/<node_id>/observability/uart",                   endpoint="node_observability_uart",    view_func=get_node_uart,             methods=["GET"])
    api.add_url_rule("/devices/mtibs/<node_id>/observability/system",                 endpoint="node_observability_system",  view_func=get_node_system,           methods=["GET"])

    # ICLE
    api.add_url_rule("/devices/icle/heartbeat",                              endpoint="icle_heartbeat",           view_func=icle_heartbeat,       methods=["POST"])
    api.add_url_rule("/devices/icle",                                        endpoint="list_icle_devices",        view_func=list_icle_devices,    methods=["GET"])
    api.add_url_rule("/devices/icle/<device_id>",                            endpoint="get_icle_device",          view_func=get_icle_device,      methods=["GET"])
    api.add_url_rule("/devices/icle/<device_id>",                            endpoint="update_icle_device",       view_func=update_icle_device,   methods=["PUT"])
    api.add_url_rule("/devices/icle/<device_id>",                            endpoint="delete_icle_device",       view_func=delete_icle_device,   methods=["DELETE"])
    api.add_url_rule("/devices/icle/<device_id>/config",                     endpoint="push_icle_config",         view_func=push_icle_config,     methods=["PUT"])
    api.add_url_rule("/devices/icle/<device_id>/ota",                        endpoint="trigger_icle_ota",         view_func=trigger_icle_ota,     methods=["POST"])
    api.add_url_rule("/devices/icle/<device_id>/logs",                       endpoint="list_icle_logs",           view_func=list_icle_logs,       methods=["GET"])
    api.add_url_rule("/devices/icle/<device_id>/logs",                       endpoint="upload_icle_log",          view_func=upload_icle_log,      methods=["POST"])
    api.add_url_rule("/devices/icle/commands/<command_id>/ack",              endpoint="ack_icle_command",         view_func=ack_icle_command,     methods=["POST"])

    register_icle_handlers(socketio)
    set_icle_socketio(socketio)
