"""
Core Cloud authentication service.

Authenticates users against the CoreKinect Core Cloud auth server
at AUTH_SERVER_URL using email/password credentials.

The Core Cloud server uses Basic Auth (base64(email:password)) with
an X-API-KEY header, and returns a token response.

We don't store or forward the Core Cloud token — we only use it to
verify the user's identity, then issue our own Concord JWT.

##########################################################################
# TODO (MONDAY): Remove DEV_USERS bypass once real Core Cloud credentials
# are provisioned. Ask your engineer to add your account to the Core Cloud
# auth server, then delete the DEV_USERS dict and the _check_dev_users()
# function. The real authenticate_corecloud() flow is already implemented
# and tested — it just needs valid server credentials.
#
# Steps:
#   1. Get added to Core Cloud auth server (ask engineer)
#   2. Delete DEV_USERS dict below
#   3. Delete _check_dev_users() function
#   4. Remove the dev-user check at top of authenticate_corecloud()
#   5. Set AUTH_ENABLED=true in staging + production Helm values
#   6. Redeploy
##########################################################################
"""

import base64
import logging
from typing import Optional, Tuple

import requests

from config import env_config

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# TODO: REMOVE THIS ENTIRE BLOCK ON MONDAY — dev/test accounts only
# ---------------------------------------------------------------------------
DEV_USERS = {
    "admin": {
        "password": "admin",
        "name": "Admin User",
        "role": "superadmin",
    },
    "mateo@concord.local": {
        "password": "admin",
        "name": "Mateo Segura",
        "role": "superadmin",
    },
    "admin@concord.local": {
        "password": "admin",
        "name": "Admin User",
        "role": "admin",
    },
    "operator@concord.local": {
        "password": "operator",
        "name": "Operator User",
        "role": "operator",
    },
}


def _check_dev_users(email: str, password: str) -> Tuple[Optional[dict], Optional[str]]:
    """Check hardcoded dev users. TODO: REMOVE ON MONDAY."""
    user = DEV_USERS.get(email)
    if not user:
        return None, None  # Not a dev user — fall through to real auth
    if user["password"] != password:
        return None, "Invalid email or password"
    return {"email": email, "name": user["name"], "role": user["role"]}, None
# ---------------------------------------------------------------------------


def authenticate_corecloud(email: str, password: str) -> Tuple[Optional[dict], Optional[str]]:
    """
    Authenticate a user against the Core Cloud auth server.

    Returns:
        (user_info, None) on success — user_info contains {"email": str, "name": str, "role": str}
        (None, error_message) on failure
    """
    # TODO: REMOVE this dev-user check on Monday
    dev_result, dev_error = _check_dev_users(email, password)
    if dev_result is not None:
        return dev_result, None
    if dev_error is not None:
        return None, dev_error

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
