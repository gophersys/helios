from flask import Flask

from .steps.get.handler import test_step_get_bp


def tests_register(api: Flask):

    api.register_blueprint(test_step_get_bp)  # GET "/v1/tests/steps"
