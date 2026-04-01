"""Integration tests for the Test Packages API endpoints."""

import io
import json
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from tests.conftest import make_obj


# ---------------------------------------------------------------------------
#  Helpers
# ---------------------------------------------------------------------------

def _now():
    return datetime(2026, 3, 31, 12, 0, 0, tzinfo=timezone.utc)


def _product_obj(**overrides):
    defaults = {
        "id": "prod-alpha",
        "name": "Alpha B0",
        "slug": "alpha-b0",
        "description": "Alpha board",
        "active": True,
        "createdAt": _now(),
        "updatedAt": _now(),
    }
    defaults.update(overrides)
    return make_obj(**defaults)


def _test_package_obj(**overrides):
    defaults = {
        "id": "tp-001",
        "productId": "prod-alpha",
        "version": "1.0.0",
        "status": "RELEASED",
        "storageKey": "test-packages/alpha-b0/1.0.0/package.tar.gz",
        "frameworkVersion": "0.3.0",
        "manifestHash": "abc123",
        "testCount": 15,
        "stagesEnabled": {"smoke": True, "fuota": True},
        "notes": "Initial release",
        "createdById": None,
        "createdAt": _now(),
        "updatedAt": _now(),
    }
    defaults.update(overrides)
    return make_obj(**defaults)


def _manifest(**overrides):
    """Build a valid manifest dict."""
    defaults = {
        "version": "1.0.0",
        "frameworkVersion": "0.3.0",
        "productSlug": "alpha-b0",
        "status": "RELEASED",
        "testCount": 15,
        "stagesEnabled": {"smoke": True, "fuota": True},
        "notes": "Initial release",
    }
    defaults.update(overrides)
    return defaults


def _tar_gz_data():
    """Return minimal bytes simulating a tar.gz file."""
    return b"\x1f\x8b" + b"\x00" * 100


# ---------------------------------------------------------------------------
#  Autouse fixture to mock storage
# ---------------------------------------------------------------------------

import pytest


@pytest.fixture(autouse=True)
def _mock_storage():
    """Prevent real MinIO calls in all tests in this module."""
    mock_client = MagicMock()
    with patch("api.v2.products.test_packages.get_storage_client", return_value=mock_client):
        with patch("api.v2.products.test_packages.get_bucket_name", return_value="test-bucket"):
            with patch("api.v2.products.test_packages.presigned_get_url", return_value="https://minio.local/presigned"):
                yield mock_client


# ---------------------------------------------------------------------------
#  POST /v2/products/<slug>/test-packages — Upload
# ---------------------------------------------------------------------------

class TestUploadTestPackage:
    """Tests for POST /v2/products/<slug>/test-packages."""

    def test_upload_success_released(self, authed_client, mock_db):
        """Upload a released test package creates a new record."""
        product = _product_obj()
        tp = _test_package_obj()
        mock_db.product.find_first.return_value = product
        mock_db.testpackage.find_first.return_value = None
        mock_db.testpackage.create.return_value = tp

        data = {
            "package": (io.BytesIO(_tar_gz_data()), "package.tar.gz"),
            "manifest": json.dumps(_manifest()),
        }
        resp = authed_client.post(
            "/v2/products/alpha-b0/test-packages",
            data=data,
            content_type="multipart/form-data",
        )
        assert resp.status_code == 201
        body = resp.get_json()
        assert body["data"]["id"] == "tp-001"
        assert body["data"]["version"] == "1.0.0"
        assert body["data"]["status"] == "RELEASED"
        mock_db.testpackage.create.assert_called_once()

    def test_upload_success_development(self, authed_client, mock_db):
        """Upload a development package creates a new record when none exists."""
        product = _product_obj()
        tp = _test_package_obj(status="DEVELOPMENT", version="dev-abc123")
        mock_db.product.find_first.return_value = product
        mock_db.testpackage.find_first.return_value = None
        mock_db.testpackage.create.return_value = tp

        data = {
            "package": (io.BytesIO(_tar_gz_data()), "package.tar.gz"),
            "manifest": json.dumps(_manifest(status="DEVELOPMENT", version="dev-abc123")),
        }
        resp = authed_client.post(
            "/v2/products/alpha-b0/test-packages",
            data=data,
            content_type="multipart/form-data",
        )
        assert resp.status_code == 201
        body = resp.get_json()
        assert body["data"]["status"] == "DEVELOPMENT"

    def test_upload_development_overwrites_existing(self, authed_client, mock_db):
        """Upload a development package overwrites an existing dev version."""
        product = _product_obj()
        existing = _test_package_obj(status="DEVELOPMENT", version="dev-abc123")
        updated = _test_package_obj(status="DEVELOPMENT", version="dev-abc123", id="tp-001")

        mock_db.product.find_first.return_value = product
        # For DEVELOPMENT status, only one find_first on testpackage (existing dev check)
        mock_db.testpackage.find_first.return_value = existing
        mock_db.testpackage.update.return_value = updated

        data = {
            "package": (io.BytesIO(_tar_gz_data()), "package.tar.gz"),
            "manifest": json.dumps(_manifest(status="DEVELOPMENT", version="dev-abc123")),
        }
        resp = authed_client.post(
            "/v2/products/alpha-b0/test-packages",
            data=data,
            content_type="multipart/form-data",
        )
        assert resp.status_code == 200
        mock_db.testpackage.update.assert_called_once()

    def test_upload_released_version_conflict(self, authed_client, mock_db):
        """Upload a released package with existing version returns 409."""
        product = _product_obj()
        existing = _test_package_obj()
        mock_db.product.find_first.return_value = product
        mock_db.testpackage.find_first.return_value = existing

        data = {
            "package": (io.BytesIO(_tar_gz_data()), "package.tar.gz"),
            "manifest": json.dumps(_manifest()),
        }
        resp = authed_client.post(
            "/v2/products/alpha-b0/test-packages",
            data=data,
            content_type="multipart/form-data",
        )
        assert resp.status_code == 409

    def test_upload_product_not_found(self, authed_client, mock_db):
        """Upload to a non-existent product slug returns 404."""
        mock_db.product.find_first.return_value = None

        data = {
            "package": (io.BytesIO(_tar_gz_data()), "package.tar.gz"),
            "manifest": json.dumps(_manifest(productSlug="nonexistent")),
        }
        resp = authed_client.post(
            "/v2/products/nonexistent/test-packages",
            data=data,
            content_type="multipart/form-data",
        )
        assert resp.status_code == 404

    def test_upload_no_file(self, authed_client, mock_db):
        """Upload without a package file returns 400."""
        mock_db.product.find_first.return_value = _product_obj()

        data = {
            "manifest": json.dumps(_manifest()),
        }
        resp = authed_client.post(
            "/v2/products/alpha-b0/test-packages",
            data=data,
            content_type="multipart/form-data",
        )
        assert resp.status_code == 400

    def test_upload_no_manifest(self, authed_client, mock_db):
        """Upload without a manifest field returns 400."""
        mock_db.product.find_first.return_value = _product_obj()

        data = {
            "package": (io.BytesIO(_tar_gz_data()), "package.tar.gz"),
        }
        resp = authed_client.post(
            "/v2/products/alpha-b0/test-packages",
            data=data,
            content_type="multipart/form-data",
        )
        assert resp.status_code == 400

    def test_upload_invalid_manifest_json(self, authed_client, mock_db):
        """Upload with invalid JSON manifest returns 400."""
        mock_db.product.find_first.return_value = _product_obj()

        data = {
            "package": (io.BytesIO(_tar_gz_data()), "package.tar.gz"),
            "manifest": "not valid json {{{",
        }
        resp = authed_client.post(
            "/v2/products/alpha-b0/test-packages",
            data=data,
            content_type="multipart/form-data",
        )
        assert resp.status_code == 400

    def test_upload_missing_version(self, authed_client, mock_db):
        """Upload with manifest missing version returns 400."""
        mock_db.product.find_first.return_value = _product_obj()

        data = {
            "package": (io.BytesIO(_tar_gz_data()), "package.tar.gz"),
            "manifest": json.dumps(_manifest(version="")),
        }
        resp = authed_client.post(
            "/v2/products/alpha-b0/test-packages",
            data=data,
            content_type="multipart/form-data",
        )
        assert resp.status_code == 400

    def test_upload_missing_framework_version(self, authed_client, mock_db):
        """Upload with manifest missing frameworkVersion returns 400."""
        mock_db.product.find_first.return_value = _product_obj()

        data = {
            "package": (io.BytesIO(_tar_gz_data()), "package.tar.gz"),
            "manifest": json.dumps(_manifest(frameworkVersion="")),
        }
        resp = authed_client.post(
            "/v2/products/alpha-b0/test-packages",
            data=data,
            content_type="multipart/form-data",
        )
        assert resp.status_code == 400

    def test_upload_slug_mismatch(self, authed_client, mock_db):
        """Upload with manifest productSlug mismatch returns 400."""
        mock_db.product.find_first.return_value = _product_obj()

        data = {
            "package": (io.BytesIO(_tar_gz_data()), "package.tar.gz"),
            "manifest": json.dumps(_manifest(productSlug="wrong-slug")),
        }
        resp = authed_client.post(
            "/v2/products/alpha-b0/test-packages",
            data=data,
            content_type="multipart/form-data",
        )
        assert resp.status_code == 400

    def test_upload_invalid_status(self, authed_client, mock_db):
        """Upload with invalid status returns 400."""
        mock_db.product.find_first.return_value = _product_obj()

        data = {
            "package": (io.BytesIO(_tar_gz_data()), "package.tar.gz"),
            "manifest": json.dumps(_manifest(status="INVALID")),
        }
        resp = authed_client.post(
            "/v2/products/alpha-b0/test-packages",
            data=data,
            content_type="multipart/form-data",
        )
        assert resp.status_code == 400

    def test_upload_invalid_file_extension(self, authed_client, mock_db):
        """Upload with a non-tar.gz file returns 400."""
        mock_db.product.find_first.return_value = _product_obj()

        data = {
            "package": (io.BytesIO(_tar_gz_data()), "package.zip"),
            "manifest": json.dumps(_manifest()),
        }
        resp = authed_client.post(
            "/v2/products/alpha-b0/test-packages",
            data=data,
            content_type="multipart/form-data",
        )
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
#  GET /v2/products/<slug>/test-packages — List
# ---------------------------------------------------------------------------

class TestListTestPackages:
    """Tests for GET /v2/products/<slug>/test-packages."""

    def test_list_success(self, authed_client, mock_db):
        """List test packages returns paginated results."""
        product = _product_obj()
        packages = [
            _test_package_obj(id="tp-001", version="1.0.0"),
            _test_package_obj(id="tp-002", version="0.9.0"),
        ]
        mock_db.product.find_first.return_value = product
        mock_db.testpackage.count.return_value = 2
        mock_db.testpackage.find_many.return_value = packages

        resp = authed_client.get("/v2/products/alpha-b0/test-packages")
        assert resp.status_code == 200
        body = resp.get_json()
        assert len(body["data"]["data"]) == 2
        assert body["data"]["pagination"]["total"] == 2

    def test_list_with_status_filter(self, authed_client, mock_db):
        """List test packages filters by status query param."""
        product = _product_obj()
        mock_db.product.find_first.return_value = product
        mock_db.testpackage.count.return_value = 1
        mock_db.testpackage.find_many.return_value = [
            _test_package_obj(status="RELEASED"),
        ]

        resp = authed_client.get("/v2/products/alpha-b0/test-packages?status=RELEASED")
        assert resp.status_code == 200
        # Verify that count was called with status filter
        call_args = mock_db.testpackage.count.call_args
        assert call_args[1]["where"]["status"] == "RELEASED"

    def test_list_empty(self, authed_client, mock_db):
        """List test packages returns empty data when none exist."""
        product = _product_obj()
        mock_db.product.find_first.return_value = product
        mock_db.testpackage.count.return_value = 0
        mock_db.testpackage.find_many.return_value = []

        resp = authed_client.get("/v2/products/alpha-b0/test-packages")
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["data"]["data"] == []
        assert body["data"]["pagination"]["total"] == 0

    def test_list_product_not_found(self, authed_client, mock_db):
        """List test packages for non-existent product returns 404."""
        mock_db.product.find_first.return_value = None

        resp = authed_client.get("/v2/products/nonexistent/test-packages")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
#  GET /v2/products/<slug>/test-packages/latest — Latest Released
# ---------------------------------------------------------------------------

class TestGetLatestTestPackage:
    """Tests for GET /v2/products/<slug>/test-packages/latest."""

    def test_latest_success(self, authed_client, mock_db):
        """Get latest released package returns the most recent one."""
        product = _product_obj()
        tp = _test_package_obj(version="2.0.0")
        mock_db.product.find_first.return_value = product
        mock_db.testpackage.find_first.return_value = tp

        resp = authed_client.get("/v2/products/alpha-b0/test-packages/latest")
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["data"]["version"] == "2.0.0"
        assert body["data"]["status"] == "RELEASED"

    def test_latest_no_released(self, authed_client, mock_db):
        """Get latest returns 404 when no released packages exist."""
        product = _product_obj()
        mock_db.product.find_first.return_value = product
        mock_db.testpackage.find_first.return_value = None

        resp = authed_client.get("/v2/products/alpha-b0/test-packages/latest")
        assert resp.status_code == 404

    def test_latest_product_not_found(self, authed_client, mock_db):
        """Get latest for non-existent product returns 404."""
        mock_db.product.find_first.return_value = None

        resp = authed_client.get("/v2/products/nonexistent/test-packages/latest")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
#  GET /v2/products/<slug>/test-packages/<version>/download — Download
# ---------------------------------------------------------------------------

class TestDownloadTestPackage:
    """Tests for GET /v2/products/<slug>/test-packages/<version>/download."""

    def test_download_success(self, authed_client, mock_db):
        """Download returns presigned URL and filename."""
        product = _product_obj()
        tp = _test_package_obj()
        mock_db.product.find_first.return_value = product
        mock_db.testpackage.find_first.return_value = tp

        resp = authed_client.get("/v2/products/alpha-b0/test-packages/1.0.0/download")
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["data"]["url"] == "https://minio.local/presigned"
        assert body["data"]["filename"] == "alpha-b0-1.0.0-test-package.tar.gz"
        assert body["data"]["version"] == "1.0.0"

    def test_download_version_not_found(self, authed_client, mock_db):
        """Download non-existent version returns 404."""
        product = _product_obj()
        mock_db.product.find_first.return_value = product
        mock_db.testpackage.find_first.return_value = None

        resp = authed_client.get("/v2/products/alpha-b0/test-packages/99.0.0/download")
        assert resp.status_code == 404

    def test_download_product_not_found(self, authed_client, mock_db):
        """Download for non-existent product returns 404."""
        mock_db.product.find_first.return_value = None

        resp = authed_client.get("/v2/products/nonexistent/test-packages/1.0.0/download")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
#  Serialization
# ---------------------------------------------------------------------------

class TestSerialization:
    """Tests for _serialize_test_package output format."""

    def test_serialization_fields(self, authed_client, mock_db):
        """Serialized test package contains all expected fields."""
        product = _product_obj()
        tp = _test_package_obj()
        mock_db.product.find_first.return_value = product
        mock_db.testpackage.find_first.return_value = tp

        resp = authed_client.get("/v2/products/alpha-b0/test-packages/latest")
        body = resp.get_json()
        data = body["data"]

        expected_fields = [
            "id", "productId", "version", "status",
            "frameworkVersion", "testCount", "stagesEnabled",
            "manifestHash", "notes", "createdAt", "updatedAt",
        ]
        for field in expected_fields:
            assert field in data, f"Missing field: {field}"

    def test_serialization_iso_dates(self, authed_client, mock_db):
        """Serialized dates are ISO 8601 format."""
        product = _product_obj()
        tp = _test_package_obj()
        mock_db.product.find_first.return_value = product
        mock_db.testpackage.find_first.return_value = tp

        resp = authed_client.get("/v2/products/alpha-b0/test-packages/latest")
        body = resp.get_json()
        data = body["data"]
        assert data["createdAt"] == "2026-03-31T12:00:00+00:00"
        assert data["updatedAt"] == "2026-03-31T12:00:00+00:00"
