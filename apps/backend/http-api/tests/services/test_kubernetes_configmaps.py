"""Tests for services/kubernetes/configmaps.py — ConfigMap and Secret operations."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


class TestListConfigmaps:
    @patch("src.services.kubernetes.configmaps.serialize_configmap")
    @patch("src.services.kubernetes.configmaps.get_core_v1_api")
    def test_list_namespaced(self, mock_core, mock_serialize):
        from src.services.kubernetes.configmaps import list_configmaps
        api = MagicMock()
        mock_core.return_value = api
        api.list_namespaced_config_map.return_value = MagicMock(items=[MagicMock()])
        mock_serialize.return_value = {"name": "test"}

        result = list_configmaps(namespace="staging")
        assert len(result) == 1
        api.list_namespaced_config_map.assert_called_once()

    @patch("src.services.kubernetes.configmaps.serialize_configmap")
    @patch("src.services.kubernetes.configmaps.get_core_v1_api")
    def test_list_all_namespaces(self, mock_core, mock_serialize):
        from src.services.kubernetes.configmaps import list_configmaps
        api = MagicMock()
        mock_core.return_value = api
        api.list_config_map_for_all_namespaces.return_value = MagicMock(items=[])

        result = list_configmaps()
        assert result == []
        api.list_config_map_for_all_namespaces.assert_called_once()

    @patch("src.services.kubernetes.configmaps.serialize_configmap")
    @patch("src.services.kubernetes.configmaps.get_core_v1_api")
    def test_list_with_label_selector(self, mock_core, mock_serialize):
        from src.services.kubernetes.configmaps import list_configmaps
        api = MagicMock()
        mock_core.return_value = api
        api.list_namespaced_config_map.return_value = MagicMock(items=[])

        list_configmaps(namespace="staging", label_selector="app=concord")
        call_kwargs = api.list_namespaced_config_map.call_args[1]
        assert call_kwargs["label_selector"] == "app=concord"


class TestGetConfigmap:
    @patch("src.services.kubernetes.configmaps.serialize_configmap")
    @patch("src.services.kubernetes.configmaps.get_core_v1_api")
    def test_success(self, mock_core, mock_serialize):
        from src.services.kubernetes.configmaps import get_configmap
        api = MagicMock()
        mock_core.return_value = api
        mock_serialize.return_value = {"name": "test", "data": {}}

        result = get_configmap("staging", "my-config")
        assert result is not None
        mock_serialize.assert_called_once()

    @patch("src.services.kubernetes.configmaps.get_core_v1_api")
    def test_not_found(self, mock_core):
        from kubernetes.client.exceptions import ApiException
        from src.services.kubernetes.configmaps import get_configmap
        api = MagicMock()
        mock_core.return_value = api
        api.read_namespaced_config_map.side_effect = ApiException(status=404, reason="Not Found")

        result = get_configmap("staging", "missing")
        assert result is None


class TestListSecrets:
    @patch("src.services.kubernetes.configmaps.serialize_secret")
    @patch("src.services.kubernetes.configmaps.get_core_v1_api")
    def test_list_namespaced(self, mock_core, mock_serialize):
        from src.services.kubernetes.configmaps import list_secrets
        api = MagicMock()
        mock_core.return_value = api
        api.list_namespaced_secret.return_value = MagicMock(items=[MagicMock()])
        mock_serialize.return_value = {"name": "test"}

        result = list_secrets(namespace="staging")
        assert len(result) == 1

    @patch("src.services.kubernetes.configmaps.serialize_secret")
    @patch("src.services.kubernetes.configmaps.get_core_v1_api")
    def test_list_all_namespaces(self, mock_core, mock_serialize):
        from src.services.kubernetes.configmaps import list_secrets
        api = MagicMock()
        mock_core.return_value = api
        api.list_secret_for_all_namespaces.return_value = MagicMock(items=[])

        result = list_secrets()
        assert result == []


class TestGetSecret:
    @patch("src.services.kubernetes.configmaps.serialize_secret")
    @patch("src.services.kubernetes.configmaps.get_core_v1_api")
    def test_success(self, mock_core, mock_serialize):
        from src.services.kubernetes.configmaps import get_secret
        api = MagicMock()
        mock_core.return_value = api
        mock_serialize.return_value = {"name": "test", "data": {}}

        result = get_secret("staging", "my-secret")
        assert result is not None

    @patch("src.services.kubernetes.configmaps.get_core_v1_api")
    def test_not_found(self, mock_core):
        from kubernetes.client.exceptions import ApiException
        from src.services.kubernetes.configmaps import get_secret
        api = MagicMock()
        mock_core.return_value = api
        api.read_namespaced_secret.side_effect = ApiException(status=404, reason="Not Found")

        result = get_secret("staging", "missing")
        assert result is None
