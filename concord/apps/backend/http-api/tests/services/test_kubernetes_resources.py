"""Tests for services/kubernetes/resources.py — K8s resource YAML operations."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


class TestGetApiClient:
    def test_core(self):
        from src.services.kubernetes.resources import _get_api_client
        with patch("src.services.kubernetes.resources.get_core_v1_api") as m:
            _get_api_client("core")
            m.assert_called_once()

    def test_apps(self):
        from src.services.kubernetes.resources import _get_api_client
        with patch("src.services.kubernetes.resources.get_apps_v1_api") as m:
            _get_api_client("apps")
            m.assert_called_once()

    def test_batch(self):
        from src.services.kubernetes.resources import _get_api_client
        with patch("src.services.kubernetes.resources.get_batch_v1_api") as m:
            _get_api_client("batch")
            m.assert_called_once()

    def test_networking(self):
        from src.services.kubernetes.resources import _get_api_client
        with patch("src.services.kubernetes.resources.get_networking_v1_api") as m:
            _get_api_client("networking")
            m.assert_called_once()

    def test_unknown_raises(self):
        from src.services.kubernetes.resources import _get_api_client
        with pytest.raises(ValueError, match="Unknown API"):
            _get_api_client("custom")


class TestGetResourceYaml:
    @patch("src.services.kubernetes.resources.get_k8s_client")
    @patch("src.services.kubernetes.resources._get_api_client")
    def test_success(self, mock_get_api, mock_k8s):
        from src.services.kubernetes.resources import get_resource_yaml
        api = MagicMock()
        mock_get_api.return_value = api
        resource = MagicMock()
        api.read_namespaced_deployment.return_value = resource

        k8s_client = MagicMock()
        k8s_client.sanitize_for_serialization.return_value = {
            "metadata": {"name": "test", "managedFields": [], "resourceVersion": "1", "uid": "u"},
            "spec": {"replicas": 1},
            "status": {"ready": 1},
        }
        mock_k8s.return_value = k8s_client

        result = get_resource_yaml("deployment", "staging", "test")
        assert result is not None
        assert result["kind"] == "Deployment"
        assert result["apiVersion"] == "apps/v1"
        assert "yaml" in result
        # Status should be stripped
        assert "status" not in result["yaml"]

    @patch("src.services.kubernetes.resources._get_api_client")
    def test_not_found(self, mock_get_api):
        from kubernetes.client import ApiException
        from src.services.kubernetes.resources import get_resource_yaml
        api = MagicMock()
        mock_get_api.return_value = api
        api.read_namespaced_pod.side_effect = ApiException(status=404, reason="Not Found")

        result = get_resource_yaml("pod", "staging", "missing")
        assert result is None

    def test_unsupported_kind(self):
        from src.services.kubernetes.resources import get_resource_yaml
        with pytest.raises(ValueError, match="Unsupported"):
            get_resource_yaml("custom", "staging", "test")


class TestApplyResourceYaml:
    @patch("src.services.kubernetes.resources.get_resource_yaml")
    @patch("src.services.kubernetes.resources._get_api_client")
    def test_success(self, mock_get_api, mock_get_yaml):
        from src.services.kubernetes.resources import apply_resource_yaml
        api = MagicMock()
        mock_get_api.return_value = api
        mock_get_yaml.return_value = {"kind": "Deployment", "yaml": "replicas: 2"}

        yaml_str = "spec:\n  replicas: 2\n"
        result = apply_resource_yaml("deployment", "staging", "test", yaml_str)
        assert result is not None
        api.patch_namespaced_deployment.assert_called_once()

    def test_invalid_yaml_raises(self):
        from src.services.kubernetes.resources import apply_resource_yaml
        with patch("src.services.kubernetes.resources._get_api_client"):
            with pytest.raises(ValueError, match="YAML must be a mapping"):
                apply_resource_yaml("pod", "staging", "test", "just a string")

    def test_unsupported_kind(self):
        from src.services.kubernetes.resources import apply_resource_yaml
        with pytest.raises(ValueError, match="Unsupported"):
            apply_resource_yaml("custom", "staging", "test", "spec: {}")

    @patch("src.services.kubernetes.resources._get_api_client")
    def test_api_error_raises(self, mock_get_api):
        from kubernetes.client import ApiException
        from src.services.kubernetes.resources import apply_resource_yaml
        api = MagicMock()
        mock_get_api.return_value = api
        api.patch_namespaced_pod.side_effect = ApiException(status=403, reason="Forbidden")

        with pytest.raises(RuntimeError, match="Failed to apply"):
            apply_resource_yaml("pod", "staging", "test", "spec:\n  containers: []")


class TestDeleteResource:
    @patch("src.services.kubernetes.resources._get_api_client")
    def test_success(self, mock_get_api):
        from src.services.kubernetes.resources import delete_resource
        api = MagicMock()
        mock_get_api.return_value = api

        result = delete_resource("pod", "staging", "old-pod")
        assert result is True

    @patch("src.services.kubernetes.resources._get_api_client")
    def test_failure(self, mock_get_api):
        from kubernetes.client import ApiException
        from src.services.kubernetes.resources import delete_resource
        api = MagicMock()
        mock_get_api.return_value = api
        api.delete_namespaced_pod.side_effect = ApiException(status=404, reason="Not Found")

        result = delete_resource("pod", "staging", "missing")
        assert result is False

    def test_unsupported_kind(self):
        from src.services.kubernetes.resources import delete_resource
        with pytest.raises(ValueError, match="Unsupported"):
            delete_resource("custom", "staging", "test")
