from flask import Flask

from .health.handler import health_bp
from .auth.register import auth_routes_register


def api_v1_register(api: Flask):
    api.register_blueprint(health_bp)

    # Groups
    auth_routes_register(api)
