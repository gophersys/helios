"""
Integration tests for Cluster Pod endpoints:

    GET    /v2/cluster/pods                              — list_pods
    GET    /v2/cluster/pods/<namespace>/<name>            — get_pod
    GET    /v2/cluster/pods/<namespace>/<name>/logs       — get_pod_logs
    DELETE /v2/cluster/pods/<namespace>/<name>            — delete_pod
"""

import json
from unittest.mock import patch

from kubernetes.client.exceptions import ApiException


# ---------------------------------------------------------------------------
# GET /v2/cluster/pods
# ---------------------------------------------------------------------------

class TestListPods:
    """Tests for the list_pods endpoint."""

    @patch("api.v2.system.pods.pods_svc.list_pods")
    def test_list_pods_success(self, mock_list, authed_client):
        """Should return 200 with a paginated list of pods."""
        mock_list.return_value = [
            {"name": "http-api-abc12", "namespace": "staging", "status": "Running"},
            {"name": "concord-ui-def34", "namespace": "staging", "status": "Running"},
            {"name": "postgres-0", "namespace": "staging", "status": "Running"},
        ]

        response = authed_client.get("/v2/cluster/pods")
        assert response.status_code == 200

        body = json.loads(response.data)
        assert body["errors"] == []
        assert len(body["data"]["data"]) == 3
        assert body["data"]["data"][0]["name"] == "http-api-abc12"
        assert body["data"]["pagination"]["total"] == 3
        assert body["data"]["pagination"]["page"] == 1

    @patch("api.v2.system.pods.pods_svc.list_pods")
    def test_list_pods_empty(self, mock_list, authed_client):
        """Should return 200 with an empty list when no pods exist."""
        mock_list.return_value = []

        response = authed_client.get("/v2/cluster/pods")
        assert response.status_code == 200

        body = json.loads(response.data)
        assert body["data"]["data"] == []
        assert body["data"]["pagination"]["total"] == 0

    @patch("api.v2.system.pods.pods_svc.list_pods")
    def test_list_pods_with_namespace_filter(self, mock_list, authed_client):
        """Should pass the namespace query param to the service layer."""
        mock_list.return_value = [
            {"name": "http-api-abc12", "namespace": "production", "status": "Running"},
        ]

        response = authed_client.get("/v2/cluster/pods?namespace=production")
        assert response.status_code == 200

        mock_list.assert_called_once_with(
            namespace="production",
            label_selector=None,
            field_selector=None,
        )

    @patch("api.v2.system.pods.pods_svc.list_pods")
    def test_list_pods_with_label_selector(self, mock_list, authed_client):
        """Should pass labelSelector query param to the service layer."""
        mock_list.return_value = [
            {"name": "http-api-abc12", "namespace": "staging", "status": "Running"},
        ]

        response = authed_client.get("/v2/cluster/pods?labelSelector=app=http-api")
        assert response.status_code == 200

        mock_list.assert_called_once_with(
            namespace=None,
            label_selector="app=http-api",
            field_selector=None,
        )

    @patch("api.v2.system.pods.pods_svc.list_pods")
    def test_list_pods_respects_limit(self, mock_list, authed_client):
        """Should truncate results to the specified limit."""
        mock_list.return_value = [
            {"name": f"pod-{i}", "namespace": "default", "status": "Running"}
            for i in range(10)
        ]

        response = authed_client.get("/v2/cluster/pods?limit=3")
        assert response.status_code == 200

        body = json.loads(response.data)
        assert len(body["data"]["data"]) == 3
        assert body["data"]["pagination"]["total"] == 10

    @patch("api.v2.system.pods.pods_svc.list_pods")
    def test_list_pods_pagination_page_2(self, mock_list, authed_client):
        """Should return the correct slice for page 2."""
        mock_list.return_value = [
            {"name": f"pod-{i}", "namespace": "default", "status": "Running"}
            for i in range(10)
        ]

        response = authed_client.get("/v2/cluster/pods?page=2&limit=3")
        assert response.status_code == 200

        body = json.loads(response.data)
        items = body["data"]["data"]
        pagination = body["data"]["pagination"]

        assert len(items) == 3
        assert items[0]["name"] == "pod-3"
        assert items[1]["name"] == "pod-4"
        assert items[2]["name"] == "pod-5"
        assert pagination["page"] == 2
        assert pagination["total"] == 10
        assert pagination["pages"] == 4  # ceil(10/3)

    @patch("api.v2.system.pods.pods_svc.list_pods")
    def test_list_pods_limit_clamped_max(self, mock_list, authed_client):
        """Limit should be clamped to max 1000."""
        mock_list.return_value = []

        response = authed_client.get("/v2/cluster/pods?limit=5000")
        assert response.status_code == 200
        # Handler clamps to 1000, result is [] anyway; just verify no error

    @patch("api.v2.system.pods.pods_svc.list_pods")
    def test_list_pods_limit_clamped_min(self, mock_list, authed_client):
        """Limit should be clamped to min 1."""
        mock_list.return_value = [{"name": "pod-0", "namespace": "default", "status": "Running"}]

        response = authed_client.get("/v2/cluster/pods?limit=0")
        assert response.status_code == 200

        body = json.loads(response.data)
        # min(max(0,1),1000) = 1 -> at most 1 item returned
        assert len(body["data"]["data"]) <= 1

    @patch("api.v2.system.pods.pods_svc.list_pods")
    def test_list_pods_k8s_api_exception(self, mock_list, authed_client):
        """Should return 500 on ApiException with non-404 status."""
        mock_list.side_effect = ApiException(status=500, reason="Internal Server Error")

        response = authed_client.get("/v2/cluster/pods")
        assert response.status_code == 500

    @patch("api.v2.system.pods.pods_svc.list_pods")
    def test_list_pods_generic_exception(self, mock_list, authed_client):
        """Should return 500 on unexpected exceptions."""
        mock_list.side_effect = Exception("Unexpected failure")

        response = authed_client.get("/v2/cluster/pods")
        assert response.status_code == 500

    def test_list_pods_requires_auth(self, client):
        """Should return 401 without authentication."""
        response = client.get("/v2/cluster/pods")
        assert response.status_code == 401


# ---------------------------------------------------------------------------
# GET /v2/cluster/pods/<namespace>/<name>
# ---------------------------------------------------------------------------

class TestGetPod:
    """Tests for the get_pod endpoint."""

    @patch("api.v2.system.pods.pods_svc.get_pod")
    def test_get_pod_success(self, mock_get, authed_client):
        """Should return 200 with detailed pod data."""
        mock_get.return_value = {
            "name": "http-api-abc12",
            "namespace": "staging",
            "status": "Running",
            "containers": [
                {"name": "http-api", "image": "concord/http-api:latest", "ready": True},
            ],
            "events": [],
        }

        response = authed_client.get("/v2/cluster/pods/staging/http-api-abc12")
        assert response.status_code == 200

        body = json.loads(response.data)
        assert body["data"]["name"] == "http-api-abc12"
        assert body["data"]["namespace"] == "staging"

    @patch("api.v2.system.pods.pods_svc.get_pod")
    def test_get_pod_not_found(self, mock_get, authed_client):
        """Should return 404 when the pod does not exist."""
        mock_get.return_value = None

        response = authed_client.get("/v2/cluster/pods/staging/nonexistent-pod")
        assert response.status_code == 404

    @patch("api.v2.system.pods.pods_svc.get_pod")
    def test_get_pod_k8s_api_404(self, mock_get, authed_client):
        """Should return 404 when K8s returns 404."""
        mock_get.side_effect = ApiException(status=404, reason="Not Found")

        response = authed_client.get("/v2/cluster/pods/staging/missing-pod")
        assert response.status_code == 404

    def test_get_pod_invalid_namespace(self, authed_client):
        """Should return 400 for invalid namespace name (uppercase, special chars)."""
        response = authed_client.get("/v2/cluster/pods/INVALID_NS/some-pod")
        assert response.status_code == 400

    def test_get_pod_invalid_name(self, authed_client):
        """Should return 400 for invalid pod name."""
        response = authed_client.get("/v2/cluster/pods/staging/INVALID_NAME!")
        assert response.status_code == 400


# ---------------------------------------------------------------------------
# GET /v2/cluster/pods/<namespace>/<name>/logs
# ---------------------------------------------------------------------------

class TestGetPodLogs:
    """Tests for the get_pod_logs endpoint."""

    @patch("api.v2.system.pods.pods_svc.get_pod_logs")
    def test_get_pod_logs_success(self, mock_logs, authed_client):
        """Should return 200 with log data for the pod."""
        mock_logs.return_value = {
            "podName": "http-api-abc12",
            "namespace": "staging",
            "containers": ["http-api"],
            "logs": {"http-api": "Starting server on :9001\nReady.\n"},
        }

        response = authed_client.get("/v2/cluster/pods/staging/http-api-abc12/logs")
        assert response.status_code == 200

        body = json.loads(response.data)
        assert body["data"]["podName"] == "http-api-abc12"
        assert "http-api" in body["data"]["logs"]
        assert "Starting server" in body["data"]["logs"]["http-api"]

    @patch("api.v2.system.pods.pods_svc.get_pod_logs")
    def test_get_pod_logs_not_found(self, mock_logs, authed_client):
        """Should return 404 when the pod does not exist."""
        mock_logs.return_value = None

        response = authed_client.get("/v2/cluster/pods/staging/nonexistent-pod/logs")
        assert response.status_code == 404

    @patch("api.v2.system.pods.pods_svc.get_pod_logs")
    def test_get_pod_logs_with_container(self, mock_logs, authed_client):
        """Should pass container query param to the service layer."""
        mock_logs.return_value = {
            "podName": "multi-container-pod",
            "namespace": "staging",
            "containers": ["sidecar"],
            "logs": {"sidecar": "Sidecar log output\n"},
        }

        response = authed_client.get(
            "/v2/cluster/pods/staging/multi-container-pod/logs?container=sidecar"
        )
        assert response.status_code == 200

        mock_logs.assert_called_once_with(
            "staging", "multi-container-pod",
            container="sidecar",
            tail_lines=100,
            previous=False,
            since_seconds=None,
        )

    @patch("api.v2.system.pods.pods_svc.get_pod_logs")
    def test_get_pod_logs_with_tail_lines(self, mock_logs, authed_client):
        """Should pass tailLines query param to the service layer."""
        mock_logs.return_value = {
            "podName": "http-api-abc12",
            "namespace": "staging",
            "containers": ["http-api"],
            "logs": {"http-api": "Last 10 lines\n"},
        }

        response = authed_client.get(
            "/v2/cluster/pods/staging/http-api-abc12/logs?tailLines=10"
        )
        assert response.status_code == 200

        mock_logs.assert_called_once_with(
            "staging", "http-api-abc12",
            container=None,
            tail_lines=10,
            previous=False,
            since_seconds=None,
        )

    @patch("api.v2.system.pods.pods_svc.get_pod_logs")
    def test_get_pod_logs_previous(self, mock_logs, authed_client):
        """Should pass previous=true query param to the service layer."""
        mock_logs.return_value = {
            "podName": "http-api-abc12",
            "namespace": "staging",
            "containers": ["http-api"],
            "logs": {"http-api": "Previous container logs\n"},
        }

        response = authed_client.get(
            "/v2/cluster/pods/staging/http-api-abc12/logs?previous=true"
        )
        assert response.status_code == 200

        mock_logs.assert_called_once_with(
            "staging", "http-api-abc12",
            container=None,
            tail_lines=100,
            previous=True,
            since_seconds=None,
        )

    @patch("api.v2.system.pods.pods_svc.get_pod_logs")
    def test_get_pod_logs_k8s_api_404(self, mock_logs, authed_client):
        """Should return 404 when K8s returns 404 ApiException."""
        mock_logs.side_effect = ApiException(status=404, reason="Not Found")

        response = authed_client.get("/v2/cluster/pods/staging/missing-pod/logs")
        assert response.status_code == 404

    @patch("api.v2.system.pods.pods_svc.get_pod_logs")
    def test_get_pod_logs_k8s_api_error(self, mock_logs, authed_client):
        """Should return 500 on non-404 K8s ApiException."""
        mock_logs.side_effect = ApiException(status=500, reason="Internal Server Error")

        response = authed_client.get("/v2/cluster/pods/staging/http-api-abc12/logs")
        assert response.status_code == 500

    def test_get_pod_logs_invalid_namespace(self, authed_client):
        """Should return 400 for invalid namespace name."""
        response = authed_client.get("/v2/cluster/pods/INVALID_NS/some-pod/logs")
        assert response.status_code == 400

    def test_get_pod_logs_invalid_name(self, authed_client):
        """Should return 400 for invalid pod name."""
        response = authed_client.get("/v2/cluster/pods/staging/INVALID_NAME!/logs")
        assert response.status_code == 400

    def test_get_pod_logs_requires_auth(self, client):
        """Should return 401 without authentication."""
        response = client.get("/v2/cluster/pods/staging/http-api-abc12/logs")
        assert response.status_code == 401


# ---------------------------------------------------------------------------
# DELETE /v2/cluster/pods/<namespace>/<name>
# ---------------------------------------------------------------------------

class TestDeletePod:
    """Tests for the delete_pod endpoint."""

    @patch("api.v2.system.pods.log_audit")
    @patch("api.v2.system.pods.pods_svc.delete_pod")
    def test_delete_pod_success(self, mock_delete, mock_audit, authed_client):
        """Should return 200 with deleted=True on successful deletion."""
        mock_delete.return_value = True

        response = authed_client.delete("/v2/cluster/pods/staging/http-api-abc12")
        assert response.status_code == 200

        body = json.loads(response.data)
        assert body["data"]["deleted"] is True
        mock_audit.assert_called_once()

    @patch("api.v2.system.pods.pods_svc.delete_pod")
    def test_delete_pod_service_returns_false(self, mock_delete, authed_client):
        """Should return 500 when the service layer returns False (failed to delete)."""
        mock_delete.return_value = False

        response = authed_client.delete("/v2/cluster/pods/staging/http-api-abc12")
        assert response.status_code == 500

    @patch("api.v2.system.pods.pods_svc.delete_pod")
    def test_delete_pod_not_found(self, mock_delete, authed_client):
        """Should return 404 when K8s returns a 404 ApiException."""
        mock_delete.side_effect = ApiException(status=404, reason="Not Found")

        response = authed_client.delete("/v2/cluster/pods/staging/missing-pod")
        assert response.status_code == 404

    def test_delete_pod_invalid_namespace(self, authed_client):
        """Should return 400 for invalid namespace."""
        response = authed_client.delete("/v2/cluster/pods/BAD_NS/some-pod")
        assert response.status_code == 400

    def test_delete_pod_requires_auth(self, client):
        """Should return 401 without authentication."""
        response = client.delete("/v2/cluster/pods/staging/http-api-abc12")
        assert response.status_code == 401
