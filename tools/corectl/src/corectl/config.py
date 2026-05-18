"""Persistent corectl configuration.

Stored at ``~/.corectl/config.yaml``. Holds the active CLI session — an
access token (15-min) plus a refresh token (30-day rotated) — and the
backend URL. Service-account API keys (CI/build servers) are passed via
flag/env and never written here.

URL precedence (env first):
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


_SYSTEM_CA_BUNDLE_PATHS = (
    "/etc/ssl/certs/ca-certificates.crt",   # Debian, Ubuntu, Alpine
    "/etc/pki/tls/certs/ca-bundle.crt",     # RHEL, Fedora, CentOS
    "/etc/pki/ca-trust/extracted/pem/tls-ca-bundle.pem",  # newer RHEL
    "/etc/ssl/cert.pem",                    # macOS Homebrew, Alpine
)


def _system_ca_bundle() -> Optional[str]:
    """Return the OS-managed CA bundle path, or None if no known one exists.

    Python's ``requests`` library defaults to certifi's bundled CA list,
    which does NOT include corporate internal CAs even when those CAs
    are properly installed in the OS trust store. This is the classic
    "openssl s_client says OK but Python says SSLCertVerificationError"
    Linux gotcha. Auto-detecting the system bundle makes corectl Just
    Work on any host that has the corekinect CA in its OS trust store
    (the common case — corp Mac, corp Linux, WSL with update-ca-certs).
    """
    for path in _SYSTEM_CA_BUNDLE_PATHS:
        if os.path.isfile(path):
            return path
    return None


def get_tls_verify(config: Dict[str, Any]):
    """Resolve the TLS verification setting for HTTPS calls.

    Returns one of:

    * ``True`` — use Python's default (certifi's bundled Mozilla CA list).
    * ``False`` — skip verification entirely (insecure escape hatch).
    * ``str`` — path to a CA bundle to verify against. The OS-managed
      bundle is auto-detected, so machines with the corekinect CA in
      their system trust store succeed without any user action.

    Resolution order (most specific wins):

    1. ``CONCORD_VERIFY_SSL`` env var (``"0"``, ``"false"``, ``"no"``,
       ``"off"`` → ``False``; anything else → ``True``-ish path/bool).
    2. ``tls_verify`` field in the saved config (persisted opt-out).
    3. ``REQUESTS_CA_BUNDLE`` env var (standard ``requests`` knob).
    4. Auto-detected system CA bundle path, if one exists.
    5. Fallback to ``True`` (certifi's default).
    """
    env_val = os.environ.get("CONCORD_VERIFY_SSL")
    if env_val is not None:
        if env_val.strip().lower() in ("0", "false", "no", "off"):
            return False
        # Anything else means "verify" — fall through to auto-detection.

    cfg_val = config.get("tls_verify")
    if cfg_val is False:
        return False
    if isinstance(cfg_val, str) and cfg_val:
        return cfg_val

    # ``REQUESTS_CA_BUNDLE`` is the standard env var ``requests`` already
    # honors automatically; we surface it here so the resolved value is
    # explicit and visible in logs.
    requests_bundle = os.environ.get("REQUESTS_CA_BUNDLE")
    if requests_bundle and os.path.isfile(requests_bundle):
        return requests_bundle

    system_bundle = _system_ca_bundle()
    if system_bundle is not None:
        return system_bundle

    return True


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
