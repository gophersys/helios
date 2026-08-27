"""Route registration for /v2/system and /v2/storage endpoints + WebSocket handlers."""

from flask import Blueprint
from flask_socketio import SocketIO

from .healthcheck import healthcheck
from .info import get_system_info
from .history import get_history_entry, get_entity_history, list_entity_types, list_history
from .logs import register_log_handlers
from .exec import register_exec_handlers
from .observability_ws import register_observability_handlers
from .retention import cleanup_validation_runs, get_validation_storage_usage
from .secrets import (
    list_secrets as list_platform_secrets,
    create_secret as create_platform_secret,
    update_secret as update_platform_secret,
    delete_secret as delete_platform_secret,
)
from .poller_state import list_poller_state, upsert_poller_state, delete_poller_state
from .error_reports import (
    create_error_report,
    list_error_reports,
    get_error_report,
    update_error_report,
    delete_error_report,
)
from .releases import (
    create_release,
    list_releases,
    get_release,
    update_release,
    delete_release,
    link_bugs_to_release,
    unlink_bug_from_release,
)
from .notifications import (
    list_notifications,
    unread_count,
    mark_read,
    mark_all_read,
    broadcast_notification,
    list_notification_types,
    get_notification_preferences,
    update_notification_preferences,
)
from .notifications_ws import register_notification_ws
from .user_reports import list_my_error_reports
from ..assets.storage_download import download_storage_file


def register_system_routes(api: Blueprint, socketio: SocketIO):
    api.add_url_rule("/healthcheck",          view_func=healthcheck,     methods=["GET"])

    api.add_url_rule("/system/info",                 view_func=get_system_info, methods=["GET"])

    api.add_url_rule("/system/history",                                        view_func=list_history,       methods=["GET"])
    api.add_url_rule("/system/history/entity-types",                           view_func=list_entity_types,  methods=["GET"])
    api.add_url_rule("/system/history/<entry_id>",                             view_func=get_history_entry,  methods=["GET"])
    api.add_url_rule("/system/history/entity/<entity_type>/<entity_id>",       view_func=get_entity_history, methods=["GET"])

    api.add_url_rule("/system/retention/validation/cleanup",   endpoint="cleanup_validation_runs",     view_func=cleanup_validation_runs,      methods=["POST"])
    api.add_url_rule("/system/retention/validation/usage",     endpoint="get_validation_storage_usage", view_func=get_validation_storage_usage, methods=["GET"])

    api.add_url_rule("/system/secrets",              endpoint="list_platform_secrets",   view_func=list_platform_secrets,   methods=["GET"])
    api.add_url_rule("/system/secrets",              endpoint="create_platform_secret",  view_func=create_platform_secret,  methods=["POST"])
    api.add_url_rule("/system/secrets/<secret_id>",  endpoint="update_platform_secret",  view_func=update_platform_secret,  methods=["PUT"])
    api.add_url_rule("/system/secrets/<secret_id>",  endpoint="delete_platform_secret",  view_func=delete_platform_secret,  methods=["DELETE"])

    api.add_url_rule("/system/poller-state",  endpoint="list_poller_state",    view_func=list_poller_state,    methods=["GET"])
    api.add_url_rule("/system/poller-state",  endpoint="upsert_poller_state",  view_func=upsert_poller_state,  methods=["PUT"])
    api.add_url_rule("/system/poller-state",  endpoint="delete_poller_state",  view_func=delete_poller_state,  methods=["DELETE"])

    api.add_url_rule("/storage/download",                                      endpoint="download_storage_file",        view_func=download_storage_file,    methods=["GET"])

    # Error reports
    api.add_url_rule("/system/error-reports",              endpoint="create_error_report",  view_func=create_error_report,  methods=["POST"])
    api.add_url_rule("/system/error-reports",              endpoint="list_error_reports",   view_func=list_error_reports,   methods=["GET"])
    api.add_url_rule("/system/error-reports/<report_id>",  endpoint="get_error_report",     view_func=get_error_report,     methods=["GET"])
    api.add_url_rule("/system/error-reports/<report_id>",  endpoint="update_error_report",  view_func=update_error_report,  methods=["PATCH"])
    api.add_url_rule("/system/error-reports/<report_id>",  endpoint="delete_error_report",  view_func=delete_error_report,  methods=["DELETE"])

    # Releases
    api.add_url_rule("/releases",                          endpoint="create_release",       view_func=create_release,       methods=["POST"])
    api.add_url_rule("/releases",                          endpoint="list_releases",        view_func=list_releases,        methods=["GET"])
    api.add_url_rule("/releases/<release_id>",             endpoint="get_release",          view_func=get_release,          methods=["GET"])
    api.add_url_rule("/releases/<release_id>",             endpoint="update_release",       view_func=update_release,       methods=["PATCH"])
    api.add_url_rule("/releases/<release_id>",             endpoint="delete_release",       view_func=delete_release,       methods=["DELETE"])
    api.add_url_rule("/releases/<release_id>/link-bugs",                       endpoint="link_bugs_to_release",     view_func=link_bugs_to_release,     methods=["POST"])
    api.add_url_rule("/releases/<release_id>/resolved-bugs/<report_id>",       endpoint="unlink_bug_from_release",  view_func=unlink_bug_from_release,  methods=["DELETE"])

    # Notifications (user-facing)
    api.add_url_rule("/notifications",                     endpoint="list_notifications",      view_func=list_notifications,      methods=["GET"])
    api.add_url_rule("/notifications/unread-count",        endpoint="unread_count",             view_func=unread_count,            methods=["GET"])
    api.add_url_rule("/notifications/<notification_id>/read", endpoint="mark_read",             view_func=mark_read,               methods=["PATCH"])
    api.add_url_rule("/notifications/read-all",            endpoint="mark_all_read",            view_func=mark_all_read,           methods=["POST"])
    api.add_url_rule("/notifications/broadcast",           endpoint="broadcast_notification",   view_func=broadcast_notification,  methods=["POST"])
    api.add_url_rule("/notifications/types",               endpoint="list_notification_types",  view_func=list_notification_types,  methods=["GET"])
    api.add_url_rule("/notifications/preferences",         endpoint="get_notification_prefs",   view_func=get_notification_preferences,    methods=["GET"])
    api.add_url_rule("/notifications/preferences",         endpoint="update_notification_prefs", view_func=update_notification_preferences, methods=["PUT"])

    # User's own bug reports
    api.add_url_rule("/my/error-reports",                  endpoint="list_my_error_reports",    view_func=list_my_error_reports,   methods=["GET"])

    register_log_handlers(socketio)
    register_exec_handlers(socketio)
    register_observability_handlers(socketio)
    register_notification_ws(socketio)
