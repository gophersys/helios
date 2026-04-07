"""Tests for BuildServiceConfig."""

from __future__ import annotations

import pytest

from src.config import BuildServiceConfig


class TestBuildServiceConfigFromEnv:
    """Tests for BuildServiceConfig.from_env()."""

    def test_from_env_defaults(self, monkeypatch):
        """from_env() returns expected defaults when no env vars are set."""
        for key in [
            "ENVIRONMENT", "CONCORD_API_URL", "CONCORD_API_KEY", "WORKER_ID",
            "POLL_INTERVAL", "WORKSPACE_DIR", "BUILD_SERVICE_DATABASE_URL",
            "BUILD_SERVICE_PORT", "METRICS_ENABLED", "BUILDER_MODE",
            "DOCKER_SOCKET", "BUILDER_TIMEOUT", "DEFAULT_BUILDER_IMAGE",
            "WORKSPACE_VOLUME", "CCACHE_VOLUME", "BUILDER_NETWORK",
            "SSH_KEY_PATH", "BITBUCKET_SSH_KEY",
            "BENCH_SIGNING_KEY", "ENGINEERING_SIGNING_KEY", "PRODUCTION_SIGNING_KEY",
        ]:
            monkeypatch.delenv(key, raising=False)

        cfg = BuildServiceConfig.from_env()

        assert cfg.environment == "development"
        assert cfg.api_url == "https://staging.concord.local"
        assert cfg.api_key == ""
        assert cfg.poll_interval == 60  # Default changed from 5 to 60 (push mode fallback)
        assert cfg.workspace_dir == "/tmp/builds"
        assert cfg.service_port == 9002
        assert cfg.metrics_enabled is True
        assert cfg.builder_mode == "docker"
        assert cfg.docker_socket == "/var/run/docker.sock"
        assert cfg.builder_timeout == 1800
        assert cfg.builder_network == "host"
        assert cfg.ssh_key_path == "/root/.ssh/id_rsa"

    def test_from_env_custom_values(self, monkeypatch):
        """from_env() respects every individually set env var."""
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.setenv("CONCORD_API_URL", "https://prod.example.com")
        monkeypatch.setenv("CONCORD_API_KEY", "secret-key")
        monkeypatch.setenv("WORKER_ID", "worker-prod-7")
        monkeypatch.setenv("POLL_INTERVAL", "10")
        monkeypatch.setenv("WORKSPACE_DIR", "/mnt/builds")
        monkeypatch.setenv("BUILD_SERVICE_PORT", "9003")
        monkeypatch.setenv("METRICS_ENABLED", "false")
        monkeypatch.setenv("BUILDER_MODE", "local")
        monkeypatch.setenv("BUILDER_TIMEOUT", "3600")
        monkeypatch.setenv("BUILDER_NETWORK", "bridge")
        monkeypatch.setenv("BENCH_SIGNING_KEY", "bench==")
        monkeypatch.setenv("ENGINEERING_SIGNING_KEY", "eng==")
        monkeypatch.setenv("PRODUCTION_SIGNING_KEY", "prod==")

        cfg = BuildServiceConfig.from_env()

        assert cfg.environment == "production"
        assert cfg.api_url == "https://prod.example.com"
        assert cfg.api_key == "secret-key"
        assert cfg.worker_id == "worker-prod-7"
        assert cfg.poll_interval == 10
        assert cfg.workspace_dir == "/mnt/builds"
        assert cfg.service_port == 9003
        assert cfg.metrics_enabled is False
        assert cfg.builder_mode == "local"
        assert cfg.builder_timeout == 3600
        assert cfg.builder_network == "bridge"
        assert cfg.bench_signing_key == "bench=="
        assert cfg.engineering_signing_key == "eng=="
        assert cfg.production_signing_key == "prod=="

    @pytest.mark.parametrize("metrics_val,expected", [
        ("true", True),
        ("True", True),
        ("1", True),
        ("yes", True),
        ("false", False),
        ("0", False),
        ("no", False),
        ("", False),
    ])
    def test_metrics_enabled_parsing(self, monkeypatch, metrics_val, expected):
        """METRICS_ENABLED is parsed as bool for various truthy/falsy strings."""
        monkeypatch.setenv("METRICS_ENABLED", metrics_val)
        cfg = BuildServiceConfig.from_env()
        assert cfg.metrics_enabled is expected

    def test_service_name_property(self, config):
        """service_name property always returns 'build-service'."""
        assert config.service_name == "build-service"


class TestSigningKeyForTrack:
    """Tests for BuildServiceConfig.signing_key_for_track()."""

    def test_signing_key_for_bench(self, config):
        """signing_key_for_track('bench') returns bench_signing_key."""
        assert config.signing_key_for_track("bench") == config.bench_signing_key

    def test_signing_key_for_engineering(self, config):
        """signing_key_for_track('engineering') returns engineering_signing_key."""
        assert config.signing_key_for_track("engineering") == config.engineering_signing_key

    def test_signing_key_for_production(self, config):
        """signing_key_for_track('production') returns production_signing_key."""
        assert config.signing_key_for_track("production") == config.production_signing_key

    def test_signing_key_unknown_track_falls_back_to_bench(self, config):
        """signing_key_for_track('unknown') falls back to bench key."""
        result = config.signing_key_for_track("unknown-track")
        assert result == config.bench_signing_key

    @pytest.mark.parametrize("track", ["bench", "engineering", "production"])
    def test_signing_key_returns_nonempty_for_all_known_tracks(self, config, track):
        """Every known track returns a non-empty signing key when env is set."""
        result = config.signing_key_for_track(track)
        assert isinstance(result, str)
        assert len(result) > 0
