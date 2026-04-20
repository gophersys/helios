"""Bitwarden-style URL resolution: env > config > default.

We verify the precedence is correct, including the edge case where the
saved config has a stale URL but ``$CONCORD_API_URL`` overrides it (the
common scenario when a dev points at staging from a corectl that was
last logged into production).
"""

from __future__ import annotations

import pytest

from corectl import config as cfg


def test_default_url_when_nothing_set(monkeypatch):
    monkeypatch.delenv("CONCORD_API_URL", raising=False)
    assert cfg.get_api_url({}) == cfg.DEFAULT_API_URL


def test_config_url_used_when_no_env(monkeypatch):
    monkeypatch.delenv("CONCORD_API_URL", raising=False)
    assert cfg.get_api_url({"api_url": "https://staging.concord.local"}) \
        == "https://staging.concord.local"


def test_env_overrides_config_and_default(monkeypatch):
    monkeypatch.setenv("CONCORD_API_URL", "https://overridden.example.com")
    # Config and default both ignored.
    assert cfg.get_api_url({"api_url": "https://saved.local"}) \
        == "https://overridden.example.com"
    assert cfg.get_api_url({}) == "https://overridden.example.com"


def test_get_session_returns_none_without_tokens():
    """Both access_token AND refresh_token must be present."""
    assert cfg.get_session({}) is None
    assert cfg.get_session({"access_token": "a"}) is None  # missing refresh
    assert cfg.get_session({"refresh_token": "r"}) is None  # missing access


def test_get_session_returns_full_record():
    config = {
        "access_token": "at", "refresh_token": "rt",
        "expires_at": "2026-01-01T00:00:00+00:00",
        "user_email": "alice@example.com",
        "api_url": "https://x.local",  # ignored — not part of session
    }
    s = cfg.get_session(config)
    assert s == {
        "access_token": "at",
        "refresh_token": "rt",
        "expires_at": "2026-01-01T00:00:00+00:00",
        "user_email": "alice@example.com",
    }


def test_store_and_clear_session_roundtrip(tmp_path, monkeypatch):
    """``store_session`` writes; ``clear_session`` removes the auth fields only."""
    monkeypatch.setattr(cfg, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(cfg, "CONFIG_FILE", tmp_path / "config.yaml")

    config: dict = {"api_url": "https://staging.local"}
    cfg.store_session(
        config,
        access_token="at",
        refresh_token="rt",
        expires_at="2026-01-01T00:00:00+00:00",
        user_email="alice@example.com",
    )

    # Reload from disk — proves persistence isn't a no-op.
    reloaded = cfg.load_config()
    assert reloaded["access_token"] == "at"
    assert reloaded["refresh_token"] == "rt"
    assert reloaded["api_url"] == "https://staging.local"  # preserved

    cfg.clear_session(reloaded)
    cfg.save_config(reloaded)
    cleared = cfg.load_config()
    assert "access_token" not in cleared
    assert "refresh_token" not in cleared
    assert cleared["api_url"] == "https://staging.local"  # still there


def test_service_account_key_only_from_env(monkeypatch):
    """``CONCORD_API_KEY`` is intentionally never read from the config file."""
    monkeypatch.delenv("CONCORD_API_KEY", raising=False)
    assert cfg.get_service_account_key({"api_token": "ck_should_not_be_read"}) is None

    monkeypatch.setenv("CONCORD_API_KEY", "ck_from_env")
    assert cfg.get_service_account_key({}) == "ck_from_env"
