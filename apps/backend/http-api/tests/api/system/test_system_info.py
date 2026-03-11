"""
Integration tests for System endpoints:

    GET  /v2/system/info                             — get_system_info
    POST /v2/system/retention/validation/cleanup      — cleanup_validation_runs
    GET  /v2/system/retention/validation/usage         — get_validation_storage_usage
"""

import json
from unittest.mock import patch, MagicMock

import pytest
from corekinect.utils import BuildInfo


# ---------------------------------------------------------------------------
# GET /v2/system/info
# ---------------------------------------------------------------------------

class TestSystemInfo:
    """Tests for the get_system_info endpoint."""

    def test_system_info_returns_200(self, authed_client):
        """GET /v2/system/info should return 200 with build metadata."""
        mock_info = BuildInfo(
            service="concord-http-api",
            version="1.2.3-abc1234",
            environment="test",
            git_commit="abc1234",
            git_branch="main",
            git_dirty=False,
            build_time="2026-01-15T10:30:00Z",
            build_host="build-server",
            python_version="3.12.0",
            arch="x86_64",
            os_info="Alpine Linux v3.19",
        )

        with patch("api.v2.system.info.collect_build_info", return_value=mock_info):
            response = authed_client.get("/v2/system/info")

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["data"]["service"] == "concord-http-api"
        assert data["data"]["version"] == "1.2.3-abc1234"
        assert data["data"]["environment"] == "test"
        assert data["data"]["gitCommit"] == "abc1234"
        assert data["data"]["gitBranch"] == "main"
        assert data["data"]["gitDirty"] is False
        assert data["data"]["buildTime"] == "2026-01-15T10:30:00Z"
        assert data["data"]["buildHost"] == "build-server"
        assert data["data"]["pythonVersion"] == "3.12.0"
        assert data["data"]["arch"] == "x86_64"
        assert data["data"]["os"] == "Alpine Linux v3.19"
        assert data["errors"] == []

    def test_system_info_requires_auth(self, client):
        """GET /v2/system/info should require authentication."""
        response = client.get("/v2/system/info")
        assert response.status_code == 401

    def test_system_info_dirty_flag(self, authed_client):
        """git_dirty should come through as a boolean."""
        mock_info = BuildInfo(
            service="concord-http-api",
            git_dirty=True,
        )

        with patch("api.v2.system.info.collect_build_info", return_value=mock_info):
            response = authed_client.get("/v2/system/info")

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["data"]["gitDirty"] is True

    def test_system_info_handles_exception(self, authed_client):
        """If collect_build_info raises, endpoint should return 500."""
        with patch("api.v2.system.info.collect_build_info", side_effect=RuntimeError("boom")):
            response = authed_client.get("/v2/system/info")

        assert response.status_code == 500
        data = json.loads(response.data)
        assert data["data"] is None
        assert len(data["errors"]) > 0


# ---------------------------------------------------------------------------
# POST /v2/system/retention/validation/cleanup
# ---------------------------------------------------------------------------

class TestRetentionCleanup:
    """Tests for the cleanup_validation_runs endpoint."""

    @patch("api.v2.system.retention.cleanup_old_validation_runs")
    def test_cleanup_success_default_retention(self, mock_cleanup, authed_client):
        """Should trigger cleanup with default 60-day retention and return result."""
        mock_cleanup.return_value = {
            "runs_deleted": 5,
            "objects_deleted": 42,
            "retention_days": 60,
            "cutoff_date": "2026-01-10T00:00:00+00:00",
        }

        response = authed_client.post("/v2/system/retention/validation/cleanup")
        assert response.status_code == 200

        body = json.loads(response.data)
        assert body["errors"] == []
        assert body["data"]["runs_deleted"] == 5
        assert body["data"]["objects_deleted"] == 42

        mock_cleanup.assert_called_once_with(60)

    @patch("api.v2.system.retention.cleanup_old_validation_runs")
    def test_cleanup_custom_retention_days(self, mock_cleanup, authed_client):
        """Should pass custom retention_days param to the service."""
        mock_cleanup.return_value = {
            "runs_deleted": 1,
            "objects_deleted": 10,
            "retention_days": 30,
            "cutoff_date": "2026-02-09T00:00:00+00:00",
        }

        response = authed_client.post(
            "/v2/system/retention/validation/cleanup?retention_days=30"
        )
        assert response.status_code == 200

        mock_cleanup.assert_called_once_with(30)

    def test_cleanup_retention_days_must_be_positive(self, authed_client):
        """Should return 400 when retention_days < 1."""
        response = authed_client.post(
            "/v2/system/retention/validation/cleanup?retention_days=0"
        )
        assert response.status_code == 400

        body = json.loads(response.data)
        assert len(body["errors"]) > 0
        assert "retention_days" in body["errors"][0]["message"]

    def test_cleanup_negative_retention_days(self, authed_client):
        """Should return 400 when retention_days is negative."""
        response = authed_client.post(
            "/v2/system/retention/validation/cleanup?retention_days=-5"
        )
        assert response.status_code == 400

    def test_cleanup_dry_run(self, authed_client):
        """Dry run should return 200 with a message (not yet implemented)."""
        response = authed_client.post(
            "/v2/system/retention/validation/cleanup?dry_run=true"
        )
        assert response.status_code == 200

        body = json.loads(response.data)
        assert body["errors"] == []
        assert body["data"]["dryRun"] is True

    @patch("api.v2.system.retention.cleanup_old_validation_runs")
    def test_cleanup_handles_service_exception(self, mock_cleanup, authed_client):
        """When cleanup raises, the endpoint should return 500 with a generic
        error message (no exception details leaked to client).
        """
        mock_cleanup.side_effect = RuntimeError("Storage connection failed")

        response = authed_client.post("/v2/system/retention/validation/cleanup")
        assert response.status_code == 500

        body = json.loads(response.data)
        assert body["data"] is None
        assert len(body["errors"]) > 0
        assert isinstance(body["errors"][0], dict)
        assert "message" in body["errors"][0]
        # Must NOT leak exception details
        assert "Storage connection failed" not in body["errors"][0]["message"]

    def test_cleanup_requires_auth(self, client):
        """Should return 401 without authentication."""
        response = client.post("/v2/system/retention/validation/cleanup")
        assert response.status_code == 401


# ---------------------------------------------------------------------------
# GET /v2/system/retention/validation/usage
# ---------------------------------------------------------------------------

class TestRetentionUsage:
    """Tests for the get_validation_storage_usage endpoint."""

    @patch("api.v2.system.retention.get_storage_usage")
    def test_usage_success(self, mock_usage, authed_client):
        """Should return storage usage statistics."""
        mock_usage.return_value = {
            "total_size_bytes": 104857600,
            "total_size_mb": 100.0,
            "total_objects": 250,
            "runs_count": 10,
            "runs": {
                "run-001": {"size": 10485760, "objects": 25},
                "run-002": {"size": 5242880, "objects": 12},
            },
        }

        response = authed_client.get("/v2/system/retention/validation/usage")
        assert response.status_code == 200

        body = json.loads(response.data)
        assert body["errors"] == []
        assert body["data"]["total_size_mb"] == 100.0
        assert body["data"]["total_objects"] == 250
        assert body["data"]["runs_count"] == 10
        assert len(body["data"]["runs"]) == 2

    @patch("api.v2.system.retention.get_storage_usage")
    def test_usage_empty(self, mock_usage, authed_client):
        """Should handle zero storage usage gracefully."""
        mock_usage.return_value = {
            "total_size_bytes": 0,
            "total_size_mb": 0.0,
            "total_objects": 0,
            "runs_count": 0,
            "runs": {},
        }

        response = authed_client.get("/v2/system/retention/validation/usage")
        assert response.status_code == 200

        body = json.loads(response.data)
        assert body["data"]["total_objects"] == 0
        assert body["data"]["runs_count"] == 0

    @patch("api.v2.system.retention.get_storage_usage")
    def test_usage_handles_service_exception(self, mock_usage, authed_client):
        """When get_storage_usage raises, the endpoint should return 500 with a
        generic error message (no exception details leaked to client).
        """
        mock_usage.side_effect = RuntimeError("MinIO unreachable")

        response = authed_client.get("/v2/system/retention/validation/usage")
        assert response.status_code == 500

        body = json.loads(response.data)
        assert body["data"] is None
        assert len(body["errors"]) > 0
        assert isinstance(body["errors"][0], dict)
        assert "message" in body["errors"][0]
        # Must NOT leak exception details
        assert "MinIO unreachable" not in body["errors"][0]["message"]

    def test_usage_requires_auth(self, client):
        """Should return 401 without authentication."""
        response = client.get("/v2/system/retention/validation/usage")
        assert response.status_code == 401
