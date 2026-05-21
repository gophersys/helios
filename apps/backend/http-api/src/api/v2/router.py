"""V2 API router — composes per-domain route registrations into a single Blueprint."""

import logging
import re

from corekinect.utils import Logger
from flask import Blueprint, Flask
from flask_socketio import SocketIO

from .auth.routes import register_auth_routes
from .products.routes import register_product_routes
from .builds.routes import register_build_routes
from .runs.routes import register_run_routes
from .fixtures.routes import register_fixture_routes
from .fixture_claims.routes import register_fixture_claim_routes
from .devices.routes import register_device_routes
from .kubernetes.routes import register_kubernetes_routes
from .system.routes import register_system_routes
from .assets.routes import register_asset_routes
from .docs import openapi_spec, swagger_ui


class LogFilter(logging.Filter):
    def __init__(self):
        super().__init__()
        self.healthcheck_pattern = re.compile(r"GET /v2/healthcheck HTTP")
        self.accepted_pattern = re.compile(r"\(.*\) accepted \(.*\)")

    def filter(self, record):
        log_message = str(record.msg)
        if self.healthcheck_pattern.search(log_message) or self.accepted_pattern.search(log_message):
            return False
        return True


v2 = Blueprint("v2", __name__, url_prefix="/v2")


def register_v2_routes(logger: Logger, server: Flask, socketio: SocketIO):
    """Register all v2 API routes, WebSocket handlers, and log filters."""
    logger.add_filter(LogFilter())

    register_auth_routes(v2)
    register_product_routes(v2)
    register_build_routes(v2, socketio)
    register_run_routes(v2, socketio)
    register_fixture_routes(v2)
    register_fixture_claim_routes(v2)
    register_device_routes(v2, socketio)
    register_kubernetes_routes(v2)
    register_system_routes(v2, socketio)
    register_asset_routes(v2)

    # Docs
    v2.add_url_rule("/openapi.json",         view_func=openapi_spec,    methods=["GET"])
    v2.add_url_rule("/docs",                 view_func=swagger_ui,      methods=["GET"])

    server.register_blueprint(v2)
