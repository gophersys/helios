"""Tests for validation catalog endpoints — verifies error responses use proper ErrorDetail format."""

import json
from pathlib import Path
from unittest.mock import patch, MagicMock

from tests.conftest import make_obj


_CATALOG_MODULE = "api.v2.validation.catalog"


class TestGetCatalog:
    """Tests for GET /v2/validation/catalog/<product>."""

    def test_catalog_not_found_returns_proper_error(self, authed_client, mock_db):
        """Verify 404 for unknown product returns proper error envelope."""
        with patch(f"{_CATALOG_MODULE}._load_catalog", return_value=None):
            response = authed_client.get("/v2/validation/catalog/nonexistent")

        assert response.status_code == 404
        body = json.loads(response.data)
        assert body["data"] is None
        assert len(body["errors"]) > 0
        assert isinstance(body["errors"][0], dict)
        assert "message" in body["errors"][0]


class TestSyncCatalog:
    """Tests for POST /v2/validation/catalog/<product>/sync."""

    def test_sync_catalog_not_found(self, authed_client, mock_db):
        """Verify 404 when catalog.yaml doesn't exist."""
        with patch(f"{_CATALOG_MODULE}._load_catalog", return_value=None):
            response = authed_client.post("/v2/validation/catalog/nonexistent/sync")

        assert response.status_code == 404
        body = json.loads(response.data)
        assert len(body["errors"]) > 0
        assert isinstance(body["errors"][0], dict)

    def test_sync_catalog_internal_error_no_exception_leak(self, authed_client, mock_db):
        """Verify 500 on DB exception returns generic message, not str(e)."""
        catalog = {
            "version": "1.0.0",
            "product": "alpha",
            "board": "alpha_b0",
            "stages": {"gate": {"name": "Gate Tests"}},
            "tests": [{"id": "t1", "name": "Test 1", "stage": "gate"}],
            "hardware": {},
        }
        with patch(f"{_CATALOG_MODULE}._load_catalog", return_value=catalog):
            # Make DB call fail
            mock_db.validationdesign.find_first.side_effect = RuntimeError(
                "connection refused to database host:5432"
            )
            response = authed_client.post(
                "/v2/validation/catalog/alpha/sync",
                data=json.dumps({}),
            )

        assert response.status_code == 500
        body = json.loads(response.data)
        assert body["data"] is None
        assert len(body["errors"]) > 0
        assert isinstance(body["errors"][0], dict)
        assert "message" in body["errors"][0]
        # Must NOT leak exception details (DB host, port, etc.)
        assert "connection refused" not in body["errors"][0]["message"]
        assert "5432" not in body["errors"][0]["message"]


class TestGetCatalogSyncStatus:
    """Tests for GET /v2/validation/catalog/<product>/sync."""

    def test_sync_status_not_found(self, authed_client, mock_db):
        """Verify 404 when catalog doesn't exist."""
        with patch(f"{_CATALOG_MODULE}._load_catalog", return_value=None):
            response = authed_client.get("/v2/validation/catalog/nonexistent/sync")

        assert response.status_code == 404
        body = json.loads(response.data)
        assert len(body["errors"]) > 0

    def test_sync_status_internal_error_no_exception_leak(self, authed_client, mock_db):
        """Verify 500 on DB exception returns generic message, not str(e)."""
        catalog = {
            "version": "1.0.0",
            "product": "alpha",
            "board": "alpha_b0",
            "stages": {"gate": {"name": "Gate Tests"}},
            "tests": [{"id": "t1", "name": "Test 1", "stage": "gate"}],
        }
        with patch(f"{_CATALOG_MODULE}._load_catalog", return_value=catalog):
            mock_db.validationdesign.find_first.side_effect = RuntimeError(
                "SSL handshake failed"
            )
            response = authed_client.get("/v2/validation/catalog/alpha/sync")

        assert response.status_code == 500
        body = json.loads(response.data)
        assert body["data"] is None
        assert len(body["errors"]) > 0
        assert isinstance(body["errors"][0], dict)
        assert "message" in body["errors"][0]
        # Must NOT leak exception details
        assert "SSL" not in body["errors"][0]["message"]
