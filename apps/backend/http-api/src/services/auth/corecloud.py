"""
Core Cloud authentication service.

Authenticates users against the CoreKinect Core Cloud auth server
at AUTH_SERVER_URL using email/password credentials.

The Core Cloud server uses Basic Auth (base64(email:password)) with
an X-API-KEY header, and returns a token response.

We don't store or forward the Core Cloud token — we only use it to
verify the user's identity, then issue our own Concord JWT.
"""

import base64
import logging
from typing import Optional, Tuple

import requests

from config import env_config

logger = logging.getLogger(__name__)


def authenticate_corecloud(email: str, password: str) -> Tuple[Optional[dict], Optional[str]]:
    """
    Authenticate a user against the Core Cloud auth server.

    Returns:
        (user_info, None) on success — user_info contains {"email": str, "name": str, "role": str}
        (None, error_message) on failure
    """
    # SECURITY: All authentication must go through Core Cloud auth server.
    # To disable auth for development, set AUTH_ENABLED=false in environment.
    auth_url = getattr(env_config, "AUTH_SERVER_URL", "")
    api_key = getattr(env_config, "AUTH_SERVER_API_KEY", "")

    if not auth_url:
        return None, "Core Cloud auth server not configured"

    # Build the token request URL
    token_url = f"{auth_url.rstrip('/')}/Authentication/Tokens/Request"

    # Basic auth header: base64(email:password)
    credentials = f"{email}:{password}"
    basic_auth = base64.b64encode(credentials.encode("utf-8")).decode("ascii")

    headers = {
        "Authorization": f"Basic {basic_auth}",
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json",
    }
    if api_key:
        headers["X-API-KEY"] = api_key

    body = {"grant_type": "password"}

    try:
        resp = requests.post(token_url, headers=headers, data=body, timeout=10, verify=True)
    except requests.exceptions.ConnectionError:
        logger.error("Core Cloud auth server unreachable: %s", token_url)
        return None, "Auth server unreachable"
    except requests.exceptions.Timeout:
        logger.error("Core Cloud auth server timed out: %s", token_url)
        return None, "Auth server timed out"
    except Exception as e:
        logger.error("Core Cloud auth request failed: %s", e)
        return None, "Auth server error"

    if resp.status_code == 401:
        return None, "Invalid email or password"

    if resp.status_code != 200:
        logger.warning(
            "Core Cloud auth returned %d: %s", resp.status_code, resp.text[:200]
        )
        return None, f"Auth server error ({resp.status_code})"

    try:
        data = resp.json()
    except ValueError:
        return None, "Invalid response from auth server"

    # Verify we got a token (confirms the credentials are valid)
    token = (
        data.get("accessToken")
        or data.get("access_token")
        or data.get("token")
        or data.get("id_token")
        or data.get("jwt")
    )
    if not token:
        return None, "Auth server returned no token"

    # Identity confirmed — return the email as the verified identity.
    return {"email": email, "name": email.split("@")[0], "role": "user"}, None
