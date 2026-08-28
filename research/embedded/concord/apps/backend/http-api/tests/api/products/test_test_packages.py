"""Integration tests for the Test Packages API endpoints."""

import io
import json
import tarfile
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
        "boardRevisionId": None,
        "version": "1.0.0",
        "type": "VALIDATION",
        "status": "RELEASED",
        "storageKey": "test-packages/alpha-b0/1.0.0/package.tar.gz",
        "frameworkVersion": "0.3.0",
        "schemaVersion": None,
        "message": None,
        "gitSha": None,
        "gitDirty": None,
        "manifestHash": "abc123",
        "testCount": 15,
        "stagesEnabled": {"smoke": True, "fuota": True},
        "notes": "Initial release",
        "releasedVersion": None,
        "releasedAt": None,
        "releasedById": None,
        "createdById": None,
        "createdAt": _now(),
        "updatedAt": _now(),
        "packageStages": None,
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


def _tar_gz_data(include_framework_markers: bool = True) -> bytes:
    """Build a minimal valid tar.gz containing the framework-artifact markers
    enforced by ``_check_framework_artifacts`` in the upload handler.

    The handler refuses any tarball without ``.claude/.framework-version`` and
    ``.devcontainer/.framework-version`` — this helper keeps tests honest by
    producing the same shape ``corectl test init`` writes to disk. Pass
    ``include_framework_markers=False`` to simulate a stale uploader.
    """
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        def _add(name: str, content: bytes) -> None:
            info = tarfile.TarInfo(name=name)
            info.size = len(content)
            tar.addfile(info, io.BytesIO(content))

        if include_framework_markers:
            _add(".claude/.framework-version", b"0.12.0\n")
            _add(".devcontainer/.framework-version", b"0.12.0\n")
        # Throw in a placeholder concord.yaml so the tarball isn't empty
        # — keeps the bytes shape closer to a real upload without
        # invoking the stage extractor.
        _add("concord.yaml", b"schema: '1.0'\n")
    return buf.getvalue()


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
        """Direct RELEASED uploads are no longer supported — returns 400."""
        product = _product_obj()
        mock_db.product.find_first.return_value = product
        mock_db.product.find_unique.return_value = product

        data = {
            "package": (io.BytesIO(_tar_gz_data()), "package.tar.gz"),
            "manifest": json.dumps(_manifest()),
        }
        resp = authed_client.post(
            "/v2/products/alpha-b0/test-packages",
            data=data,
            content_type="multipart/form-data",
        )
        assert resp.status_code == 400
        body = resp.get_json()
        assert "no longer supported" in body["errors"][0]["message"].lower()

    def test_upload_success_development(self, authed_client, mock_db):
        """Upload a development package creates a new record when none exists."""
        product = _product_obj()
        tp = _test_package_obj(status="DEVELOPMENT", version="dev-abc123")
        mock_db.product.find_unique.return_value = product
        mock_db.product.find_first.return_value = product
        mock_db.testpackage.find_first.return_value = None
        mock_db.testpackage.create.return_value = tp
        mock_db.testpackage.find_unique.return_value = tp

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

    def test_upload_duplicate_dev_version_rejected(self, authed_client, mock_db):
        """v0.5.0+: duplicate dev version → 409 (no more silent overwrite).

        corectl always epoch-suffixes dev versions so the same SHA never
        collides on its own; a duplicate ``(productId, version, type)``
        reaching the upload handler is treated as a bug, not a normal
        re-upload.
        """
        product = _product_obj()
        existing = _test_package_obj(status="DEVELOPMENT", version="dev-abc123-1700000000")

        mock_db.product.find_unique.return_value = product
        mock_db.product.find_first.return_value = product
        mock_db.testpackage.find_first.return_value = existing

        data = {
            "package": (io.BytesIO(_tar_gz_data()), "package.tar.gz"),
            "manifest": json.dumps(_manifest(status="DEVELOPMENT", version="dev-abc123-1700000000")),
        }
        resp = authed_client.post(
            "/v2/products/alpha-b0/test-packages",
            data=data,
            content_type="multipart/form-data",
        )
        assert resp.status_code == 409
        mock_db.testpackage.create.assert_not_called()
        mock_db.testpackage.update.assert_not_called()

    def test_upload_two_phase_creates_uploading_placeholder_first(
        self, authed_client, mock_db, _mock_storage,
    ):
        """Two-phase commit: placeholder row created BEFORE the MinIO put.

        Order matters — if the row landed after the upload, a crash
        between put and create would leave an orphan blob nobody owns.
        Asserts the create call (status=UPLOADING) precedes the storage
        put_object call in the call timeline.
        """
        product = _product_obj()
        placeholder = _test_package_obj(
            id="tp-new", status="UPLOADING", version="dev-foo-100", storageKey=None,
        )
        mock_db.product.find_unique.return_value = product
        mock_db.product.find_first.return_value = product
        mock_db.testpackage.find_first.return_value = None
        mock_db.testpackage.create.return_value = placeholder
        mock_db.testpackage.find_unique.return_value = _test_package_obj(
            id="tp-new", status="DEVELOPMENT", version="dev-foo-100",
        )

        data = {
            "package": (io.BytesIO(_tar_gz_data()), "package.tar.gz"),
            "manifest": json.dumps(_manifest(status="DEVELOPMENT", version="dev-foo-100")),
        }
        resp = authed_client.post(
            "/v2/products/alpha-b0/test-packages",
            data=data,
            content_type="multipart/form-data",
        )
        assert resp.status_code == 201, resp.get_json()

        # Placeholder was created with status=UPLOADING and no storageKey.
        create_data = mock_db.testpackage.create.call_args.kwargs["data"]
        assert create_data["status"] == "UPLOADING"
        assert create_data["storageKey"] is None

        # MinIO put happened.
        assert _mock_storage.put_object.called

        # Two updates after the put: first stamps storageKey while status
        # is still UPLOADING, then flips status to DEVELOPMENT once stage
        # extraction + joined re-fetch succeed (the new two-phase commit
        # gates public visibility on stage metadata being written first).
        update_calls = mock_db.testpackage.update.call_args_list
        key_writes = [
            c for c in update_calls
            if c.kwargs.get("data", {}).get("storageKey") is not None
        ]
        assert key_writes, "expected an update stamping storageKey"
        flip_calls = [
            c for c in update_calls
            if c.kwargs.get("data", {}).get("status") == "DEVELOPMENT"
        ]
        assert flip_calls, "expected an update flipping status=DEVELOPMENT"
        # The key write must happen before (or with) the flip — never after.
        key_idx = update_calls.index(key_writes[0])
        flip_idx = update_calls.index(flip_calls[0])
        assert key_idx <= flip_idx, "storageKey must be set no later than the flip"

    def test_upload_storage_failure_leaves_uploading_placeholder(
        self, authed_client, mock_db, _mock_storage,
    ):
        """MinIO failure → placeholder stays in UPLOADING for retention to reap."""
        product = _product_obj()
        placeholder = _test_package_obj(
            id="tp-stuck", status="UPLOADING", version="dev-broken-1", storageKey=None,
        )
        mock_db.product.find_unique.return_value = product
        mock_db.product.find_first.return_value = product
        mock_db.testpackage.find_first.return_value = None
        mock_db.testpackage.create.return_value = placeholder

        # MinIO put raises.
        _mock_storage.put_object.side_effect = RuntimeError("minio-down")

        data = {
            "package": (io.BytesIO(_tar_gz_data()), "package.tar.gz"),
            "manifest": json.dumps(_manifest(status="DEVELOPMENT", version="dev-broken-1")),
        }
        resp = authed_client.post(
            "/v2/products/alpha-b0/test-packages",
            data=data,
            content_type="multipart/form-data",
        )
        assert resp.status_code == 500
        # Placeholder was NOT flipped — no update with status=DEVELOPMENT.
        flips = [
            c for c in mock_db.testpackage.update.call_args_list
            if c.kwargs.get("data", {}).get("status") == "DEVELOPMENT"
        ]
        assert not flips, "placeholder should remain UPLOADING after upload failure"

    def test_upload_reuses_stuck_uploading_placeholder(
        self, authed_client, mock_db, _mock_storage,
    ):
        """Retry of a stuck UPLOADING placeholder is allowed (not 409)."""
        product = _product_obj()
        stuck = _test_package_obj(
            id="tp-stuck-1", status="UPLOADING", version="dev-retry-1", storageKey=None,
        )
        mock_db.product.find_unique.return_value = product
        mock_db.product.find_first.return_value = product
        mock_db.testpackage.find_first.return_value = stuck
        mock_db.testpackage.find_unique.return_value = _test_package_obj(
            id="tp-stuck-1", status="DEVELOPMENT", version="dev-retry-1",
        )

        data = {
            "package": (io.BytesIO(_tar_gz_data()), "package.tar.gz"),
            "manifest": json.dumps(_manifest(status="DEVELOPMENT", version="dev-retry-1")),
        }
        resp = authed_client.post(
            "/v2/products/alpha-b0/test-packages",
            data=data,
            content_type="multipart/form-data",
        )
        assert resp.status_code == 201, resp.get_json()
        # No second create call — reused the placeholder.
        mock_db.testpackage.create.assert_not_called()
        # Status got flipped on the existing placeholder.
        flips = [
            c for c in mock_db.testpackage.update.call_args_list
            if c.kwargs.get("data", {}).get("status") == "DEVELOPMENT"
        ]
        assert flips

    def test_upload_released_version_rejected(self, authed_client, mock_db):
        """Upload a released package is always rejected (must upload as dev, then promote)."""
        product = _product_obj()
        mock_db.product.find_unique.return_value = product
        mock_db.product.find_first.return_value = product

        data = {
            "package": (io.BytesIO(_tar_gz_data()), "package.tar.gz"),
            "manifest": json.dumps(_manifest()),
        }
        resp = authed_client.post(
            "/v2/products/alpha-b0/test-packages",
            data=data,
            content_type="multipart/form-data",
        )
        assert resp.status_code == 400

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
        mock_db.product.find_unique.return_value = product
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
        mock_db.product.find_unique.return_value = product
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
        mock_db.product.find_unique.return_value = product
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
        mock_db.product.find_unique.return_value = product
        mock_db.product.find_first.return_value = product
        mock_db.testpackage.find_first.return_value = tp

        resp = authed_client.get("/v2/products/alpha-b0/test-packages/latest")
        body = resp.get_json()
        data = body["data"]

        # ``stagesEnabled``, ``schemaVersion``, and ``gitDirty`` were dropped
        # in v0.5.0 (test-package refactor). ``manifestVersion`` replaced
        # ``schemaVersion`` and is the new canonical field.
        expected_fields = [
            "id", "productId", "boardRevisionId", "version", "type", "status",
            "frameworkVersion", "testCount", "manifestVersion",
            "manifestHash", "notes", "createdAt", "updatedAt",
        ]
        for field in expected_fields:
            assert field in data, f"Missing field: {field}"

    def test_serialization_iso_dates(self, authed_client, mock_db):
        """Serialized dates are ISO 8601 format."""
        product = _product_obj()
        tp = _test_package_obj()
        mock_db.product.find_unique.return_value = product
        mock_db.product.find_first.return_value = product
        mock_db.testpackage.find_first.return_value = tp

        resp = authed_client.get("/v2/products/alpha-b0/test-packages/latest")
        body = resp.get_json()
        data = body["data"]
        assert data["createdAt"] == "2026-03-31T12:00:00+00:00"
        assert data["updatedAt"] == "2026-03-31T12:00:00+00:00"


# ---------------------------------------------------------------------------
#  GET /v2/products/<product_id>/test-packages/<package_id> — Get Single
# ---------------------------------------------------------------------------

class TestGetTestPackage:
    """Tests for GET /v2/products/<product_id>/test-packages/<package_id>."""

    def test_get_success(self, authed_client, mock_db):
        """Get a single test package by ID returns 200 with package data."""
        product = _product_obj()
        tp = _test_package_obj(id="tp-001", version="1.0.0")
        mock_db.product.find_unique.return_value = product
        mock_db.product.find_first.return_value = product
        mock_db.testpackage.find_first.return_value = tp

        resp = authed_client.get("/v2/products/alpha-b0/test-packages/tp-001")
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["data"]["id"] == "tp-001"
        assert body["data"]["version"] == "1.0.0"

    def test_get_not_found(self, authed_client, mock_db):
        """Get a non-existent package returns 404."""
        product = _product_obj()
        mock_db.product.find_unique.return_value = product
        mock_db.product.find_first.return_value = product
        mock_db.testpackage.find_first.return_value = None

        resp = authed_client.get("/v2/products/alpha-b0/test-packages/tp-nonexistent")
        assert resp.status_code == 404

    def test_get_product_not_found(self, authed_client, mock_db):
        """Get package for non-existent product returns 404."""
        mock_db.product.find_unique.return_value = None
        mock_db.product.find_first.return_value = None

        resp = authed_client.get("/v2/products/nonexistent/test-packages/tp-001")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
#  DELETE /v2/products/<product_id>/test-packages/<package_id> — Delete
# ---------------------------------------------------------------------------

class TestDeleteTestPackage:
    """Tests for DELETE /v2/products/<product_id>/test-packages/<package_id>."""

    def test_delete_success(self, authed_client, mock_db):
        """Delete a development package succeeds with 200."""
        product = _product_obj()
        tp = _test_package_obj(status="DEVELOPMENT", version="dev-abc123")
        mock_db.product.find_unique.return_value = product
        mock_db.product.find_first.return_value = product
        mock_db.testpackage.find_first.return_value = tp
        mock_db.testrun.count.return_value = 0

        with patch("api.v2.products.test_packages.log_audit"):
            resp = authed_client.delete("/v2/products/alpha-b0/test-packages/tp-001")

        assert resp.status_code == 200
        body = resp.get_json()
        assert body["data"]["deleted"] is True
        mock_db.testpackagestage.delete_many.assert_called_once()
        mock_db.testpackage.delete.assert_called_once()

    def test_delete_released_rejected(self, authed_client, mock_db):
        """Delete a released package returns 409 conflict."""
        product = _product_obj()
        tp = _test_package_obj(status="RELEASED")
        mock_db.product.find_unique.return_value = product
        mock_db.product.find_first.return_value = product
        mock_db.testpackage.find_first.return_value = tp

        resp = authed_client.delete("/v2/products/alpha-b0/test-packages/tp-001")
        assert resp.status_code == 409
        body = resp.get_json()
        assert "immutable" in body["errors"][0]["message"].lower()

    def test_delete_referenced_by_test_runs(self, authed_client, mock_db):
        """Delete a package referenced by test runs returns 409."""
        product = _product_obj()
        tp = _test_package_obj(status="DEVELOPMENT")
        mock_db.product.find_unique.return_value = product
        mock_db.product.find_first.return_value = product
        mock_db.testpackage.find_first.return_value = tp
        mock_db.testrun.count.return_value = 3

        resp = authed_client.delete("/v2/products/alpha-b0/test-packages/tp-001")
        assert resp.status_code == 409
        body = resp.get_json()
        assert "3 test run(s)" in body["errors"][0]["message"]

    def test_delete_product_not_found(self, authed_client, mock_db):
        """Delete package for non-existent product returns 404."""
        mock_db.product.find_unique.return_value = None
        mock_db.product.find_first.return_value = None

        resp = authed_client.delete("/v2/products/nonexistent/test-packages/tp-001")
        assert resp.status_code == 404

    def test_delete_package_not_found(self, authed_client, mock_db):
        """Delete non-existent package returns 404."""
        product = _product_obj()
        mock_db.product.find_unique.return_value = product
        mock_db.product.find_first.return_value = product
        mock_db.testpackage.find_first.return_value = None

        resp = authed_client.delete("/v2/products/alpha-b0/test-packages/tp-nonexistent")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
#  POST /v2/products/<product_id>/test-packages/<package_id>/release — Release
# ---------------------------------------------------------------------------

class TestReleaseTestPackage:
    """Tests for POST /v2/products/<product_id>/test-packages/<package_id>/release."""

    def _setup_release_mocks(self, mock_db, product, tp, latest_released=None):
        """Set up common mocks for release tests."""
        mock_db.product.find_unique.return_value = product
        mock_db.product.find_first.return_value = product
        # find_first is called multiple times: once for the package, once for latest released
        mock_db.testpackage.find_first.side_effect = [tp, latest_released]

    def test_release_success_strips_dev_prefix(self, authed_client, mock_db, _mock_storage):
        """v0.5.0+: release strips ``dev-`` from the version string.

        ``dev-abc123-1700000000`` → ``releasedVersion=abc123-1700000000``.
        Replaces the old auto-bump-minor heuristic which produced
        confusing results once existing rows had non-semver versions.
        """
        product = _product_obj()
        tp = _test_package_obj(
            status="DEVELOPMENT",
            version="dev-abc123-1700000000",
            storageKey="test-packages/alpha-b0/validation/dev-abc123-1700000000/package.tar.gz",
            packageStages=[],
            testBedDesign=None,
        )
        released_tp = _test_package_obj(
            status="RELEASED",
            version="dev-abc123-1700000000",
            releasedVersion="abc123-1700000000",
            releasedAt=_now(),
            releasedById="test-user-id",
            packageStages=[],
            testBedDesign=None,
        )

        self._setup_release_mocks(mock_db, product, tp, latest_released=None)
        mock_db.testpackage.update.return_value = released_tp
        mock_db.testpackage.find_unique.return_value = released_tp

        with patch("api.v2.products.test_packages.log_audit"):
            resp = authed_client.post("/v2/products/alpha-b0/test-packages/tp-001/release")

        assert resp.status_code == 200
        body = resp.get_json()
        assert body["data"]["status"] == "RELEASED"
        assert body["data"]["releasedVersion"] == "abc123-1700000000"

        update_call = mock_db.testpackage.update.call_args_list[0]
        assert update_call[1]["data"]["releasedVersion"] == "abc123-1700000000"
        assert update_call[1]["data"]["status"] == "RELEASED"

    def test_release_success_explicit_version(self, authed_client, mock_db, _mock_storage):
        """Caller-supplied ``releasedVersion`` overrides the dev-prefix-strip default."""
        product = _product_obj()
        tp = _test_package_obj(
            status="DEVELOPMENT",
            version="dev-xyz789-1700000000",
            storageKey="test-packages/alpha-b0/validation/dev-xyz789-1700000000/package.tar.gz",
            packageStages=[],
            testBedDesign=None,
        )
        released_tp = _test_package_obj(
            status="RELEASED",
            version="dev-xyz789-1700000000",
            releasedVersion="2.4.0",
            releasedAt=_now(),
            releasedById="test-user-id",
            packageStages=[],
            testBedDesign=None,
        )

        self._setup_release_mocks(mock_db, product, tp, latest_released=None)
        mock_db.testpackage.update.return_value = released_tp
        mock_db.testpackage.find_unique.return_value = released_tp

        with patch("api.v2.products.test_packages.log_audit"):
            resp = authed_client.post(
                "/v2/products/alpha-b0/test-packages/tp-001/release",
                data=json.dumps({"releasedVersion": "2.4.0"}),
                content_type="application/json",
            )

        assert resp.status_code == 200
        body = resp.get_json()
        assert body["data"]["releasedVersion"] == "2.4.0"

        update_call = mock_db.testpackage.update.call_args_list[0]
        assert update_call[1]["data"]["releasedVersion"] == "2.4.0"

    def test_release_already_released(self, authed_client, mock_db):
        """Release an already-released package returns 409."""
        product = _product_obj()
        tp = _test_package_obj(
            status="RELEASED",
            releasedVersion="1.0.0",
            packageStages=[],
        )
        mock_db.product.find_unique.return_value = product
        mock_db.product.find_first.return_value = product
        mock_db.testpackage.find_first.return_value = tp

        resp = authed_client.post("/v2/products/alpha-b0/test-packages/tp-001/release")
        assert resp.status_code == 409
        body = resp.get_json()
        assert "already been released" in body["errors"][0]["message"].lower()

    def test_release_package_not_found(self, authed_client, mock_db):
        """Release non-existent package returns 404."""
        product = _product_obj()
        mock_db.product.find_unique.return_value = product
        mock_db.product.find_first.return_value = product
        mock_db.testpackage.find_first.return_value = None

        resp = authed_client.post("/v2/products/alpha-b0/test-packages/tp-nonexistent/release")
        assert resp.status_code == 404

    def test_release_product_not_found(self, authed_client, mock_db):
        """Release package for non-existent product returns 404."""
        mock_db.product.find_unique.return_value = None
        mock_db.product.find_first.return_value = None

        resp = authed_client.post("/v2/products/nonexistent/test-packages/tp-001/release")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
#  _bump_minor — Unit Tests
# ---------------------------------------------------------------------------

# ``_bump_minor`` was removed in v0.5.0 — the release endpoint now strips
# the ``dev-`` prefix from the dev version (or accepts an explicit
# ``releasedVersion`` from the caller) instead of synthesizing a semver.
# See ``test_release_success_first_release`` / ``_dev_prefix_strip`` for
# the new behavior.
