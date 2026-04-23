"""Persistent corectl configuration.

Stored at ``~/.corectl/config.yaml``. Holds the active CLI session — an
access token (15-min) plus a refresh token (30-day rotated) — and the
backend URL. Service-account API keys (CI/build servers) are passed via
flag/env and never written here.

URL precedence (Bitwarden style):
    1. ``$CONCORD_API_URL``
    2. ``api_url`` in the saved config
    3. Hardcoded production: ``https://concord.ad.corekinect.com``

The legacy ``api_token`` field is gone — corectl has not had a formal
release yet, so we keep one shape and one shape only.
"""

import os
from pathlib import Path
from typing import Any, Dict, Optional


CONFIG_DIR = Path.home() / ".corectl"
CONFIG_FILE = CONFIG_DIR / "config.yaml"
DEFAULT_API_URL = "https://concord.ad.corekinect.com"


def load_config() -> Dict[str, Any]:
    """Load config from ``~/.corectl/config.yaml``. Empty dict if missing."""
    if not CONFIG_FILE.exists():
        return {}
    import yaml
    with open(CONFIG_FILE) as f:
        return yaml.safe_load(f) or {}


def save_config(config: Dict[str, Any]) -> None:
    """Persist config to ``~/.corectl/config.yaml``.

    Creates the directory + file with restrictive perms — the file holds a
    long-lived refresh token, so other users on the box must not read it.
    """
    import yaml
    CONFIG_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)
    with open(CONFIG_FILE, "w") as f:
        yaml.dump(config, f, default_flow_style=False)
    try:
        os.chmod(CONFIG_FILE, 0o600)
    except OSError:
        # Filesystem may not support chmod (Windows, network mounts).
        pass


def get_api_url(config: Dict[str, Any]) -> str:
    """Resolve the Concord API base URL.

    Order: ``$CONCORD_API_URL`` env → ``api_url`` in config → production default.
    """
    return (
        os.environ.get("CONCORD_API_URL")
        or config.get("api_url")
        or DEFAULT_API_URL
    )


def get_tls_verify(config: Dict[str, Any]) -> bool:
    """Whether HTTPS certificates should be verified. Defaults to True."""
    return config.get("tls_verify", True)


def get_service_account_key(config: Dict[str, Any]) -> Optional[str]:
    """Return a service-account API key from the environment, if set.

    Service accounts are explicitly **never** written to the config file —
    they are CI/runner credentials and only flow through env vars or a
    one-shot ``--service-account`` flag.
    """
    return os.environ.get("CONCORD_API_KEY") or None


def get_session(config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Return the saved CLI session dict, or None if not logged in.

    Shape:
        {
            "access_token": "<jwt>",
            "refresh_token": "<opaque>",
            "expires_at":    "2026-04-20T12:34:56+00:00",
            "user_email":    "alice@example.com",
        }
    """
    if not config.get("access_token") or not config.get("refresh_token"):
        return None
    return {
        "access_token": config["access_token"],
        "refresh_token": config["refresh_token"],
        "expires_at": config.get("expires_at"),
        "user_email": config.get("user_email"),
    }


def store_session(
    config: Dict[str, Any],
    *,
    access_token: str,
    refresh_token: str,
    expires_at: str,
    user_email: Optional[str] = None,
) -> Dict[str, Any]:
    """Merge a fresh session into ``config`` (in place) and persist it.

    Returns the updated config so callers can chain the result.
    """
    config["access_token"] = access_token
    config["refresh_token"] = refresh_token
    config["expires_at"] = expires_at
    if user_email is not None:
        config["user_email"] = user_email
    save_config(config)
    return config


def clear_session(config: Dict[str, Any]) -> Dict[str, Any]:
    """Drop the saved session fields and persist. Used on ``corectl auth logout``."""
    for k in ("access_token", "refresh_token", "expires_at", "user_email"):
        config.pop(k, None)
    save_config(config)
    return config
