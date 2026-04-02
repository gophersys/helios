"""Configuration management for corectl.

Stores auth tokens and API URL in ~/.corectl/config.yaml.
"""

import os
from pathlib import Path
from typing import Any, Dict, Optional

import yaml


CONFIG_DIR = Path.home() / ".corectl"
CONFIG_FILE = CONFIG_DIR / "config.yaml"


def load_config() -> Dict[str, Any]:
    """Load config from ~/.corectl/config.yaml."""
    if not CONFIG_FILE.exists():
        return {}
    with open(CONFIG_FILE) as f:
        return yaml.safe_load(f) or {}


def save_config(config: Dict[str, Any]) -> None:
    """Save config to ~/.corectl/config.yaml."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        yaml.dump(config, f, default_flow_style=False)


def get_api_url(config: Dict[str, Any]) -> str:
    """Get Concord API URL from config or environment."""
    return (
        os.environ.get("CONCORD_API_URL")
        or config.get("api_url")
        or "http://localhost:9001"
    )


def get_api_token(config: Dict[str, Any]) -> Optional[str]:
    """Get auth token from config or environment."""
    return (
        os.environ.get("CONCORD_API_KEY")
        or config.get("api_token")
    )


def get_tls_verify(config: Dict[str, Any]) -> bool:
    """Get TLS verification setting from config."""
    return config.get("tls_verify", True)


def require_auth(config: Dict[str, Any]) -> str:
    """Get auth token or exit with error."""
    token = get_api_token(config)
    if not token:
        import click
        click.echo("Not authenticated. Run: corectl auth login", err=True)
        raise SystemExit(1)
    return token
