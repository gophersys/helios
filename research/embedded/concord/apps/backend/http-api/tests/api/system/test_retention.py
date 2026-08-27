"""Tests for system retention endpoints — verifies error responses use proper ErrorDetail format."""

import json
from unittest.mock import patch, MagicMock

from tests.conftest import make_obj


_RETENTION_MODULE = "api.v2.system.retention"


class TestCleanupValidationRuns:
    """Tests for POST /v2/system/retention/validation/cleanup."""

    def test_cleanup_internal_error_returns_proper_error(self, authed_client, mock_db):
        """Verify 500 on exception returns proper error envelope, not raw string or traceback."""
        with patch(
            f"{_RETENTION_MODULE}.cleanup_old_validation_runs",
            side_effect=RuntimeError("database connection lost"),
        ):
            response = authed_client.post("/v2/system/retention/validation/cleanup")

        assert response.status_code == 500
        body = json.loads(response.data)
        assert body["data"] is None
        assert len(body["errors"]) > 0
        assert isinstance(body["errors"][0], dict)
        assert "message" in body["errors"][0]
        # Must NOT leak exception details to client
        assert "database connection lost" not in body["errors"][0]["message"]

    def test_cleanup_success(self, authed_client, mock_db):
        """Verify successful cleanup returns 200."""
        with patch(
            f"{_RETENTION_MODULE}.cleanup_old_validation_runs",
            return_value={"deleted": 5, "errors": []},
        ):
            response = authed_client.post("/v2/system/retention/validation/cleanup")

        assert response.status_code == 200
        body = json.loads(response.data)
        assert body["data"]["deleted"] == 5

    def test_cleanup_bad_retention_days(self, authed_client, mock_db):
        """Verify retention_days < 1 returns 400."""
        response = authed_client.post(
            "/v2/system/retention/validation/cleanup?retention_days=0"
        )
        assert response.status_code == 400
        body = json.loads(response.data)
        assert len(body["errors"]) > 0


class TestGetValidationStorageUsage:
    """Tests for GET /v2/system/retention/validation/usage."""

    def test_usage_internal_error_returns_proper_error(self, authed_client, mock_db):
        """Verify 500 on exception returns proper error envelope, not raw string or traceback."""
        with patch(
            f"{_RETENTION_MODULE}.get_storage_usage",
            side_effect=ConnectionError("storage unavailable"),
        ):
            response = authed_client.get("/v2/system/retention/validation/usage")

        assert response.status_code == 500
        body = json.loads(response.data)
        assert body["data"] is None
        assert len(body["errors"]) > 0
        assert isinstance(body["errors"][0], dict)
        assert "message" in body["errors"][0]
        # Must NOT leak exception details to client
        assert "storage unavailable" not in body["errors"][0]["message"]

    def test_usage_success(self, authed_client, mock_db):
        """Verify successful usage response returns 200."""
        with patch(
            f"{_RETENTION_MODULE}.get_storage_usage",
            return_value={"total_bytes": 1024, "run_count": 3},
        ):
            response = authed_client.get("/v2/system/retention/validation/usage")

        assert response.status_code == 200
        body = json.loads(response.data)
        assert body["data"]["total_bytes"] == 1024
