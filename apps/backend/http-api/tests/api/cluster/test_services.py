"""
Integration tests for Cluster Service endpoints:

    GET /v2/cluster/services                         — list_services
    GET /v2/cluster/services/<namespace>/<name>       — get_service
"""

import json
from unittest.mock import patch

from kubernetes.client.exceptions import ApiException


# ---------------------------------------------------------------------------
# GET /v2/cluster/services
# ---------------------------------------------------------------------------

class TestListServices:
    """Tests for the list_services endpoint."""

    @patch("api.v2.system.services_api.svc_svc.list_services")
    def test_list_services_success(self, mock_list, authed_client):
        """Should return 200 with a paginated list of services."""
        mock_list.return_value = [
            {"name": "http-api", "namespace": "staging", "type": "ClusterIP", "clusterIP": "10.43.0.10"},
            {"name": "postgres", "namespace": "staging", "type": "ClusterIP", "clusterIP": "10.43.0.11"},
        ]

        response = authed_client.get("/v2/cluster/services")
        assert response.status_code == 200

        body = json.loads(response.data)
        assert body["errors"] == []
        assert len(body["data"]["data"]) == 2
        assert body["data"]["data"][0]["name"] == "http-api"
        assert body["data"]["pagination"]["total"] == 2
        assert body["data"]["pagination"]["page"] == 1

    @patch("api.v2.system.services_api.svc_svc.list_services")
    def test_list_services_with_namespace(self, mock_list, authed_client):
        """Should pass namespace query param to the service layer."""
        mock_list.return_value = []

        response = authed_client.get("/v2/cluster/services?namespace=production")
        assert response.status_code == 200

        mock_list.assert_called_once_with(namespace="production", label_selector=None)

    @patch("api.v2.system.services_api.svc_svc.list_services")
    def test_list_services_with_label_selector(self, mock_list, authed_client):
        """Should pass label_selector query param to the service layer."""
        mock_list.return_value = [
            {"name": "http-api", "namespace": "staging", "type": "ClusterIP", "clusterIP": "10.43.0.10"},
        ]

        response = authed_client.get(
            "/v2/cluster/services?namespace=staging&labelSelector=app=http-api"
        )
        assert response.status_code == 200

        mock_list.assert_called_once_with(namespace="staging", label_selector="app=http-api")

        body = json.loads(response.data)
        assert len(body["data"]["data"]) == 1
        assert body["data"]["data"][0]["name"] == "http-api"

    @patch("api.v2.system.services_api.svc_svc.list_services")
    def test_list_services_empty(self, mock_list, authed_client):
        """Should return 200 with an empty paginated result."""
        mock_list.return_value = []

        response = authed_client.get("/v2/cluster/services")
        assert response.status_code == 200

        body = json.loads(response.data)
        assert body["data"]["data"] == []
        assert body["data"]["pagination"]["total"] == 0

    @patch("api.v2.system.services_api.svc_svc.list_services")
    def test_list_services_k8s_error(self, mock_list, authed_client):
        """Should return 500 on K8s API errors."""
        mock_list.side_effect = Exception("Timeout")

        response = authed_client.get("/v2/cluster/services")
        assert response.status_code == 500

    def test_list_services_requires_auth(self, client):
        """Should return 401 without authentication."""
        response = client.get("/v2/cluster/services")
        assert response.status_code == 401


# ---------------------------------------------------------------------------
# GET /v2/cluster/services/<namespace>/<name>
# ---------------------------------------------------------------------------

class TestGetService:
    """Tests for the get_service endpoint."""

    @patch("api.v2.system.services_api.svc_svc.get_service")
    def test_get_service_success(self, mock_get, authed_client):
        """Should return 200 with detailed service data."""
        mock_get.return_value = {
            "name": "http-api",
            "namespace": "staging",
            "type": "ClusterIP",
            "clusterIP": "10.43.0.10",
            "ports": [{"port": 9001, "targetPort": 9001, "protocol": "TCP"}],
            "endpoints": [
                {"addresses": ["10.42.0.15"], "ports": [{"port": 9001, "protocol": "TCP"}]},
            ],
        }

        response = authed_client.get("/v2/cluster/services/staging/http-api")
        assert response.status_code == 200

        body = json.loads(response.data)
        assert body["data"]["name"] == "http-api"
        assert len(body["data"]["endpoints"]) == 1

    @patch("api.v2.system.services_api.svc_svc.get_service")
    def test_get_service_not_found(self, mock_get, authed_client):
        """Should return 404 when the service does not exist."""
        mock_get.return_value = None

        response = authed_client.get("/v2/cluster/services/staging/nonexistent-svc")
        assert response.status_code == 404

    @patch("api.v2.system.services_api.svc_svc.get_service")
    def test_get_service_k8s_api_404(self, mock_get, authed_client):
        """Should return 404 on K8s 404 ApiException."""
        mock_get.side_effect = ApiException(status=404, reason="Not Found")

        response = authed_client.get("/v2/cluster/services/staging/missing")
        assert response.status_code == 404

    def test_get_service_invalid_namespace(self, authed_client):
        """Should return 400 for invalid namespace name."""
        response = authed_client.get("/v2/cluster/services/BAD_NS/http-api")
        assert response.status_code == 400

    def test_get_service_invalid_name(self, authed_client):
        """Should return 400 for invalid service name."""
        response = authed_client.get("/v2/cluster/services/staging/BAD!")
        assert response.status_code == 400
