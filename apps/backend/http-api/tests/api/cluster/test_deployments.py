"""
Integration tests for Cluster Deployment endpoints:

    GET  /v2/cluster/deployments                              — list_deployments
    GET  /v2/cluster/deployments/<namespace>/<name>            — get_deployment
    POST /v2/cluster/deployments/<namespace>/<name>/scale      — scale_deployment
    POST /v2/cluster/deployments/<namespace>/<name>/restart    — restart_deployment
"""

import json
from unittest.mock import patch

from kubernetes.client.exceptions import ApiException


# ---------------------------------------------------------------------------
# GET /v2/cluster/deployments
# ---------------------------------------------------------------------------

class TestListDeployments:
    """Tests for the list_deployments endpoint."""

    @patch("api.v2.kubernetes.deployments.dep_svc.list_deployments")
    def test_list_deployments_success(self, mock_list, authed_client):
        """Should return 200 with a paginated list of deployments."""
        mock_list.return_value = [
            {"name": "http-api", "namespace": "staging", "replicas": 2, "availableReplicas": 2},
            {"name": "concord-frontend", "namespace": "staging", "replicas": 1, "availableReplicas": 1},
        ]

        response = authed_client.get("/v2/kubernetes/deployments")
        assert response.status_code == 200

        body = json.loads(response.data)
        assert body["errors"] == []
        assert len(body["data"]["data"]) == 2
        assert body["data"]["data"][0]["name"] == "http-api"
        assert body["data"]["pagination"]["total"] == 2
        assert body["data"]["pagination"]["page"] == 1

    @patch("api.v2.kubernetes.deployments.dep_svc.list_deployments")
    def test_list_deployments_with_namespace(self, mock_list, authed_client):
        """Should pass namespace query param to the service layer."""
        mock_list.return_value = []

        response = authed_client.get("/v2/kubernetes/deployments?namespace=production")
        assert response.status_code == 200

        mock_list.assert_called_once_with(namespace="production", label_selector=None, field_selector=None)

    @patch("api.v2.kubernetes.deployments.dep_svc.list_deployments")
    def test_list_deployments_empty(self, mock_list, authed_client):
        """Should return 200 with an empty list when no deployments exist."""
        mock_list.return_value = []

        response = authed_client.get("/v2/kubernetes/deployments")
        assert response.status_code == 200

        body = json.loads(response.data)
        assert body["data"]["data"] == []
        assert body["data"]["pagination"]["total"] == 0

    @patch("api.v2.kubernetes.deployments.dep_svc.list_deployments")
    def test_list_deployments_k8s_error(self, mock_list, authed_client):
        """Should return 500 when K8s API raises."""
        mock_list.side_effect = Exception("Timeout")

        response = authed_client.get("/v2/kubernetes/deployments")
        assert response.status_code == 500

    @patch("api.v2.kubernetes.deployments.dep_svc.list_deployments")
    def test_list_deployments_pagination_page_2(self, mock_list, authed_client):
        """Should return the correct slice for page 2."""
        # Return 3 items; with limit=2, page 2 should have 1 item
        mock_list.return_value = [
            {"name": f"deploy-{i}", "namespace": "staging"} for i in range(3)
        ]

        response = authed_client.get("/v2/kubernetes/deployments?page=2&limit=2")
        assert response.status_code == 200

        body = json.loads(response.data)
        assert len(body["data"]["data"]) == 1
        assert body["data"]["data"][0]["name"] == "deploy-2"
        assert body["data"]["pagination"]["page"] == 2
        assert body["data"]["pagination"]["limit"] == 2
        assert body["data"]["pagination"]["total"] == 3
        assert body["data"]["pagination"]["pages"] == 2

    @patch("api.v2.kubernetes.deployments.dep_svc.list_deployments")
    def test_list_deployments_label_selector(self, mock_list, authed_client):
        """Should pass labelSelector query param to the service layer."""
        mock_list.return_value = [
            {"name": "http-api", "namespace": "staging"},
        ]

        response = authed_client.get(
            "/v2/kubernetes/deployments?labelSelector=app%3Dhttp-api"
        )
        assert response.status_code == 200

        mock_list.assert_called_once_with(
            namespace=None,
            label_selector="app=http-api",
            field_selector=None,
        )
        body = json.loads(response.data)
        assert len(body["data"]["data"]) == 1

    def test_list_deployments_requires_auth(self, client):
        """Should return 401 without authentication."""
        response = client.get("/v2/kubernetes/deployments")
        assert response.status_code == 401


# ---------------------------------------------------------------------------
# GET /v2/cluster/deployments/<namespace>/<name>
# ---------------------------------------------------------------------------

class TestGetDeployment:
    """Tests for the get_deployment endpoint."""

    @patch("api.v2.kubernetes.deployments.dep_svc.get_deployment")
    def test_get_deployment_success(self, mock_get, authed_client):
        """Should return 200 with detailed deployment data."""
        mock_get.return_value = {
            "name": "http-api",
            "namespace": "staging",
            "replicas": 2,
            "availableReplicas": 2,
            "pods": [
                {"name": "http-api-abc12", "status": "Running", "ready": True, "restarts": 0, "nodeName": "node-1"},
            ],
        }

        response = authed_client.get("/v2/kubernetes/deployments/staging/http-api")
        assert response.status_code == 200

        body = json.loads(response.data)
        assert body["data"]["name"] == "http-api"
        assert len(body["data"]["pods"]) == 1

    @patch("api.v2.kubernetes.deployments.dep_svc.get_deployment")
    def test_get_deployment_not_found(self, mock_get, authed_client):
        """Should return 404 when deployment does not exist."""
        mock_get.return_value = None

        response = authed_client.get("/v2/kubernetes/deployments/staging/nonexistent")
        assert response.status_code == 404

    @patch("api.v2.kubernetes.deployments.dep_svc.get_deployment")
    def test_get_deployment_k8s_404(self, mock_get, authed_client):
        """Should return 404 when K8s returns 404 ApiException."""
        mock_get.side_effect = ApiException(status=404, reason="Not Found")

        response = authed_client.get("/v2/kubernetes/deployments/staging/missing")
        assert response.status_code == 404

    def test_get_deployment_invalid_namespace(self, authed_client):
        """Should return 400 for invalid namespace name."""
        response = authed_client.get("/v2/kubernetes/deployments/INVALID/http-api")
        assert response.status_code == 400

    def test_get_deployment_invalid_name(self, authed_client):
        """Should return 400 for invalid deployment name."""
        response = authed_client.get("/v2/kubernetes/deployments/staging/INVALID_NAME!")
        assert response.status_code == 400


# ---------------------------------------------------------------------------
# POST /v2/cluster/deployments/<namespace>/<name>/scale
# ---------------------------------------------------------------------------

class TestScaleDeployment:
    """Tests for the scale_deployment endpoint."""

    @patch("api.v2.kubernetes.deployments.log_audit")
    @patch("api.v2.kubernetes.deployments.dep_svc.scale_deployment")
    def test_scale_deployment_success(self, mock_scale, mock_audit, authed_client):
        """Should return 200 with scaled=True on success."""
        mock_scale.return_value = True

        response = authed_client.post(
            "/v2/kubernetes/deployments/staging/http-api/scale",
            data=json.dumps({"replicas": 3}),
        )
        assert response.status_code == 200

        body = json.loads(response.data)
        assert body["data"]["scaled"] is True
        assert body["data"]["replicas"] == 3
        mock_scale.assert_called_once_with("staging", "http-api", 3)
        mock_audit.assert_called_once()

    @patch("api.v2.kubernetes.deployments.dep_svc.scale_deployment")
    def test_scale_deployment_to_zero(self, mock_scale, authed_client):
        """Should allow scaling to zero replicas."""
        mock_scale.return_value = True

        response = authed_client.post(
            "/v2/kubernetes/deployments/staging/http-api/scale",
            data=json.dumps({"replicas": 0}),
        )
        assert response.status_code == 200

        body = json.loads(response.data)
        assert body["data"]["scaled"] is True
        assert body["data"]["replicas"] == 0

    def test_scale_deployment_missing_replicas(self, authed_client):
        """Should return 400 when replicas field is missing."""
        response = authed_client.post(
            "/v2/kubernetes/deployments/staging/http-api/scale",
            data=json.dumps({}),
        )
        assert response.status_code == 400

    def test_scale_deployment_negative_replicas(self, authed_client):
        """Should return 400 when replicas is negative."""
        response = authed_client.post(
            "/v2/kubernetes/deployments/staging/http-api/scale",
            data=json.dumps({"replicas": -1}),
        )
        assert response.status_code == 400

    def test_scale_deployment_replicas_too_high(self, authed_client):
        """Should return 400 when replicas exceeds 100."""
        response = authed_client.post(
            "/v2/kubernetes/deployments/staging/http-api/scale",
            data=json.dumps({"replicas": 101}),
        )
        assert response.status_code == 400

    def test_scale_deployment_replicas_not_integer(self, authed_client):
        """Should return 400 when replicas is not an integer."""
        response = authed_client.post(
            "/v2/kubernetes/deployments/staging/http-api/scale",
            data=json.dumps({"replicas": "three"}),
        )
        assert response.status_code == 400

    def test_scale_deployment_no_body(self, authed_client):
        """Should return 400 when request body is empty."""
        response = authed_client.post(
            "/v2/kubernetes/deployments/staging/http-api/scale",
        )
        assert response.status_code == 400

    @patch("api.v2.kubernetes.deployments.dep_svc.scale_deployment")
    def test_scale_deployment_not_found(self, mock_scale, authed_client):
        """Should return 404 when deployment doesn't exist."""
        mock_scale.side_effect = ApiException(status=404, reason="Not Found")

        response = authed_client.post(
            "/v2/kubernetes/deployments/staging/missing-deploy/scale",
            data=json.dumps({"replicas": 2}),
        )
        assert response.status_code == 404

    @patch("api.v2.kubernetes.deployments.dep_svc.scale_deployment")
    def test_scale_deployment_service_returns_false(self, mock_scale, authed_client):
        """Should return 500 when scale fails."""
        mock_scale.return_value = False

        response = authed_client.post(
            "/v2/kubernetes/deployments/staging/http-api/scale",
            data=json.dumps({"replicas": 2}),
        )
        assert response.status_code == 500

    def test_scale_deployment_invalid_namespace(self, authed_client):
        """Should return 400 for invalid namespace name."""
        response = authed_client.post(
            "/v2/kubernetes/deployments/BAD_NS/http-api/scale",
            data=json.dumps({"replicas": 2}),
        )
        assert response.status_code == 400

    def test_scale_deployment_requires_auth(self, client):
        """Should return 401 without authentication."""
        response = client.post("/v2/kubernetes/deployments/staging/http-api/scale")
        assert response.status_code == 401


# ---------------------------------------------------------------------------
# POST /v2/cluster/deployments/<namespace>/<name>/restart
# ---------------------------------------------------------------------------

class TestRestartDeployment:
    """Tests for the restart_deployment endpoint."""

    @patch("api.v2.kubernetes.deployments.log_audit")
    @patch("api.v2.kubernetes.deployments.dep_svc.restart_deployment")
    def test_restart_deployment_success(self, mock_restart, mock_audit, authed_client):
        """Should return 200 with restarted=True on success."""
        mock_restart.return_value = True

        response = authed_client.post("/v2/kubernetes/deployments/staging/http-api/restart")
        assert response.status_code == 200

        body = json.loads(response.data)
        assert body["data"]["restarted"] is True
        mock_restart.assert_called_once_with("staging", "http-api")
        mock_audit.assert_called_once()

    @patch("api.v2.kubernetes.deployments.dep_svc.restart_deployment")
    def test_restart_deployment_service_returns_false(self, mock_restart, authed_client):
        """Should return 500 when restart fails."""
        mock_restart.return_value = False

        response = authed_client.post("/v2/kubernetes/deployments/staging/http-api/restart")
        assert response.status_code == 500

    @patch("api.v2.kubernetes.deployments.dep_svc.restart_deployment")
    def test_restart_deployment_not_found(self, mock_restart, authed_client):
        """Should return 404 when K8s returns 404."""
        mock_restart.side_effect = ApiException(status=404, reason="Not Found")

        response = authed_client.post("/v2/kubernetes/deployments/staging/missing-deploy/restart")
        assert response.status_code == 404

    @patch("api.v2.kubernetes.deployments.dep_svc.restart_deployment")
    def test_restart_deployment_k8s_error(self, mock_restart, authed_client):
        """Should return 500 on generic K8s exceptions."""
        mock_restart.side_effect = Exception("Timeout")

        response = authed_client.post("/v2/kubernetes/deployments/staging/http-api/restart")
        assert response.status_code == 500

    def test_restart_deployment_invalid_namespace(self, authed_client):
        """Should return 400 for invalid namespace name."""
        response = authed_client.post("/v2/kubernetes/deployments/BAD_NS/http-api/restart")
        assert response.status_code == 400

    def test_restart_deployment_requires_auth(self, client):
        """Should return 401 without authentication."""
        response = client.post("/v2/kubernetes/deployments/staging/http-api/restart")
        assert response.status_code == 401
