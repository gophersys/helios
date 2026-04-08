"""Tests for services/kubernetes/client.py — K8s client initialization and access."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


class TestInitKubernetesClient:
    @patch("src.services.kubernetes.client.k8s_client")
    @patch("src.services.kubernetes.client.k8s_config")
    def test_incluster_config(self, mock_config, mock_client):
        from src.services.kubernetes.client import init_kubernetes_client
        import src.services.kubernetes.client as client_mod

        original = client_mod.appKubernetesClient
        try:
            client_mod.appKubernetesClient = None
            mock_api_client = MagicMock()
            mock_client.ApiClient.return_value = mock_api_client

            result = init_kubernetes_client()
            assert result == mock_api_client
            mock_config.load_incluster_config.assert_called_once()
        finally:
            client_mod.appKubernetesClient = original

    @patch("src.services.kubernetes.client.k8s_client")
    @patch("src.services.kubernetes.client.k8s_config")
    def test_fallback_to_kubeconfig(self, mock_config, mock_client):
        from kubernetes import config as real_config
        from src.services.kubernetes.client import init_kubernetes_client
        import src.services.kubernetes.client as client_mod

        original = client_mod.appKubernetesClient
        try:
            client_mod.appKubernetesClient = None
            mock_config.ConfigException = real_config.ConfigException
            mock_config.load_incluster_config.side_effect = real_config.ConfigException("not in cluster")
            mock_api_client = MagicMock()
            mock_client.ApiClient.return_value = mock_api_client

            result = init_kubernetes_client()
            assert result == mock_api_client
            mock_config.load_kube_config.assert_called_once()
        finally:
            client_mod.appKubernetesClient = original

    @patch("src.services.kubernetes.client.k8s_client")
    @patch("src.services.kubernetes.client.k8s_config")
    def test_no_config_returns_none(self, mock_config, mock_client):
        from kubernetes import config as real_config
        from src.services.kubernetes.client import init_kubernetes_client
        import src.services.kubernetes.client as client_mod

        original = client_mod.appKubernetesClient
        try:
            client_mod.appKubernetesClient = None
            mock_config.ConfigException = real_config.ConfigException
            mock_config.load_incluster_config.side_effect = real_config.ConfigException("not in cluster")
            mock_config.load_kube_config.side_effect = real_config.ConfigException("no kubeconfig")

            result = init_kubernetes_client()
            assert result is None
        finally:
            client_mod.appKubernetesClient = original


class TestCloseKubernetesClient:
    def test_close_with_client(self):
        from src.services.kubernetes.client import close_kubernetes_client
        import src.services.kubernetes.client as client_mod

        original = client_mod.appKubernetesClient
        try:
            mock_client = MagicMock()
            client_mod.appKubernetesClient = mock_client

            close_kubernetes_client()
            mock_client.close.assert_called_once()
            assert client_mod.appKubernetesClient is None
        finally:
            client_mod.appKubernetesClient = original

    def test_close_with_no_client(self):
        from src.services.kubernetes.client import close_kubernetes_client
        import src.services.kubernetes.client as client_mod

        original = client_mod.appKubernetesClient
        try:
            client_mod.appKubernetesClient = None
            close_kubernetes_client()  # Should not raise
            assert client_mod.appKubernetesClient is None
        finally:
            client_mod.appKubernetesClient = original

    def test_close_with_exception(self):
        from src.services.kubernetes.client import close_kubernetes_client
        import src.services.kubernetes.client as client_mod

        original = client_mod.appKubernetesClient
        try:
            mock_client = MagicMock()
            mock_client.close.side_effect = Exception("close error")
            client_mod.appKubernetesClient = mock_client

            close_kubernetes_client()  # Should swallow exception
            assert client_mod.appKubernetesClient is None
        finally:
            client_mod.appKubernetesClient = original


class TestGetK8sClient:
    def test_raises_when_not_initialized(self):
        from src.services.kubernetes.client import get_k8s_client
        import src.services.kubernetes.client as client_mod

        original = client_mod.appKubernetesClient
        try:
            client_mod.appKubernetesClient = None
            with pytest.raises(RuntimeError):
                get_k8s_client()
        finally:
            client_mod.appKubernetesClient = original

    def test_returns_client(self):
        from src.services.kubernetes.client import get_k8s_client
        import src.services.kubernetes.client as client_mod

        original = client_mod.appKubernetesClient
        try:
            mock_client = MagicMock()
            client_mod.appKubernetesClient = mock_client

            result = get_k8s_client()
            assert result == mock_client
        finally:
            client_mod.appKubernetesClient = original


class TestApiGetters:
    @patch("src.services.kubernetes.client.get_k8s_client")
    @patch("src.services.kubernetes.client.k8s_client")
    def test_get_core_v1_api(self, mock_k8s, mock_get):
        from src.services.kubernetes.client import get_core_v1_api
        mock_get.return_value = MagicMock()
        result = get_core_v1_api()
        mock_k8s.CoreV1Api.assert_called_once()

    @patch("src.services.kubernetes.client.get_k8s_client")
    @patch("src.services.kubernetes.client.k8s_client")
    def test_get_apps_v1_api(self, mock_k8s, mock_get):
        from src.services.kubernetes.client import get_apps_v1_api
        mock_get.return_value = MagicMock()
        result = get_apps_v1_api()
        mock_k8s.AppsV1Api.assert_called_once()

    @patch("src.services.kubernetes.client.get_k8s_client")
    @patch("src.services.kubernetes.client.k8s_client")
    def test_get_batch_v1_api(self, mock_k8s, mock_get):
        from src.services.kubernetes.client import get_batch_v1_api
        mock_get.return_value = MagicMock()
        result = get_batch_v1_api()
        mock_k8s.BatchV1Api.assert_called_once()

    @patch("src.services.kubernetes.client.get_k8s_client")
    @patch("src.services.kubernetes.client.k8s_client")
    def test_get_networking_v1_api(self, mock_k8s, mock_get):
        from src.services.kubernetes.client import get_networking_v1_api
        mock_get.return_value = MagicMock()
        result = get_networking_v1_api()
        mock_k8s.NetworkingV1Api.assert_called_once()

    @patch("src.services.kubernetes.client.get_k8s_client")
    @patch("src.services.kubernetes.client.k8s_client")
    def test_get_rbac_v1_api(self, mock_k8s, mock_get):
        from src.services.kubernetes.client import get_rbac_v1_api
        mock_get.return_value = MagicMock()
        result = get_rbac_v1_api()
        mock_k8s.RbacAuthorizationV1Api.assert_called_once()
