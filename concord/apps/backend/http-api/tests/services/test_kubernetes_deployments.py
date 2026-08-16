"""Tests for services/kubernetes/deployments.py — K8s deployment operations."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


class TestListDeployments:
    @patch("src.services.kubernetes.deployments.serialize_deployment")
    @patch("src.services.kubernetes.deployments.get_apps_v1_api")
    def test_list_namespaced(self, mock_get_api, mock_serialize):
        from src.services.kubernetes.deployments import list_deployments
        api = MagicMock()
        mock_get_api.return_value = api
        dep = MagicMock()
        api.list_namespaced_deployment.return_value = MagicMock(items=[dep])
        mock_serialize.return_value = {"name": "test"}

        result = list_deployments(namespace="staging")
        assert len(result) == 1
        api.list_namespaced_deployment.assert_called_once_with("staging")

    @patch("src.services.kubernetes.deployments.serialize_deployment")
    @patch("src.services.kubernetes.deployments.get_apps_v1_api")
    def test_list_all_namespaces(self, mock_get_api, mock_serialize):
        from src.services.kubernetes.deployments import list_deployments
        api = MagicMock()
        mock_get_api.return_value = api
        api.list_deployment_for_all_namespaces.return_value = MagicMock(items=[])

        result = list_deployments()
        assert result == []
        api.list_deployment_for_all_namespaces.assert_called_once()

    @patch("src.services.kubernetes.deployments.serialize_deployment")
    @patch("src.services.kubernetes.deployments.get_apps_v1_api")
    def test_list_with_selectors(self, mock_get_api, mock_serialize):
        from src.services.kubernetes.deployments import list_deployments
        api = MagicMock()
        mock_get_api.return_value = api
        api.list_namespaced_deployment.return_value = MagicMock(items=[])

        list_deployments(
            namespace="staging",
            label_selector="app=concord",
            field_selector="metadata.name=http-api",
        )
        call_kwargs = api.list_namespaced_deployment.call_args[1]
        assert call_kwargs["label_selector"] == "app=concord"
        assert call_kwargs["field_selector"] == "metadata.name=http-api"


class TestGetDeployment:
    @patch("src.services.kubernetes.deployments.get_core_v1_api")
    @patch("src.services.kubernetes.deployments.serialize_deployment")
    @patch("src.services.kubernetes.deployments.get_apps_v1_api")
    def test_success(self, mock_apps, mock_serialize, mock_core):
        from src.services.kubernetes.deployments import get_deployment
        api = MagicMock()
        mock_apps.return_value = api
        dep = MagicMock()
        dep.spec.selector.match_labels = {"app": "concord"}
        api.read_namespaced_deployment.return_value = dep
        mock_serialize.return_value = {"name": "test"}

        core = MagicMock()
        mock_core.return_value = core
        pod = MagicMock()
        pod.metadata.name = "pod-1"
        pod.status.phase = "Running"
        pod.status.container_statuses = [MagicMock(ready=True, restart_count=0)]
        pod.spec.node_name = "node-1"
        core.list_namespaced_pod.return_value = MagicMock(items=[pod])

        result = get_deployment("staging", "http-api")
        assert result is not None
        assert result["pods"][0]["name"] == "pod-1"
        assert result["pods"][0]["ready"] is True

    @patch("src.services.kubernetes.deployments.get_apps_v1_api")
    def test_not_found(self, mock_apps):
        from kubernetes.client.exceptions import ApiException
        from src.services.kubernetes.deployments import get_deployment
        api = MagicMock()
        mock_apps.return_value = api
        api.read_namespaced_deployment.side_effect = ApiException(status=404, reason="Not Found")

        result = get_deployment("staging", "nonexistent")
        assert result is None


class TestScaleDeployment:
    @patch("src.services.kubernetes.deployments.get_apps_v1_api")
    def test_success(self, mock_apps):
        from src.services.kubernetes.deployments import scale_deployment
        api = MagicMock()
        mock_apps.return_value = api

        result = scale_deployment("staging", "http-api", 3)
        assert result is True
        api.patch_namespaced_deployment_scale.assert_called_once()

    @patch("src.services.kubernetes.deployments.get_apps_v1_api")
    def test_failure(self, mock_apps):
        from kubernetes.client.exceptions import ApiException
        from src.services.kubernetes.deployments import scale_deployment
        api = MagicMock()
        mock_apps.return_value = api
        api.patch_namespaced_deployment_scale.side_effect = ApiException(
            status=403, reason="Forbidden"
        )

        result = scale_deployment("staging", "http-api", 3)
        assert result is False


class TestRestartDeployment:
    @patch("src.services.kubernetes.deployments.get_apps_v1_api")
    def test_success(self, mock_apps):
        from src.services.kubernetes.deployments import restart_deployment
        api = MagicMock()
        mock_apps.return_value = api

        result = restart_deployment("staging", "http-api")
        assert result is True
        api.patch_namespaced_deployment.assert_called_once()

    @patch("src.services.kubernetes.deployments.get_apps_v1_api")
    def test_failure(self, mock_apps):
        from kubernetes.client.exceptions import ApiException
        from src.services.kubernetes.deployments import restart_deployment
        api = MagicMock()
        mock_apps.return_value = api
        api.patch_namespaced_deployment.side_effect = ApiException(
            status=500, reason="Internal Error"
        )

        result = restart_deployment("staging", "http-api")
        assert result is False
