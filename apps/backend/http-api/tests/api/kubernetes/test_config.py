"""
Integration tests for Cluster ConfigMap and Secret endpoints:

    GET /v2/cluster/configmaps                         — list_configmaps
    GET /v2/cluster/configmaps/<namespace>/<name>       — get_configmap
    GET /v2/cluster/secrets                             — list_secrets
    GET /v2/cluster/secrets/<namespace>/<name>           — get_secret
"""

import json
from unittest.mock import patch

from kubernetes.client.exceptions import ApiException


# ---------------------------------------------------------------------------
# GET /v2/cluster/configmaps
# ---------------------------------------------------------------------------

class TestListConfigMaps:
    """Tests for the list_configmaps endpoint."""

    @patch("api.v2.kubernetes.config.config_svc.list_configmaps")
    def test_list_configmaps_success(self, mock_list, authed_client):
        """Should return 200 with a paginated list of configmaps."""
        mock_list.return_value = [
            {"name": "app-config", "namespace": "staging", "dataKeys": ["API_URL", "DB_HOST"]},
            {"name": "traefik-config", "namespace": "kube-system", "dataKeys": ["config.toml"]},
        ]

        response = authed_client.get("/v2/kubernetes/configmaps")
        assert response.status_code == 200

        body = json.loads(response.data)
        assert body["errors"] == []
        assert len(body["data"]["data"]) == 2
        assert body["data"]["pagination"]["total"] == 2

    @patch("api.v2.kubernetes.config.config_svc.list_configmaps")
    def test_list_configmaps_with_namespace(self, mock_list, authed_client):
        """Should pass namespace query param to the service layer."""
        mock_list.return_value = []

        response = authed_client.get("/v2/kubernetes/configmaps?namespace=staging")
        assert response.status_code == 200

        mock_list.assert_called_once_with(namespace="staging", label_selector=None)

    @patch("api.v2.kubernetes.config.config_svc.list_configmaps")
    def test_list_configmaps_with_label_selector(self, mock_list, authed_client):
        """Should pass labelSelector query param to the service layer."""
        mock_list.return_value = [
            {"name": "app-config", "namespace": "staging", "dataKeys": ["API_URL"]},
        ]

        response = authed_client.get("/v2/kubernetes/configmaps?labelSelector=app%3Dconcord")
        assert response.status_code == 200

        mock_list.assert_called_once_with(namespace=None, label_selector="app=concord")
        body = json.loads(response.data)
        assert len(body["data"]["data"]) == 1

    @patch("api.v2.kubernetes.config.config_svc.list_configmaps")
    def test_list_configmaps_with_namespace_and_label_selector(self, mock_list, authed_client):
        """Should pass both namespace and labelSelector to the service layer."""
        mock_list.return_value = []

        response = authed_client.get(
            "/v2/kubernetes/configmaps?namespace=staging&labelSelector=tier%3Dbackend"
        )
        assert response.status_code == 200

        mock_list.assert_called_once_with(namespace="staging", label_selector="tier=backend")

    @patch("api.v2.kubernetes.config.config_svc.list_configmaps")
    def test_list_configmaps_empty(self, mock_list, authed_client):
        """Should return 200 with an empty paginated list."""
        mock_list.return_value = []

        response = authed_client.get("/v2/kubernetes/configmaps")
        assert response.status_code == 200

        body = json.loads(response.data)
        assert body["data"]["data"] == []
        assert body["data"]["pagination"]["total"] == 0

    @patch("api.v2.kubernetes.config.config_svc.list_configmaps")
    def test_list_configmaps_k8s_error(self, mock_list, authed_client):
        """Should return 500 on K8s API errors."""
        mock_list.side_effect = Exception("Timeout")

        response = authed_client.get("/v2/kubernetes/configmaps")
        assert response.status_code == 500

    def test_list_configmaps_requires_auth(self, client):
        """Should return 401 without authentication."""
        response = client.get("/v2/kubernetes/configmaps")
        assert response.status_code == 401


# ---------------------------------------------------------------------------
# GET /v2/cluster/configmaps/<namespace>/<name>
# ---------------------------------------------------------------------------

class TestGetConfigMap:
    """Tests for the get_configmap endpoint."""

    @patch("api.v2.kubernetes.config.config_svc.get_configmap")
    def test_get_configmap_success(self, mock_get, authed_client):
        """Should return 200 with configmap data."""
        mock_get.return_value = {
            "name": "app-config",
            "namespace": "staging",
            "data": {"API_URL": "http://localhost:9001", "DB_HOST": "postgres"},
        }

        response = authed_client.get("/v2/kubernetes/configmaps/staging/app-config")
        assert response.status_code == 200

        body = json.loads(response.data)
        assert body["data"]["name"] == "app-config"
        assert body["data"]["data"]["API_URL"] == "http://localhost:9001"

    @patch("api.v2.kubernetes.config.config_svc.get_configmap")
    def test_get_configmap_not_found(self, mock_get, authed_client):
        """Should return 404 when the configmap does not exist."""
        mock_get.return_value = None

        response = authed_client.get("/v2/kubernetes/configmaps/staging/nonexistent")
        assert response.status_code == 404

    @patch("api.v2.kubernetes.config.config_svc.get_configmap")
    def test_get_configmap_k8s_api_404(self, mock_get, authed_client):
        """Should return 404 on K8s 404 ApiException."""
        mock_get.side_effect = ApiException(status=404, reason="Not Found")

        response = authed_client.get("/v2/kubernetes/configmaps/staging/missing")
        assert response.status_code == 404

    def test_get_configmap_invalid_namespace(self, authed_client):
        """Should return 400 for invalid namespace name."""
        response = authed_client.get("/v2/kubernetes/configmaps/BAD_NS/app-config")
        assert response.status_code == 400


# ---------------------------------------------------------------------------
# GET /v2/cluster/secrets
# ---------------------------------------------------------------------------

class TestListSecrets:
    """Tests for the list_secrets endpoint."""

    @patch("api.v2.kubernetes.config.config_svc.list_secrets")
    def test_list_secrets_success(self, mock_list, authed_client):
        """Should return 200 with a paginated list of secrets."""
        mock_list.return_value = [
            {"name": "db-credentials", "namespace": "staging", "type": "Opaque"},
            {"name": "tls-cert", "namespace": "staging", "type": "kubernetes.io/tls"},
        ]

        response = authed_client.get("/v2/kubernetes/secrets")
        assert response.status_code == 200

        body = json.loads(response.data)
        assert body["errors"] == []
        assert len(body["data"]["data"]) == 2
        assert body["data"]["pagination"]["total"] == 2

    @patch("api.v2.kubernetes.config.config_svc.list_secrets")
    def test_list_secrets_with_namespace(self, mock_list, authed_client):
        """Should pass namespace query param to the service layer."""
        mock_list.return_value = []

        response = authed_client.get("/v2/kubernetes/secrets?namespace=production")
        assert response.status_code == 200

        mock_list.assert_called_once_with(namespace="production", label_selector=None)

    @patch("api.v2.kubernetes.config.config_svc.list_secrets")
    def test_list_secrets_with_label_selector(self, mock_list, authed_client):
        """Should pass labelSelector query param to the service layer."""
        mock_list.return_value = [
            {"name": "db-credentials", "namespace": "staging", "type": "Opaque"},
        ]

        response = authed_client.get("/v2/kubernetes/secrets?labelSelector=app%3Dconcord")
        assert response.status_code == 200

        mock_list.assert_called_once_with(namespace=None, label_selector="app=concord")
        body = json.loads(response.data)
        assert len(body["data"]["data"]) == 1

    @patch("api.v2.kubernetes.config.config_svc.list_secrets")
    def test_list_secrets_with_namespace_and_label_selector(self, mock_list, authed_client):
        """Should pass both namespace and labelSelector to the service layer."""
        mock_list.return_value = []

        response = authed_client.get(
            "/v2/kubernetes/secrets?namespace=production&labelSelector=tier%3Dbackend"
        )
        assert response.status_code == 200

        mock_list.assert_called_once_with(namespace="production", label_selector="tier=backend")

    @patch("api.v2.kubernetes.config.config_svc.list_secrets")
    def test_list_secrets_k8s_error(self, mock_list, authed_client):
        """Should return 500 on K8s API errors."""
        mock_list.side_effect = Exception("Timeout")

        response = authed_client.get("/v2/kubernetes/secrets")
        assert response.status_code == 500

    def test_list_secrets_requires_auth(self, client):
        """Should return 401 without authentication."""
        response = client.get("/v2/kubernetes/secrets")
        assert response.status_code == 401


# ---------------------------------------------------------------------------
# GET /v2/cluster/secrets/<namespace>/<name>
# ---------------------------------------------------------------------------

class TestGetSecret:
    """Tests for the get_secret endpoint."""

    @patch("api.v2.kubernetes.config.config_svc.get_secret")
    @patch("api.v2.kubernetes.config.log_audit")
    def test_get_secret_success(self, mock_audit, mock_get, authed_client):
        """Should return 200 with secret data and generate audit log."""
        mock_get.return_value = {
            "name": "db-credentials",
            "namespace": "staging",
            "type": "Opaque",
            "data": {"username": "YWRtaW4=", "password": "cGFzc3dvcmQ="},
        }

        response = authed_client.get("/v2/kubernetes/secrets/staging/db-credentials")
        assert response.status_code == 200

        body = json.loads(response.data)
        assert body["data"]["name"] == "db-credentials"
        # Secret viewing is audit-logged
        mock_audit.assert_called_once_with("cluster.secret.view", "Secret", "staging/db-credentials")

    @patch("api.v2.kubernetes.config.log_audit")
    @patch("api.v2.kubernetes.config.config_svc.get_secret")
    def test_get_secret_not_found(self, mock_get, mock_audit, authed_client):
        """Should return 404 when the secret does not exist."""
        mock_get.return_value = None

        response = authed_client.get("/v2/kubernetes/secrets/staging/nonexistent")
        assert response.status_code == 404

    def test_get_secret_invalid_namespace(self, authed_client):
        """Should return 400 for invalid namespace name."""
        response = authed_client.get("/v2/kubernetes/secrets/BAD_NS/db-credentials")
        assert response.status_code == 400

    def test_get_secret_invalid_name(self, authed_client):
        """Should return 400 for invalid secret name."""
        response = authed_client.get("/v2/kubernetes/secrets/staging/BAD_NAME!")
        assert response.status_code == 400
