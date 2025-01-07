from flask import Flask

from .tokens.refresh import token_refresh_bp
from .tokens.request import tokens_request_bp


def auth_routes_register(api: Flask):
    api.register_blueprint(token_refresh_bp)
    api.register_blueprint(tokens_request_bp)
