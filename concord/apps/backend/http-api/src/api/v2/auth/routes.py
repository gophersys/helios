"""Route registration for /v2/auth, /v2/users, /v2/permissions, /v2/api-keys endpoints."""

from flask import Blueprint

from .api_keys import create_api_key, delete_api_key, list_api_keys
from .dev_login import dev_login, dev_users
from .login import login
from .me import me
from .session import (
    approve_session,
    poll_session,
    refresh_session,
    request_session_code,
    revoke_session,
    verify_session_code,
)
from .permission_sets import (
    create_permission_set,
    delete_permission_set,
    list_permission_sets,
    update_permission_set,
)
from .permissions_list import list_permissions
from .users import (
    users_create,
    users_delete,
    users_get_product_access,
    users_list,
    users_set_product_access,
    users_set_role,
    users_update,
)


def register_auth_routes(api: Blueprint):
    api.add_url_rule("/auth/login",           view_func=login,          methods=["POST"])
    api.add_url_rule("/auth/me",              view_func=me,             methods=["GET"])

    api.add_url_rule("/auth/dev-users",       view_func=dev_users,      methods=["GET"])
    api.add_url_rule("/auth/dev-login",       view_func=dev_login,      methods=["POST"])

    api.add_url_rule("/auth/session/code",     view_func=request_session_code, methods=["POST"])
    api.add_url_rule("/auth/session/poll",     view_func=poll_session,         methods=["POST"])
    api.add_url_rule("/auth/session/verify",   view_func=verify_session_code,  methods=["GET"])
    api.add_url_rule("/auth/session/approve",  view_func=approve_session,      methods=["POST"])
    api.add_url_rule("/auth/session/refresh",  view_func=refresh_session,      methods=["POST"])
    api.add_url_rule("/auth/session/revoke",   view_func=revoke_session,       methods=["POST"])

    api.add_url_rule("/users",           view_func=users_list,     methods=["GET"])
    api.add_url_rule("/users",           view_func=users_create,   methods=["POST"])
    api.add_url_rule("/users/<user_id>", view_func=users_update,   methods=["PUT"])
    api.add_url_rule("/users/<user_id>", view_func=users_delete,   methods=["DELETE"])
    api.add_url_rule("/users/<user_id>/role",           view_func=users_set_role,            methods=["PUT"])
    api.add_url_rule("/users/<user_id>/product-access", view_func=users_get_product_access, methods=["GET"])
    api.add_url_rule("/users/<user_id>/product-access", view_func=users_set_product_access, methods=["PUT"])

    api.add_url_rule("/permissions",          view_func=list_permission_sets,   methods=["GET"])
    api.add_url_rule("/permissions",          view_func=create_permission_set,  methods=["POST"])
    api.add_url_rule("/permissions/<set_id>", view_func=update_permission_set,  methods=["PUT"])
    api.add_url_rule("/permissions/<set_id>", view_func=delete_permission_set,  methods=["DELETE"])
    api.add_url_rule("/permissions/available", view_func=list_permissions,      methods=["GET"])

    api.add_url_rule("/api-keys",          view_func=list_api_keys,   methods=["GET"])
    api.add_url_rule("/api-keys",          view_func=create_api_key,  methods=["POST"])
    api.add_url_rule("/api-keys/<key_id>", view_func=delete_api_key,  methods=["DELETE"])
