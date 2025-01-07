from flask import Flask

from .health.handler import health_bp
from .catalog.register import catalog_register
from .tests.register import tests_register


def api_v2_register(api: Flask):
    api.register_blueprint(health_bp)

    # Groups
    catalog_register(api)
    tests_register(api)
