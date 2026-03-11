"""
Integration tests for Cluster Job endpoints:

    GET    /v2/cluster/jobs                         — list_jobs
    GET    /v2/cluster/jobs/<namespace>/<name>       — get_job
    DELETE /v2/cluster/jobs/<namespace>/<name>       — delete_job
"""

import json
from unittest.mock import patch

from kubernetes.client.exceptions import ApiException


# ---------------------------------------------------------------------------
# GET /v2/cluster/jobs
# ---------------------------------------------------------------------------

class TestListJobs:
    """Tests for the list_jobs endpoint."""

    @patch("api.v2.system.jobs.jobs_svc.list_jobs")
    def test_list_jobs_success(self, mock_list, authed_client):
        """Should return 200 with a paginated list of jobs."""
        mock_list.return_value = [
            {"name": "validation-run-001", "namespace": "staging", "status": "Complete"},
            {"name": "build-alpha-002", "namespace": "staging", "status": "Running"},
        ]

        response = authed_client.get("/v2/cluster/jobs")
        assert response.status_code == 200

        body = json.loads(response.data)
        assert body["errors"] == []
        assert len(body["data"]["data"]) == 2
        assert body["data"]["data"][0]["name"] == "validation-run-001"
        assert body["data"]["pagination"]["total"] == 2
        assert body["data"]["pagination"]["page"] == 1

    @patch("api.v2.system.jobs.jobs_svc.list_jobs")
    def test_list_jobs_with_namespace_filter(self, mock_list, authed_client):
        """Should pass namespace query param to the service layer."""
        mock_list.return_value = []

        response = authed_client.get("/v2/cluster/jobs?namespace=production")
        assert response.status_code == 200

        mock_list.assert_called_once_with(
            namespace="production",
            label_selector=None,
            field_selector=None,
        )

    @patch("api.v2.system.jobs.jobs_svc.list_jobs")
    def test_list_jobs_empty(self, mock_list, authed_client):
        """Should return 200 with an empty list when no jobs exist."""
        mock_list.return_value = []

        response = authed_client.get("/v2/cluster/jobs")
        assert response.status_code == 200

        body = json.loads(response.data)
        assert body["data"]["data"] == []
        assert body["data"]["pagination"]["total"] == 0

    @patch("api.v2.system.jobs.jobs_svc.list_jobs")
    def test_list_jobs_respects_limit(self, mock_list, authed_client):
        """Should truncate results to the specified limit."""
        mock_list.return_value = [
            {"name": f"job-{i}", "namespace": "default", "status": "Complete"}
            for i in range(10)
        ]

        response = authed_client.get("/v2/cluster/jobs?limit=5")
        assert response.status_code == 200

        body = json.loads(response.data)
        assert len(body["data"]["data"]) == 5
        assert body["data"]["pagination"]["total"] == 10
        assert body["data"]["pagination"]["limit"] == 5
        assert body["data"]["pagination"]["pages"] == 2

    @patch("api.v2.system.jobs.jobs_svc.list_jobs")
    def test_list_jobs_k8s_error(self, mock_list, authed_client):
        """Should return 500 on K8s API errors."""
        mock_list.side_effect = Exception("Timeout")

        response = authed_client.get("/v2/cluster/jobs")
        assert response.status_code == 500

    @patch("api.v2.system.jobs.jobs_svc.list_jobs")
    def test_list_jobs_k8s_api_exception_500(self, mock_list, authed_client):
        """Should return 500 on non-404 ApiException."""
        mock_list.side_effect = ApiException(status=500, reason="Internal Server Error")

        response = authed_client.get("/v2/cluster/jobs")
        assert response.status_code == 500

    def test_list_jobs_requires_auth(self, client):
        """Should return 401 without authentication."""
        response = client.get("/v2/cluster/jobs")
        assert response.status_code == 401

    @patch("api.v2.system.jobs.jobs_svc.list_jobs")
    def test_list_jobs_with_label_selector(self, mock_list, authed_client):
        """Should pass labelSelector query param to the service layer."""
        mock_list.return_value = [
            {"name": "validation-run-001", "namespace": "staging", "status": "Complete"},
        ]

        response = authed_client.get(
            "/v2/cluster/jobs?namespace=staging&labelSelector=app=validation"
        )
        assert response.status_code == 200

        mock_list.assert_called_once_with(
            namespace="staging",
            label_selector="app=validation",
            field_selector=None,
        )
        body = json.loads(response.data)
        assert len(body["data"]["data"]) == 1

    @patch("api.v2.system.jobs.jobs_svc.list_jobs")
    def test_list_jobs_with_field_selector(self, mock_list, authed_client):
        """Should pass fieldSelector query param to the service layer."""
        mock_list.return_value = []

        response = authed_client.get(
            "/v2/cluster/jobs?fieldSelector=status.successful=1"
        )
        assert response.status_code == 200

        mock_list.assert_called_once_with(
            namespace=None,
            label_selector=None,
            field_selector="status.successful=1",
        )

    @patch("api.v2.system.jobs.jobs_svc.list_jobs")
    def test_list_jobs_with_all_filters(self, mock_list, authed_client):
        """Should pass all filter params together to the service layer."""
        mock_list.return_value = []

        response = authed_client.get(
            "/v2/cluster/jobs?namespace=staging"
            "&labelSelector=app=validation"
            "&fieldSelector=status.successful=1"
        )
        assert response.status_code == 200

        mock_list.assert_called_once_with(
            namespace="staging",
            label_selector="app=validation",
            field_selector="status.successful=1",
        )

    @patch("api.v2.system.jobs.jobs_svc.list_jobs")
    def test_list_jobs_pagination_page_2(self, mock_list, authed_client):
        """Should return the second page of results."""
        mock_list.return_value = [
            {"name": f"job-{i}", "namespace": "default", "status": "Complete"}
            for i in range(10)
        ]

        response = authed_client.get("/v2/cluster/jobs?page=2&limit=3")
        assert response.status_code == 200

        body = json.loads(response.data)
        assert len(body["data"]["data"]) == 3
        assert body["data"]["data"][0]["name"] == "job-3"
        assert body["data"]["pagination"]["page"] == 2
        assert body["data"]["pagination"]["total"] == 10
        assert body["data"]["pagination"]["pages"] == 4


# ---------------------------------------------------------------------------
# GET /v2/cluster/jobs/<namespace>/<name>
# ---------------------------------------------------------------------------

class TestGetJob:
    """Tests for the get_job endpoint."""

    @patch("api.v2.system.jobs.jobs_svc.get_job")
    def test_get_job_success(self, mock_get, authed_client):
        """Should return 200 with detailed job data."""
        mock_get.return_value = {
            "name": "validation-run-001",
            "namespace": "staging",
            "status": "Complete",
            "pods": [
                {"name": "validation-run-001-abc12", "status": "Succeeded", "restarts": 0},
            ],
        }

        response = authed_client.get("/v2/cluster/jobs/staging/validation-run-001")
        assert response.status_code == 200

        body = json.loads(response.data)
        assert body["data"]["name"] == "validation-run-001"
        assert len(body["data"]["pods"]) == 1

    @patch("api.v2.system.jobs.jobs_svc.get_job")
    def test_get_job_not_found(self, mock_get, authed_client):
        """Should return 404 when the job does not exist."""
        mock_get.return_value = None

        response = authed_client.get("/v2/cluster/jobs/staging/nonexistent-job")
        assert response.status_code == 404

    @patch("api.v2.system.jobs.jobs_svc.get_job")
    def test_get_job_k8s_api_404(self, mock_get, authed_client):
        """Should return 404 when K8s returns 404."""
        mock_get.side_effect = ApiException(status=404, reason="Not Found")

        response = authed_client.get("/v2/cluster/jobs/staging/missing-job")
        assert response.status_code == 404

    def test_get_job_invalid_namespace(self, authed_client):
        """Should return 400 for invalid namespace name."""
        response = authed_client.get("/v2/cluster/jobs/BAD_NS/some-job")
        assert response.status_code == 400

    def test_get_job_invalid_name(self, authed_client):
        """Should return 400 for invalid job name."""
        response = authed_client.get("/v2/cluster/jobs/staging/BAD_NAME!")
        assert response.status_code == 400


# ---------------------------------------------------------------------------
# DELETE /v2/cluster/jobs/<namespace>/<name>
# ---------------------------------------------------------------------------

class TestDeleteJob:
    """Tests for the delete_job endpoint."""

    @patch("api.v2.system.jobs.log_audit")
    @patch("api.v2.system.jobs.jobs_svc.delete_job")
    def test_delete_job_success(self, mock_delete, mock_audit, authed_client):
        """Should return 200 with deleted=True on success."""
        mock_delete.return_value = True

        response = authed_client.delete("/v2/cluster/jobs/staging/validation-run-001")
        assert response.status_code == 200

        body = json.loads(response.data)
        assert body["data"]["deleted"] is True
        mock_delete.assert_called_once_with("staging", "validation-run-001")
        mock_audit.assert_called_once()

    @patch("api.v2.system.jobs.jobs_svc.delete_job")
    def test_delete_job_service_returns_false(self, mock_delete, authed_client):
        """Should return 500 when the service layer returns False."""
        mock_delete.return_value = False

        response = authed_client.delete("/v2/cluster/jobs/staging/validation-run-001")
        assert response.status_code == 500

    @patch("api.v2.system.jobs.jobs_svc.delete_job")
    def test_delete_job_not_found(self, mock_delete, authed_client):
        """Should return 404 when K8s returns 404."""
        mock_delete.side_effect = ApiException(status=404, reason="Not Found")

        response = authed_client.delete("/v2/cluster/jobs/staging/missing-job")
        assert response.status_code == 404

    @patch("api.v2.system.jobs.jobs_svc.delete_job")
    def test_delete_job_k8s_error(self, mock_delete, authed_client):
        """Should return 500 on generic exceptions."""
        mock_delete.side_effect = Exception("Connection error")

        response = authed_client.delete("/v2/cluster/jobs/staging/some-job")
        assert response.status_code == 500

    def test_delete_job_invalid_namespace(self, authed_client):
        """Should return 400 for invalid namespace name."""
        response = authed_client.delete("/v2/cluster/jobs/BAD_NS/some-job")
        assert response.status_code == 400

    def test_delete_job_requires_auth(self, client):
        """Should return 401 without authentication."""
        response = client.delete("/v2/cluster/jobs/staging/some-job")
        assert response.status_code == 401
