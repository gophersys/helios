"""Tests for services/builds/job_runner.py — K8s job creation and entrypoint script."""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from tests.conftest import make_obj


# ---------------------------------------------------------------------------
# create_build_k8s_job
# ---------------------------------------------------------------------------

class TestCreateBuildK8sJob:
    """Tests for create_build_k8s_job()."""

    def _make_job(self, **overrides):
        defaults = dict(
            id="job-12345678",
            product=make_obj(id="prod-1", name="Alpha B0", slug="alpha_b0",
                             builderImage="registry.io/alpha-builder:latest",
                             fwRepoSlug="alpha_fw"),
            webhookData={
                "repoUrl": "git@bitbucket.org:ck/alpha_fw.git",
                "builderImage": "registry.io/alpha-builder:latest",
            },
            matrixLabel="smoke_app_debug",
            branch="main",
            board="alpha_b0",
            variant="release",
            target="app",
            versionBump=False,
            buildNum=5,
            configFlags=None,
        )
        defaults.update(overrides)
        return make_obj(**defaults)

    @patch("src.services.builds.job_runner.get_db_client")
    def test_returns_none_when_job_not_found(self, mock_get_db):
        """Returns None when BuildJob not found in DB."""
        from src.services.builds.job_runner import create_build_k8s_job

        db = MagicMock()
        mock_get_db.return_value = db
        db.buildjob.find_unique.return_value = None

        result = create_build_k8s_job("missing-id")
        assert result is None

    @patch("src.services.builds.job_runner.get_db_client")
    def test_returns_none_when_no_repo_url(self, mock_get_db):
        """Returns None when job has no repoUrl."""
        from src.services.builds.job_runner import create_build_k8s_job

        db = MagicMock()
        mock_get_db.return_value = db
        db.buildjob.find_unique.return_value = self._make_job(
            webhookData={"repoUrl": "", "builderImage": "img:latest"},
        )

        result = create_build_k8s_job("job-1")
        assert result is None

    @patch("src.services.builds.job_runner.get_db_client")
    def test_returns_none_when_no_builder_image(self, mock_get_db):
        """Returns None when no builder image can be determined."""
        from src.services.builds.job_runner import create_build_k8s_job

        db = MagicMock()
        mock_get_db.return_value = db
        db.buildjob.find_unique.return_value = self._make_job(
            webhookData={"repoUrl": "git@bb.org:ck/fw.git", "builderImage": ""},
            product=make_obj(id="p-1", name="X", slug="x",
                             builderImage=None, fwRepoSlug=None),
        )

        result = create_build_k8s_job("job-1")
        assert result is None

    @patch("src.services.builds.job_runner.get_k8s_client")
    @patch("src.services.builds.job_runner.get_db_client")
    def test_fallback_builder_image_from_product(self, mock_get_db, mock_get_k8s):
        """Falls back to product.builderImage when webhookData has none."""
        from src.services.builds.job_runner import create_build_k8s_job

        db = MagicMock()
        mock_get_db.return_value = db

        product = make_obj(id="p-1", name="Alpha", slug="alpha",
                           builderImage="registry.io/fallback:v1",
                           fwRepoSlug="alpha_fw")
        db.buildjob.find_unique.return_value = self._make_job(
            webhookData={"repoUrl": "git@bb.org:ck/fw.git", "builderImage": ""},
            product=product,
        )
        db.user.find_first.return_value = make_obj(id="sys-1")
        db.secret.find_unique.return_value = None

        mock_k8s_client = MagicMock()
        mock_get_k8s.return_value = mock_k8s_client
        mock_batch_v1 = MagicMock()
        mock_k8s_api = MagicMock()
        mock_k8s_api.BatchV1Api.return_value = mock_batch_v1

        with patch.dict(sys.modules, {
            "kubernetes": MagicMock(),
            "kubernetes.client": mock_k8s_api,
        }):
            result = create_build_k8s_job("job-12345678")

        assert result is not None

    @patch("src.services.builds.job_runner.get_k8s_client")
    @patch("src.services.builds.job_runner.get_db_client")
    def test_k8s_client_not_available(self, mock_get_db, mock_get_k8s):
        """Returns None when K8s client is not available."""
        from src.services.builds.job_runner import create_build_k8s_job

        db = MagicMock()
        mock_get_db.return_value = db
        db.buildjob.find_unique.return_value = self._make_job()
        db.user.find_first.return_value = make_obj(id="sys-1")
        db.secret.find_unique.return_value = None

        mock_get_k8s.return_value = None

        with patch.dict(sys.modules, {
            "kubernetes": MagicMock(),
            "kubernetes.client": MagicMock(),
        }):
            result = create_build_k8s_job("job-12345678")

        assert result is None

    @patch("src.services.builds.job_runner.get_k8s_client")
    @patch("src.services.builds.job_runner.get_db_client")
    def test_k8s_exception_returns_none(self, mock_get_db, mock_get_k8s):
        """Returns None when K8s job creation throws an exception."""
        from src.services.builds.job_runner import create_build_k8s_job

        db = MagicMock()
        mock_get_db.return_value = db
        db.buildjob.find_unique.return_value = self._make_job()
        db.user.find_first.return_value = make_obj(id="sys-1")
        db.secret.find_unique.return_value = None

        mock_get_k8s.return_value = MagicMock()

        # Build a mock kubernetes module that raises on create_namespaced_job
        mock_k8s_client_mod = MagicMock()
        batch_mock = MagicMock()
        batch_mock.create_namespaced_job.side_effect = Exception("K8s error")
        mock_k8s_client_mod.BatchV1Api.return_value = batch_mock

        mock_kubernetes = MagicMock()
        mock_kubernetes.client = mock_k8s_client_mod

        with patch.dict(sys.modules, {
            "kubernetes": mock_kubernetes,
            "kubernetes.client": mock_k8s_client_mod,
        }):
            result = create_build_k8s_job("job-12345678")

        assert result is None

    @patch("src.services.builds.job_runner.get_k8s_client")
    @patch("src.services.builds.job_runner.get_db_client")
    def test_signing_key_lookup(self, mock_get_db, mock_get_k8s):
        """Signing key is looked up when signingKeyId is provided."""
        from src.services.builds.job_runner import create_build_k8s_job

        db = MagicMock()
        mock_get_db.return_value = db
        db.buildjob.find_unique.return_value = self._make_job(
            webhookData={
                "repoUrl": "git@bb.org:ck/fw.git",
                "builderImage": "img:latest",
                "signingKeyId": "secret-1",
            },
        )
        db.user.find_first.return_value = make_obj(id="sys-1")
        db.secret.find_unique.return_value = make_obj(value="base64encodedkey==")

        mock_get_k8s.return_value = MagicMock()
        mock_k8s_api = MagicMock()
        mock_batch_v1 = MagicMock()
        mock_k8s_api.BatchV1Api.return_value = mock_batch_v1

        with patch.dict(sys.modules, {
            "kubernetes": MagicMock(),
            "kubernetes.client": mock_k8s_api,
        }):
            result = create_build_k8s_job("job-12345678")

        assert result is not None
        db.secret.find_unique.assert_called_once_with(where={"id": "secret-1"})


# ---------------------------------------------------------------------------
# _build_entrypoint_script
# ---------------------------------------------------------------------------

class TestBuildEntrypointScript:
    """Tests for _build_entrypoint_script()."""

    def test_script_contains_key_sections(self):
        """Entrypoint script contains all required sections."""
        from src.services.builds.job_runner import _build_entrypoint_script

        script = _build_entrypoint_script()

        assert "git clone" in script
        assert "CONCORD_API_URL" in script
        assert "SIGNING_KEY" in script
        assert "Build Complete" in script
        assert "set -eo pipefail" in script

    def test_script_handles_artifact_upload(self):
        """Entrypoint script includes artifact upload loop."""
        from src.services.builds.job_runner import _build_entrypoint_script

        script = _build_entrypoint_script()

        assert "artifacts" in script
        assert "ARTIFACT_TYPE" in script
        assert "encryptedCfw" in script
