"""
Integration tests for Cluster Resource YAML endpoints:

    GET    /v2/cluster/resources/<kind>/<namespace>/<name>  — get_resource_yaml
    PUT    /v2/cluster/resources/<kind>/<namespace>/<name>  — apply_resource_yaml
    DELETE /v2/cluster/resources/<kind>/<namespace>/<name>  — delete_resource
"""

import json
from unittest.mock import patch

from kubernetes.client.exceptions import ApiException


# ---------------------------------------------------------------------------
# GET /v2/cluster/resources/<kind>/<namespace>/<name>
# ---------------------------------------------------------------------------

class TestGetResourceYaml:
    """Tests for the get_resource_yaml endpoint."""

    @patch("api.v2.kubernetes.resources.res_svc.get_resource_yaml")
    def test_get_resource_yaml_success(self, mock_get, authed_client):
        """Should return 200 with the resource YAML."""
        mock_get.return_value = {
            "kind": "Deployment",
            "apiVersion": "apps/v1",
            "yaml": "apiVersion: apps/v1\nkind: Deployment\nmetadata:\n  name: http-api\n",
        }

        response = authed_client.get("/v2/kubernetes/resources/Deployment/staging/http-api")
        assert response.status_code == 200

        body = json.loads(response.data)
        assert body["data"]["kind"] == "Deployment"
        assert body["data"]["apiVersion"] == "apps/v1"
        assert "yaml" in body["data"]

    @patch("api.v2.kubernetes.resources.res_svc.get_resource_yaml")
    def test_get_resource_yaml_not_found(self, mock_get, authed_client):
        """Should return 404 when the resource does not exist."""
        mock_get.return_value = None

        response = authed_client.get("/v2/kubernetes/resources/Deployment/staging/missing")
        assert response.status_code == 404

    @patch("api.v2.kubernetes.resources.res_svc.get_resource_yaml")
    def test_get_resource_yaml_k8s_api_404(self, mock_get, authed_client):
        """Should return 404 on K8s 404 ApiException."""
        mock_get.side_effect = ApiException(status=404, reason="Not Found")

        response = authed_client.get("/v2/kubernetes/resources/Pod/staging/missing")
        assert response.status_code == 404

    def test_get_resource_yaml_unsupported_kind(self, authed_client):
        """Should return 400 for unsupported resource kinds."""
        response = authed_client.get("/v2/kubernetes/resources/FooBar/staging/something")
        assert response.status_code == 400

    def test_get_resource_yaml_invalid_namespace(self, authed_client):
        """Should return 400 for invalid namespace name."""
        response = authed_client.get("/v2/kubernetes/resources/Deployment/BAD_NS/http-api")
        assert response.status_code == 400

    def test_get_resource_yaml_invalid_name(self, authed_client):
        """Should return 400 for invalid resource name."""
        response = authed_client.get("/v2/kubernetes/resources/Deployment/staging/BAD_NAME!")
        assert response.status_code == 400

    @patch("api.v2.kubernetes.resources.res_svc.get_resource_yaml")
    def test_get_resource_yaml_value_error(self, mock_get, authed_client):
        """Should return 400 on ValueError from the service."""
        mock_get.side_effect = ValueError("Invalid resource parameters")

        response = authed_client.get("/v2/kubernetes/resources/Pod/staging/test-pod")
        assert response.status_code == 400

    def test_get_resource_yaml_requires_auth(self, client):
        """Should return 401 without authentication."""
        response = client.get("/v2/kubernetes/resources/Deployment/staging/http-api")
        assert response.status_code == 401


# ---------------------------------------------------------------------------
# PUT /v2/cluster/resources/<kind>/<namespace>/<name>
# ---------------------------------------------------------------------------

class TestApplyResourceYaml:
    """Tests for the apply_resource_yaml endpoint."""

    @patch("api.v2.kubernetes.resources.log_audit")
    @patch("api.v2.kubernetes.resources.res_svc.apply_resource_yaml")
    def test_apply_resource_yaml_success(self, mock_apply, mock_audit, authed_client):
        """Should return 200 with the updated resource YAML."""
        mock_apply.return_value = {
            "kind": "Deployment",
            "apiVersion": "apps/v1",
            "yaml": "apiVersion: apps/v1\nkind: Deployment\nmetadata:\n  name: http-api\n",
        }

        response = authed_client.put(
            "/v2/kubernetes/resources/Deployment/staging/http-api",
            data=json.dumps({"yaml": "apiVersion: apps/v1\nkind: Deployment\nmetadata:\n  name: http-api\n"}),
        )
        assert response.status_code == 200

        body = json.loads(response.data)
        assert body["data"]["kind"] == "Deployment"
        mock_audit.assert_called_once()

    def test_apply_resource_yaml_missing_yaml_field(self, authed_client):
        """Should return 400 when yaml field is missing."""
        response = authed_client.put(
            "/v2/kubernetes/resources/Deployment/staging/http-api",
            data=json.dumps({}),
        )
        assert response.status_code == 400

    def test_apply_resource_yaml_no_body(self, authed_client):
        """Should return 400 when request body is empty."""
        response = authed_client.put(
            "/v2/kubernetes/resources/Deployment/staging/http-api",
        )
        assert response.status_code == 400

    def test_apply_resource_yaml_unsupported_kind(self, authed_client):
        """Should return 400 for unsupported resource kinds."""
        response = authed_client.put(
            "/v2/kubernetes/resources/FooBar/staging/something",
            data=json.dumps({"yaml": "kind: FooBar"}),
        )
        assert response.status_code == 400

    @patch("api.v2.kubernetes.resources.res_svc.apply_resource_yaml")
    def test_apply_resource_yaml_runtime_error(self, mock_apply, authed_client):
        """Should return 400 when the service raises RuntimeError."""
        mock_apply.side_effect = RuntimeError("Failed to apply: conflict")

        response = authed_client.put(
            "/v2/kubernetes/resources/Deployment/staging/http-api",
            data=json.dumps({"yaml": "apiVersion: apps/v1\nkind: Deployment\n"}),
        )
        assert response.status_code == 400

    @patch("api.v2.kubernetes.resources.res_svc.apply_resource_yaml")
    def test_apply_resource_yaml_k8s_404(self, mock_apply, authed_client):
        """Should return 404 on K8s 404 ApiException."""
        mock_apply.side_effect = ApiException(status=404, reason="Not Found")

        response = authed_client.put(
            "/v2/kubernetes/resources/Deployment/staging/missing",
            data=json.dumps({"yaml": "apiVersion: apps/v1\nkind: Deployment\n"}),
        )
        assert response.status_code == 404

    def test_apply_resource_yaml_invalid_namespace(self, authed_client):
        """Should return 400 for invalid namespace name."""
        response = authed_client.put(
            "/v2/kubernetes/resources/Deployment/BAD_NS/http-api",
            data=json.dumps({"yaml": "some yaml"}),
        )
        assert response.status_code == 400

    def test_apply_resource_yaml_requires_auth(self, client):
        """Should return 401 without authentication."""
        response = client.put("/v2/kubernetes/resources/Deployment/staging/http-api")
        assert response.status_code == 401


# ---------------------------------------------------------------------------
# DELETE /v2/cluster/resources/<kind>/<namespace>/<name>
# ---------------------------------------------------------------------------

class TestDeleteResource:
    """Tests for the delete_resource endpoint."""

    @patch("api.v2.kubernetes.resources.log_audit")
    @patch("api.v2.kubernetes.resources.res_svc.delete_resource")
    def test_delete_resource_success(self, mock_delete, mock_audit, authed_client):
        """Should return 200 with deleted=True on success."""
        mock_delete.return_value = True

        response = authed_client.delete("/v2/kubernetes/resources/Deployment/staging/http-api")
        assert response.status_code == 200

        body = json.loads(response.data)
        assert body["data"]["deleted"] is True
        mock_audit.assert_called_once()

    @patch("api.v2.kubernetes.resources.res_svc.delete_resource")
    def test_delete_resource_service_returns_false(self, mock_delete, authed_client):
        """Should return 500 when the service returns False."""
        mock_delete.return_value = False

        response = authed_client.delete("/v2/kubernetes/resources/Pod/staging/test-pod")
        assert response.status_code == 500

    @patch("api.v2.kubernetes.resources.res_svc.delete_resource")
    def test_delete_resource_not_found(self, mock_delete, authed_client):
        """Should return 404 when K8s returns 404."""
        mock_delete.side_effect = ApiException(status=404, reason="Not Found")

        response = authed_client.delete("/v2/kubernetes/resources/Deployment/staging/missing")
        assert response.status_code == 404

    def test_delete_resource_unsupported_kind(self, authed_client):
        """Should return 400 for unsupported resource kinds."""
        response = authed_client.delete("/v2/kubernetes/resources/FooBar/staging/something")
        assert response.status_code == 400

    def test_delete_resource_invalid_namespace(self, authed_client):
        """Should return 400 for invalid namespace name."""
        response = authed_client.delete("/v2/kubernetes/resources/Deployment/BAD_NS/http-api")
        assert response.status_code == 400

    @patch("api.v2.kubernetes.resources.res_svc.delete_resource")
    def test_delete_resource_value_error(self, mock_delete, authed_client):
        """Should return 400 on ValueError from the service."""
        mock_delete.side_effect = ValueError("Unsupported kind")

        response = authed_client.delete("/v2/kubernetes/resources/Pod/staging/test-pod")
        assert response.status_code == 400

    def test_delete_resource_requires_auth(self, client):
        """Should return 401 without authentication."""
        response = client.delete("/v2/kubernetes/resources/Deployment/staging/http-api")
        assert response.status_code == 401


# ---------------------------------------------------------------------------
# CronJob and ReplicaSet resource kind support
# ---------------------------------------------------------------------------

class TestCronJobAndReplicaSetSupport:
    """Tests that CronJob and ReplicaSet are accepted as valid resource kinds."""

    @patch("api.v2.kubernetes.resources.res_svc.get_resource_yaml")
    def test_get_cronjob_resource(self, mock_get, authed_client):
        """Should return 200 for CronJob kind."""
        mock_get.return_value = {
            "kind": "CronJob",
            "apiVersion": "batch/v1",
            "yaml": "apiVersion: batch/v1\nkind: CronJob\nmetadata:\n  name: db-backup\n",
        }

        response = authed_client.get("/v2/kubernetes/resources/CronJob/staging/db-backup")
        assert response.status_code == 200

        body = json.loads(response.data)
        assert body["data"]["kind"] == "CronJob"
        assert body["data"]["apiVersion"] == "batch/v1"

    @patch("api.v2.kubernetes.resources.res_svc.get_resource_yaml")
    def test_get_replicaset_resource(self, mock_get, authed_client):
        """Should return 200 for ReplicaSet kind."""
        mock_get.return_value = {
            "kind": "ReplicaSet",
            "apiVersion": "apps/v1",
            "yaml": "apiVersion: apps/v1\nkind: ReplicaSet\nmetadata:\n  name: http-api-abc123\n",
        }

        response = authed_client.get("/v2/kubernetes/resources/ReplicaSet/staging/http-api-abc123")
        assert response.status_code == 200

        body = json.loads(response.data)
        assert body["data"]["kind"] == "ReplicaSet"
        assert body["data"]["apiVersion"] == "apps/v1"

    @patch("api.v2.kubernetes.resources.log_audit")
    @patch("api.v2.kubernetes.resources.res_svc.apply_resource_yaml")
    def test_apply_cronjob_resource(self, mock_apply, mock_audit, authed_client):
        """Should return 200 when applying a CronJob resource."""
        mock_apply.return_value = {
            "kind": "CronJob",
            "apiVersion": "batch/v1",
            "yaml": "apiVersion: batch/v1\nkind: CronJob\n",
        }

        response = authed_client.put(
            "/v2/kubernetes/resources/CronJob/staging/db-backup",
            data=json.dumps({"yaml": "apiVersion: batch/v1\nkind: CronJob\n"}),
        )
        assert response.status_code == 200
        mock_audit.assert_called_once()

    @patch("api.v2.kubernetes.resources.log_audit")
    @patch("api.v2.kubernetes.resources.res_svc.delete_resource")
    def test_delete_replicaset_resource(self, mock_delete, mock_audit, authed_client):
        """Should return 200 when deleting a ReplicaSet resource."""
        mock_delete.return_value = True

        response = authed_client.delete("/v2/kubernetes/resources/ReplicaSet/staging/http-api-abc123")
        assert response.status_code == 200

        body = json.loads(response.data)
        assert body["data"]["deleted"] is True
        mock_audit.assert_called_once()


# ---------------------------------------------------------------------------
# Case-insensitive resource kind matching
# ---------------------------------------------------------------------------

class TestResourceKindCaseInsensitive:
    """Tests that resource kind validation is case-insensitive."""

    @patch("api.v2.kubernetes.resources.res_svc.get_resource_yaml")
    def test_lowercase_kind_accepted(self, mock_get, authed_client):
        """Should accept lowercase resource kind (e.g., 'deployment')."""
        mock_get.return_value = {"kind": "Deployment", "apiVersion": "apps/v1", "yaml": ""}

        response = authed_client.get("/v2/kubernetes/resources/deployment/staging/http-api")
        assert response.status_code == 200

    @patch("api.v2.kubernetes.resources.res_svc.get_resource_yaml")
    def test_uppercase_kind_accepted(self, mock_get, authed_client):
        """Should accept uppercase resource kind (e.g., 'DEPLOYMENT')."""
        mock_get.return_value = {"kind": "Deployment", "apiVersion": "apps/v1", "yaml": ""}

        response = authed_client.get("/v2/kubernetes/resources/DEPLOYMENT/staging/http-api")
        assert response.status_code == 200

    @patch("api.v2.kubernetes.resources.res_svc.get_resource_yaml")
    def test_mixed_case_kind_accepted(self, mock_get, authed_client):
        """Should accept mixed-case resource kind (e.g., 'dEpLoYmEnT')."""
        mock_get.return_value = {"kind": "Deployment", "apiVersion": "apps/v1", "yaml": ""}

        response = authed_client.get("/v2/kubernetes/resources/dEpLoYmEnT/staging/http-api")
        assert response.status_code == 200

    @patch("api.v2.kubernetes.resources.res_svc.get_resource_yaml")
    def test_cronjob_mixed_case_accepted(self, mock_get, authed_client):
        """Should accept 'cronJob' (mixed case) as a valid kind."""
        mock_get.return_value = {"kind": "CronJob", "apiVersion": "batch/v1", "yaml": ""}

        response = authed_client.get("/v2/kubernetes/resources/cronJob/staging/my-cron")
        assert response.status_code == 200

    @patch("api.v2.kubernetes.resources.res_svc.get_resource_yaml")
    def test_replicaset_mixed_case_accepted(self, mock_get, authed_client):
        """Should accept 'replicaSet' (mixed case) as a valid kind."""
        mock_get.return_value = {"kind": "ReplicaSet", "apiVersion": "apps/v1", "yaml": ""}

        response = authed_client.get("/v2/kubernetes/resources/replicaSet/staging/my-rs")
        assert response.status_code == 200
