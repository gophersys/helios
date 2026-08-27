"""Route registration for /v2/test/* discovery endpoints."""

from flask import Blueprint

from .nodes import list_test_nodes


def register_test_routes(api: Blueprint):
    """Bind the test discovery endpoints to the v2 Blueprint."""
    api.add_url_rule(
        "/test/nodes",
        endpoint="list_test_nodes",
        view_func=list_test_nodes,
        methods=["GET"],
    )
