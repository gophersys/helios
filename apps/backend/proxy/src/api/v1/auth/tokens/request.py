# Standard includes
import logging

# 3rd party includes
from flask import Blueprint, request, jsonify, current_app
import requests

# Corekinect includes
from corekinect.utils import Logger

# App includes
from src.server import ProxyEnvConfig


tokens_request_bp = Blueprint("token_request", __name__)


@tokens_request_bp.route("/v1/auth/tokens/request", methods=["POST"])
def auth_tokens_request_handler():
    # Get global server objects
    log: Logger = current_app.config.get("logger", None)
    env_config: ProxyEnvConfig = current_app.config.get("env_config", None)

    try:
        # Extract Basic Auth credentials from the headers
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Basic "):
            return jsonify({"error": "Invalid or missing Authorization header"}), 401

        base64_credentials = auth_header.split(" ", 1)[1]
        log.debug(f"Received Basic Auth credentials: {base64_credentials}")

        # Prepare headers for the auth server request
        headers = {"X-API-KEY": env_config.AUTH_SERVER_API_KEY, "Authorization": f"Basic {base64_credentials}"}

        # Prepare the request body
        body = {"grant_type": "password"}

        # Make the request to the auth server
        auth_server_url = f"{env_config.AUTH_SERVER_URL}/Authentication/Tokens/Request"
        log.debug(f"Sending request to auth server at {auth_server_url} with headers: {headers} and body: {body}")

        response = requests.post(auth_server_url, headers=headers, data=body)

        # Handle the response from the auth server
        return response.text, response.status_code

    except Exception as e:
        log.error(f"An error occurred: {str(e)}")
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500
