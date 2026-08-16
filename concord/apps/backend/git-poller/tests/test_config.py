"""Tests for GitPollerConfig env-var parsing."""

import os
import pytest

from config import GitPollerConfig


class TestGitPollerConfigDefaults:
    def test_default_poll_interval(self, monkeypatch):
        monkeypatch.delenv("POLL_INTERVAL", raising=False)
        cfg = GitPollerConfig(auto_load_env=False)
        assert cfg.poll_interval == 5

    def test_default_product_cache_ttl(self, monkeypatch):
        monkeypatch.delenv("PRODUCT_CACHE_TTL", raising=False)
        cfg = GitPollerConfig(auto_load_env=False)
        assert cfg.product_cache_ttl == 60

    def test_default_service_port(self, monkeypatch):
        monkeypatch.delenv("SERVICE_PORT", raising=False)
        cfg = GitPollerConfig(auto_load_env=False)
        assert cfg.service_port == 9003

    def test_default_environment(self, monkeypatch):
        monkeypatch.delenv("ENVIRONMENT", raising=False)
        cfg = GitPollerConfig(auto_load_env=False)
        assert cfg.environment == "development"

    def test_default_bitbucket_workspace(self, monkeypatch):
        monkeypatch.delenv("BITBUCKET_WORKSPACE", raising=False)
        cfg = GitPollerConfig(auto_load_env=False)
        assert cfg.bitbucket_workspace == "corekinect"

    def test_default_ssh_key_path(self, monkeypatch):
        monkeypatch.delenv("SSH_KEY_PATH", raising=False)
        cfg = GitPollerConfig(auto_load_env=False)
        assert cfg.ssh_key_path == "/root/.ssh/id_rsa"

    def test_empty_secrets_default_to_empty_string(self, monkeypatch):
        for var in ("CONCORD_API_KEY", "BITBUCKET_SSH_KEY", "BITBUCKET_API_TOKEN", "BITBUCKET_EMAIL"):
            monkeypatch.delenv(var, raising=False)
        cfg = GitPollerConfig(auto_load_env=False)
        assert cfg.concord_api_key == ""
        assert cfg.bitbucket_ssh_key == ""
        assert cfg.bitbucket_api_token == ""
        assert cfg.bitbucket_email == ""


class TestGitPollerConfigFromEnv:
    def test_reads_poll_interval_from_env(self, monkeypatch):
        monkeypatch.setenv("POLL_INTERVAL", "15")
        cfg = GitPollerConfig(auto_load_env=False)
        assert cfg.poll_interval == 15

    def test_reads_product_cache_ttl_from_env(self, monkeypatch):
        monkeypatch.setenv("PRODUCT_CACHE_TTL", "120")
        cfg = GitPollerConfig(auto_load_env=False)
        assert cfg.product_cache_ttl == 120

    def test_reads_concord_api_url_from_env(self, monkeypatch):
        monkeypatch.setenv("CONCORD_API_URL", "http://my-api:9001")
        cfg = GitPollerConfig(auto_load_env=False)
        assert cfg.concord_api_url == "http://my-api:9001"

    def test_reads_concord_api_key_from_env(self, monkeypatch):
        monkeypatch.setenv("CONCORD_API_KEY", "ck_test_key")
        cfg = GitPollerConfig(auto_load_env=False)
        assert cfg.concord_api_key == "ck_test_key"

    def test_reads_bitbucket_workspace_from_env(self, monkeypatch):
        monkeypatch.setenv("BITBUCKET_WORKSPACE", "myworkspace")
        cfg = GitPollerConfig(auto_load_env=False)
        assert cfg.bitbucket_workspace == "myworkspace"

    def test_reads_bitbucket_email_from_env(self, monkeypatch):
        monkeypatch.setenv("BITBUCKET_EMAIL", "dev@example.com")
        cfg = GitPollerConfig(auto_load_env=False)
        assert cfg.bitbucket_email == "dev@example.com"

    def test_reads_bitbucket_api_token_from_env(self, monkeypatch):
        monkeypatch.setenv("BITBUCKET_API_TOKEN", "token123")
        cfg = GitPollerConfig(auto_load_env=False)
        assert cfg.bitbucket_api_token == "token123"

    def test_reads_ssh_key_path_from_env(self, monkeypatch):
        monkeypatch.setenv("SSH_KEY_PATH", "/custom/id_rsa")
        cfg = GitPollerConfig(auto_load_env=False)
        assert cfg.ssh_key_path == "/custom/id_rsa"

    def test_reads_bitbucket_ssh_key_from_env(self, monkeypatch):
        monkeypatch.setenv("BITBUCKET_SSH_KEY", "base64encodedkey==")
        cfg = GitPollerConfig(auto_load_env=False)
        assert cfg.bitbucket_ssh_key == "base64encodedkey=="

    def test_reads_service_port_from_env(self, monkeypatch):
        monkeypatch.setenv("SERVICE_PORT", "9999")
        cfg = GitPollerConfig(auto_load_env=False)
        assert cfg.service_port == 9999

    def test_reads_environment_from_env(self, monkeypatch):
        monkeypatch.setenv("ENVIRONMENT", "production")
        cfg = GitPollerConfig(auto_load_env=False)
        assert cfg.environment == "production"
