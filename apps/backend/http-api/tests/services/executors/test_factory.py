"""Tests for executor factory."""

from unittest.mock import patch

import pytest

from services.executors.factory import get_executor


class TestGetExecutor:
    def test_build_always_docker(self):
        """Builds always use DockerExecutor regardless of environment."""
        for env in ("development", "staging", "production"):
            with patch("config.env.env_config") as mock_cfg:
                mock_cfg.ENVIRONMENT = env
                mock_cfg.BUILD_TIMEOUT_MINUTES = 45
                executor = get_executor("build")
                assert type(executor).__name__ == "DockerExecutor"

    def test_validation_docker_in_dev(self):
        with patch("config.env.env_config") as mock_cfg:
            mock_cfg.ENVIRONMENT = "development"
            mock_cfg.VALIDATION_TIMEOUT_MINUTES = 60
            executor = get_executor("validation")
            assert type(executor).__name__ == "DockerExecutor"

    def test_validation_k8s_in_staging(self):
        with patch("config.env.env_config") as mock_cfg:
            mock_cfg.ENVIRONMENT = "staging"
            executor = get_executor("validation")
            assert type(executor).__name__ == "KubernetesExecutor"

    def test_validation_k8s_in_production(self):
        with patch("config.env.env_config") as mock_cfg:
            mock_cfg.ENVIRONMENT = "production"
            executor = get_executor("validation")
            assert type(executor).__name__ == "KubernetesExecutor"

    def test_manufacturing_docker_in_dev(self):
        with patch("config.env.env_config") as mock_cfg:
            mock_cfg.ENVIRONMENT = "development"
            mock_cfg.VALIDATION_TIMEOUT_MINUTES = 60
            executor = get_executor("manufacturing")
            assert type(executor).__name__ == "DockerExecutor"

    def test_manufacturing_k8s_in_staging(self):
        with patch("config.env.env_config") as mock_cfg:
            mock_cfg.ENVIRONMENT = "staging"
            executor = get_executor("manufacturing")
            assert type(executor).__name__ == "KubernetesExecutor"

    def test_unknown_domain_raises(self):
        with patch("config.env.env_config") as mock_cfg:
            mock_cfg.ENVIRONMENT = "development"
            with pytest.raises(ValueError, match="Unknown executor domain"):
                get_executor("unknown")
