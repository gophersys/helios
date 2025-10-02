import base64
import requests
import logging
from datetime import datetime, timedelta
from functools import wraps
from typing import Tuple, Optional
from flask import Blueprint, jsonify, request
from dateutil import parser

# Corekinect includes
from corekinect.utils import Logger

LOG_MODULE = "middleware"


class CoreCloudAuthTokenInfo:
    def __init__(
        self, access_token: str, refresh_token: str, token_type: str, issued: str, expires: str, expires_in: int
    ):
        self.access_token: str = access_token
        self.refresh_token: str = refresh_token
        self.token_type: str = token_type
        self.issued: datetime = parser.parse(issued)
        self.expires: datetime = parser.parse(expires)
        self.expires_in: int = expires_in

    def is_expired(self, threshold: timedelta) -> bool:
        return datetime.now(tz=self.expires.tzinfo) >= (self.expires - threshold)


class AuthMiddlewareConfig:
    def __init__(self, cc_auth_server_url: str, server_api_key: str, server_client_id: str, server_client_secret: str):
        self.cc_auth_server_url: str = cc_auth_server_url
        self.server_api_key: str = server_api_key
        self.server_client_id: str = server_client_id
        self.server_client_secret: str = server_client_secret


class AuthMiddleware:
    TOKEN_EXPIRATION_THRESHOLD = timedelta(minutes=5)

    def __init__(self):
        self.config: AuthMiddlewareConfig = None
        self.my_token_info: CoreCloudAuthTokenInfo = None

    def init(self, logger: Logger, auth_enabled: bool, config: AuthMiddlewareConfig) -> str:
        self.config = config
        self.auth_enabled = auth_enabled

        # Logger
        self.logger: Logger = logger
        if self.logger is None:
            self.logger = Logger(
                Logger.Config(
                    logger_name=LOG_MODULE,
                    log_directory="logs",
                    overall_log_level=logging.DEBUG,
                    console_log_level=logging.DEBUG,
                    file_log_level=logging.DEBUG,
                    enable_log_color=True,
                )
            )
        else:
            # Create a child logger from the parent
            self.logger = logger.from_parent(LOG_MODULE)

        if auth_enabled:
            # Do a health check on the auth server make sure it's reachable
            error = self._do_auth_server_health_check()
            if error:
                return f"Could not start middleware layer, error getting a health check on CC Auth Server: {error}"

            # Get a session token for us
            error, _ = self.get_server_token()
            if error:
                return f"Could not get a service token for this server: {error}"
        else:
            self.logger.warning("!!!!!!!!! -> Auth is disabled in server!, proceed with caution <- !!!!!!!!!")

        return ""

    def _do_auth_server_health_check(self) -> str:
        try:
            health_check_url = f"{self.config.cc_auth_server_url}/health/live"
            response = requests.get(health_check_url, verify=None)
            response.raise_for_status()
            return ""
        except requests.RequestException as e:
            return f"Auth server health check failed: {e}"

    def get_server_token(self) -> Tuple[str, Optional[str]]:
        try:
            # Check if the token is about to expire
            if self.my_token_info and not self.my_token_info.is_expired(self.TOKEN_EXPIRATION_THRESHOLD):
                return "", self.my_token_info.access_token

            # Create the base64 encoded credentials
            credentials = f"{self.config.server_client_id}:{self.config.server_client_secret}"
            base64_credentials = base64.b64encode(credentials.encode()).decode("utf-8")

            # Prepare headers for the auth server request
            headers = {"X-API-KEY": self.config.server_api_key, "Authorization": f"Basic {base64_credentials}"}

            # Prepare the request body
            body = {"grant_type": "client_credentials"}

            # Make the request to the auth server
            auth_server_url = f"{self.config.cc_auth_server_url}/Authentication/Tokens/Request"
            response = requests.post(auth_server_url, headers=headers, data=body)

            if response.status_code == 200:
                auth_data = response.json()
                self.my_token_info = CoreCloudAuthTokenInfo(
                    access_token=auth_data.get("accessToken"),
                    refresh_token=auth_data.get("refreshToken"),
                    token_type=auth_data.get("tokenType"),
                    issued=auth_data.get("issued"),
                    expires=auth_data.get("expires"),
                    expires_in=auth_data.get("expiresIn"),
                )
                self.logger.info(f"Succesfully acquired access token for server")
                return "", self.my_token_info.access_token
            else:
                return f"Failed to get server token (status: {response.status_code}): {response.text}", None
        except Exception as e:
            return f"Error getting server token: {e}", None

    def check_permissions(self, required_permissions, requires_privileged_access=False):
        def decorator(f):
            @wraps(f)
            def decorated_function(*args, **kwargs):
                if self.auth_enabled:
                    # Extract the access token from the request headers
                    access_token = request.headers.get("Authorization")
                    if access_token is None or not access_token.startswith("Bearer "):
                        self.logger.debug("No access token provided or invalid format")
                        return jsonify({"error": "Unauthorized"}), 401

                    token_error, server_token = self.get_server_token()
                    if token_error:
                        self.logger.error(f"A server error ocurred whilst getting access token: {token_error}")
                        return jsonify({"error": f"{token_error}"}), 503

                    # Prepare headers for the auth server request
                    headers = {
                        "X-API-KEY": self.config.server_api_key,
                        "Authorization": f"Bearer {server_token}",
                    }

                    # Prepare the request body
                    body = {
                        "apiKey": self.config.server_api_key,
                        "authorizationHeader": access_token,
                        "requiresPrivilegedAccess": requires_privileged_access,
                        "requiredPermissions": required_permissions,
                    }

                    # Hit the auth server to check permissions
                    auth_server_url = f"{self.config.cc_auth_server_url}/Authorization/Validation/ValidatePermissions"
                    self.logger.debug(
                        f"Hitting auth server at {auth_server_url} with headers \n{headers} and body: \n{body}"
                    )

                    try:
                        response = requests.post(auth_server_url, headers=headers, json=body)
                    except Exception as e:
                        self.logger.error(f"Auth server request failed: {e}")
                        return jsonify({"error": "Unauthorized"}), 401

                    self.logger.debug(f"Auth server response status: {response.status_code}")

                    # Handle the response from the auth server
                    if response.status_code == 200:
                        auth_data = response.json()
                        self.logger.debug(f"Auth data: {auth_data}")

                        if not auth_data.get("isAuthorized"):
                            self.logger.debug("Permissions not granted")
                            return jsonify({"error": "Forbidden"}), 403
                    else:
                        self.logger.debug("Unauthorized request")
                        return response.text, response.status_code

                return f(*args, **kwargs)

            return decorated_function

        return decorator


authMiddleware = AuthMiddleware()
