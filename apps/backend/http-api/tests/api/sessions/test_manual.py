"""Tests for sessions/manual.py — run_tests endpoint and create_k8s_job_name helper."""

from __future__ import annotations

import io
import os
import zipfile
from unittest.mock import MagicMock, patch

import pytest

from api.v2.sessions.manual import create_k8s_job_name


# ---------------------------------------------------------------------------
# TestCreateK8sJobName — pure unit tests, no Flask needed
# ---------------------------------------------------------------------------

class TestCreateK8sJobName:
    """Tests for create_k8s_job_name() helper."""

    def test_basic_name_is_rfc1123_compliant(self):
        """Basic product + job_id produces valid RFC 1123 name."""
        job_id = "a1b2c3d4-e5f6-7890-abcd-ef1234567890-electrical"
        name = create_k8s_job_name("alpha", job_id)
        assert len(name) <= 63
        assert name[0].isalnum()
        assert name[-1].isalnum()
        assert name == name.lower()

    def test_product_with_spaces_sanitized(self):
        """Spaces in product name are replaced with hyphens."""
        job_id = "aaaa1111-bbbb2222-cccc3333-dddd4444-electrical"
        name = create_k8s_job_name("Alpha B0 Board", job_id)
        assert " " not in name
        assert len(name) <= 63

    def test_product_with_underscores_sanitized(self):
        """Underscores in product name are replaced with hyphens."""
        job_id = "aaaa1111-bbbb2222-cccc3333-dddd4444-smoke"
        name = create_k8s_job_name("alpha_b0", job_id)
        assert "_" not in name

    def test_version_suffix_included(self):
        """Firmware version is normalized and appended."""
        job_id = "aaaa1111-bbbb2222-cccc3333-dddd4444-app-post"
        name = create_k8s_job_name("alpha", job_id, firmware_version="0.8.3")
        assert "0-8-3" in name or "0.8.3".replace(".", "-") in name

    def test_max_length_enforced(self):
        """Result never exceeds 63 characters regardless of input length."""
        long_product = "very-long-product-name-that-exceeds-reasonable-length"
        job_id = "aaaa1111-bbbb2222-cccc3333-dddd4444-long-test-name"
        name = create_k8s_job_name(long_product, job_id, firmware_version="1.23.456")
        assert len(name) <= 63

    @pytest.mark.parametrize("product,job_id", [
        ("alpha", "short-id"),
        ("sigma5", "a1b2c3d4-e5f6-7890-abcd-ef1234567890-fuota"),
        ("alpha-b0", "deadbeef-1234-5678-abcd-ef0123456789-comm-post"),
    ])
    def test_always_starts_and_ends_with_alnum(self, product, job_id):
        """Job name always starts and ends with an alphanumeric character."""
        name = create_k8s_job_name(product, job_id)
        assert name[0].isalnum(), f"Starts with non-alnum: {name!r}"
        assert name[-1].isalnum(), f"Ends with non-alnum: {name!r}"


# ---------------------------------------------------------------------------
# TestRunTests — endpoint tests
# ---------------------------------------------------------------------------

def _make_valid_zip(tmp_path) -> bytes:
    """Create a minimal valid zip archive with a version folder."""
    zf_path = tmp_path / "fw.zip"
    with zipfile.ZipFile(zf_path, "w") as zf:
        # Add a version-like folder entry using writestr (Python 3.10 compatible)
        zf.writestr("0.8.3/", "")
        zf.writestr("0.8.3/app_nrf52840.hex", ":100000\n")
    return zf_path.read_bytes()


@pytest.fixture(autouse=True)
def _mock_logger():
    """Mock get_logger() so it returns a real logger object instead of None."""
    import logging
    with patch("api.v2.sessions.manual.get_logger", return_value=logging.getLogger("test")):
        yield


class TestRunTests:
    """Tests for POST /v2/sessions/manual/run — manual firmware upload."""

    def test_run_tests_no_file_returns_400(self, authed_client):
        """POST without file field returns 400."""
        resp = authed_client.post(
            "/v2/sessions/manual/run",
            data={"product": "alpha"},
            content_type="multipart/form-data",
        )
        assert resp.status_code == 400

    def test_run_tests_non_zip_file_returns_400(self, authed_client):
        """POST with non-zip file extension returns 400."""
        resp = authed_client.post(
            "/v2/sessions/manual/run",
            data={
                "file": (io.BytesIO(b"not a zip"), "firmware.tar.gz"),
                "product": "alpha",
            },
            content_type="multipart/form-data",
        )
        assert resp.status_code == 400

    def test_run_tests_invalid_zip_returns_400(self, authed_client):
        """POST with corrupt zip data returns 400."""
        resp = authed_client.post(
            "/v2/sessions/manual/run",
            data={
                "file": (io.BytesIO(b"this is not a real zip file"), "firmware.zip"),
                "product": "alpha",
            },
            content_type="multipart/form-data",
        )
        assert resp.status_code == 400

    def test_run_tests_missing_product_returns_400(self, authed_client, tmp_path):
        """POST valid zip but without product form field returns 400."""
        zip_bytes = _make_valid_zip(tmp_path)
        resp = authed_client.post(
            "/v2/sessions/manual/run",
            data={
                "file": (io.BytesIO(zip_bytes), "firmware.zip"),
                # no product field
            },
            content_type="multipart/form-data",
        )
        assert resp.status_code == 400

    def test_run_tests_success_with_k8s_mocked(self, authed_client, tmp_path):
        """POST valid zip with product creates K8s jobs and returns 201."""
        zip_bytes = _make_valid_zip(tmp_path)

        mock_storage = MagicMock()

        with patch("api.v2.sessions.manual.get_storage_client", return_value=mock_storage):
            with patch("api.v2.sessions.manual.get_bucket_name", return_value="test-bucket"):
                with patch("api.v2.sessions.manual.create_kubernetes_job", return_value="alpha-val-job1") as mock_k8s:
                    with patch("api.v2.sessions.manual.log_audit"):
                        resp = authed_client.post(
                            "/v2/sessions/manual/run",
                            data={
                                "file": (io.BytesIO(zip_bytes), "firmware.zip"),
                                "product": "alpha",
                            },
                            content_type="multipart/form-data",
                        )

        assert resp.status_code == 201
        body = resp.get_json()
        assert body["data"]["product"] == "alpha"
        assert len(body["data"]["jobs"]) == 3  # electrical, app_post, comm_post
        assert mock_k8s.call_count == 3

    def test_run_tests_k8s_failure_still_returns_201(self, authed_client, tmp_path):
        """POST where K8s job creation fails records FAILED status but still returns 201."""
        zip_bytes = _make_valid_zip(tmp_path)

        mock_storage = MagicMock()

        with patch("api.v2.sessions.manual.get_storage_client", return_value=mock_storage):
            with patch("api.v2.sessions.manual.get_bucket_name", return_value="test-bucket"):
                with patch("api.v2.sessions.manual.create_kubernetes_job", return_value=None):
                    with patch("api.v2.sessions.manual.log_audit"):
                        resp = authed_client.post(
                            "/v2/sessions/manual/run",
                            data={
                                "file": (io.BytesIO(zip_bytes), "firmware.zip"),
                                "product": "alpha",
                            },
                            content_type="multipart/form-data",
                        )

        assert resp.status_code == 201
        body = resp.get_json()
        failed = [j for j in body["data"]["jobs"] if j["status"] == "FAILED"]
        assert len(failed) == 3

    # TODO: test_run_tests_zip_path_traversal_returns_400
    # TODO: test_run_tests_storage_upload_failure_returns_error
    # TODO: test_run_tests_empty_filename_returns_400
