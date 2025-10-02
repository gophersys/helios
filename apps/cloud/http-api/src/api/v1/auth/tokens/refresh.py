# Standard includes
import logging

# 3rd party includes
from flask import Blueprint, request, jsonify
import requests

# App includes
from config import env_config

token_refresh_bp = Blueprint("token_refresh", __name__)


@token_refresh_bp.route("/v1/auth/tokens/refresh", methods=["POST"])
def auth_tokens_refresh_handler():
    try:
        # Extract the refresh token from the request body
        refresh_token = request.json.get("refreshToken")
        if not refresh_token:
            return jsonify({"error": "Bad request, 'refreshToken' field is required."}), 400

        logging.debug(f"Received refresh token: {refresh_token}")

        # Prepare headers for the auth server request
        headers = {"X-API-KEY": env_config.AUTH_SERVER_API_KEY}

        # Prepare the request body
        body = {"refreshToken": refresh_token}

        # Make the request to the auth server
        auth_server_url = f"{env_config.AUTH_SERVER_URL}/Authentication/Tokens/Refresh"
        logging.debug(f"Sending request to auth server at {auth_server_url} with headers: {headers} and body: {body}")

        response = requests.post(auth_server_url, headers=headers, json=body)

        # Handle the response from the auth server
        return response.text, response.status_code

    except Exception as e:
        logging.error(f"An error occurred: {str(e)}")
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500
