"""Tests for build worker configuration."""

import os
from unittest.mock import patch

from src.config import BuildConfig


class TestBuildConfig:
    def test_from_env_defaults(self):
        """Config loads with defaults when env vars are missing."""
        with patch.dict(os.environ, {}, clear=True):
            config = BuildConfig.from_env()
            assert config.api_url == "https://staging.concord.local"
            assert config.api_key == ""
            assert config.poll_interval == 5
            assert config.workspace_dir == "/tmp/builds"
            assert config.ssh_key_path == "/root/.ssh/id_rsa"
            assert config.ncs_version is None

    def test_from_env_custom(self):
        """Config reads custom values from environment."""
        env = {
            "CONCORD_API_URL": "https://prod.example.com",
            "CONCORD_API_KEY": "test-key-123",
            "WORKER_ID": "worker-1",
            "POLL_INTERVAL": "10",
            "WORKSPACE_DIR": "/builds",
            "SSH_KEY_PATH": "/keys/id_rsa",
            "NCS_VERSION": "2.7.0",
        }
        with patch.dict(os.environ, env, clear=True):
            config = BuildConfig.from_env()
            assert config.api_url == "https://prod.example.com"
            assert config.api_key == "test-key-123"
            assert config.worker_id == "worker-1"
            assert config.poll_interval == 10
            assert config.workspace_dir == "/builds"
            assert config.ssh_key_path == "/keys/id_rsa"
            assert config.ncs_version == "2.7.0"
