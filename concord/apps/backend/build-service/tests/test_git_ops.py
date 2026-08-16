"""Tests for GitOps — repo config loading, build script fetching, overlay
extraction, clone logic, and builder image resolution.

All subprocess.run / requests calls are mocked so no network or git is needed.
"""

from __future__ import annotations

import json
import subprocess
import tarfile
from io import BytesIO
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.worker.git_ops import GitOps


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def api_client() -> MagicMock:
    """Minimal mock of ConcordClient."""
    m = MagicMock()
    m.api_url = "https://test.concord.local"
    m._headers.return_value = {"Authorization": "Bearer test"}
    m.api_get.return_value = None
    m.stream_log_chunk.return_value = None
    return m


@pytest.fixture
def git_ops(api_client) -> GitOps:
    """GitOps instance with a mocked API client."""
    return GitOps(ssh_key_path="/root/.ssh/id_rsa", api_client=api_client)


# ---------------------------------------------------------------------------
# _load_repo_configs
# ---------------------------------------------------------------------------

class TestLoadRepoConfigs:
    """Tests for GitOps._load_repo_configs()."""

    def test_load_repo_configs_parses_response(self, git_ops, api_client):
        """Populates _repo_configs from API response."""
        api_client.api_get.return_value = {
            "data": [
                {
                    "id": "alpha_fw",
                    "sshUrl": "git@bitbucket.org:corekinect/alpha_fw.git",
                    "buildScript": "scripts/build.sh",
                    "ncsVersion": "2.7.0",
                }
            ]
        }
        result = git_ops._load_repo_configs()
        assert result is True
        assert "alpha_fw" in git_ops._repo_configs
        assert git_ops._repo_configs["alpha_fw"]["ssh_url"] == "git@bitbucket.org:corekinect/alpha_fw.git"
        assert git_ops._configs_loaded is True

    def test_load_repo_configs_returns_false_on_api_error(self, git_ops, api_client):
        """Returns False and does not set _configs_loaded when API fails."""
        api_client.api_get.return_value = None
        result = git_ops._load_repo_configs()
        assert result is False

    def test_load_repo_configs_returns_false_on_empty_data(self, git_ops, api_client):
        """Returns False when API returns data=None."""
        api_client.api_get.return_value = {"data": None}
        result = git_ops._load_repo_configs()
        assert result is False

    def test_load_repo_configs_uses_name_as_fallback_slug(self, git_ops, api_client):
        """Uses 'name' field as slug when 'id' is absent."""
        api_client.api_get.return_value = {
            "data": [
                {"name": "alpha_mfg_fw", "sshUrl": "git@bitbucket.org:ck/alpha_mfg_fw.git"}
            ]
        }
        git_ops._load_repo_configs()
        assert "alpha_mfg_fw" in git_ops._repo_configs


# ---------------------------------------------------------------------------
# _get_repo_config
# ---------------------------------------------------------------------------

class TestGetRepoConfig:
    """Tests for GitOps._get_repo_config()."""

    def test_get_repo_config_triggers_load_when_not_loaded(self, git_ops, api_client):
        """Calls _load_repo_configs when _configs_loaded is False."""
        api_client.api_get.return_value = {
            "data": [{"id": "alpha_fw", "sshUrl": "ssh://example.com/alpha_fw"}]
        }
        config = git_ops._get_repo_config("alpha_fw")
        assert config is not None
        assert api_client.api_get.called

    def test_get_repo_config_refreshes_on_cache_miss(self, git_ops, api_client):
        """Attempts a second load if product is missing after initial load.

        The code calls _load_repo_configs() once on cache miss; on the
        second call the product becomes available.
        """
        # _configs_loaded starts False → first call triggers load (empty)
        # second automatic refresh finds the product
        api_client.api_get.side_effect = [
            {"data": []},
            {"data": [{"id": "new_product", "sshUrl": "ssh://example/new_product"}]},
        ]
        # _configs_loaded is False (default) — _get_repo_config will call
        # _load_repo_configs once, find nothing, then call it a second time.
        config = git_ops._get_repo_config("new_product")
        assert config is not None
        assert config["ssh_url"] == "ssh://example/new_product"


# ---------------------------------------------------------------------------
# fetch_build_script
# ---------------------------------------------------------------------------

class TestFetchBuildScript:
    """Tests for GitOps.fetch_build_script()."""

    def test_fetch_build_script_returns_content(self, git_ops, api_client):
        """Returns the content string from the API response."""
        api_client.api_get.return_value = {"data": {"content": "#!/bin/bash\necho ok"}}
        result = git_ops.fetch_build_script("alpha_fw")
        assert result == "#!/bin/bash\necho ok"

    def test_fetch_build_script_strips_fw_suffix_from_key(self, git_ops, api_client):
        """Strips _fw suffix when constructing the API path."""
        api_client.api_get.return_value = {"data": {"content": "# script"}}
        git_ops.fetch_build_script("alpha_fw")
        called_path = api_client.api_get.call_args[0][0]
        assert called_path.endswith("/alpha")

    def test_fetch_build_script_returns_none_on_error(self, git_ops, api_client):
        """Returns None when the API returns None."""
        api_client.api_get.return_value = None
        result = git_ops.fetch_build_script("alpha_fw")
        assert result is None

    def test_fetch_build_script_returns_none_when_no_data(self, git_ops, api_client):
        """Returns None when API response has no 'data' field."""
        api_client.api_get.return_value = {}
        result = git_ops.fetch_build_script("alpha_fw")
        assert result is None


# ---------------------------------------------------------------------------
# fetch_overlays
# ---------------------------------------------------------------------------

class TestFetchOverlays:
    """Tests for GitOps.fetch_overlays()."""

    def _make_tarball(self) -> bytes:
        """Build an in-memory tar.gz containing one test file."""
        buf = BytesIO()
        with tarfile.open(fileobj=buf, mode="w:gz") as tar:
            content = b"overlay content"
            info = tarfile.TarInfo(name="boards/my.conf")
            info.size = len(content)
            tar.addfile(info, BytesIO(content))
        return buf.getvalue()

    def test_fetch_overlays_extracts_tarball(self, git_ops, tmp_path):
        """Extracts tar.gz response content into dest_dir."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = self._make_tarball()

        with patch("src.worker.git_ops.requests.get", return_value=mock_resp):
            result = git_ops.fetch_overlays("alpha_fw", tmp_path / "overlays")

        assert result is True
        extracted = list((tmp_path / "overlays").rglob("*"))
        assert any(f.name == "my.conf" for f in extracted)

    def test_fetch_overlays_returns_false_on_404(self, git_ops, tmp_path):
        """Returns False when the API returns 404."""
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        with patch("src.worker.git_ops.requests.get", return_value=mock_resp):
            result = git_ops.fetch_overlays("alpha_fw", tmp_path / "overlays")
        assert result is False

    def test_fetch_overlays_returns_false_on_exception(self, git_ops, tmp_path):
        """Returns False gracefully when requests.get raises an exception."""
        with patch("src.worker.git_ops.requests.get", side_effect=Exception("network down")):
            result = git_ops.fetch_overlays("alpha_fw", tmp_path / "overlays")
        assert result is False

    def test_fetch_overlays_strips_fw_suffix_from_key(self, git_ops, tmp_path):
        """API path uses the stripped script key (e.g., 'alpha' not 'alpha_fw')."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = self._make_tarball()

        with patch("src.worker.git_ops.requests.get", return_value=mock_resp) as mock_get:
            git_ops.fetch_overlays("alpha_fw", tmp_path / "overlays")

        called_url = mock_get.call_args[0][0]
        assert "/overlays/alpha" in called_url
        assert "_fw" not in called_url


# ---------------------------------------------------------------------------
# clone_repo
# ---------------------------------------------------------------------------

class TestCloneRepo:
    """Tests for GitOps.clone_repo()."""

    def _success_run(self, *args, **kwargs):
        """Simulate successful subprocess.run result."""
        result = MagicMock()
        result.returncode = 0
        result.stderr = b""
        return result

    def test_clone_repo_returns_true_on_success(self, git_ops, tmp_path):
        """Returns True when all git commands succeed."""
        with patch("subprocess.run", side_effect=self._success_run):
            result = git_ops.clone_repo("alpha_fw", tmp_path / "alpha_fw", branch="main")
        assert result is True

    def test_clone_repo_returns_false_on_git_failure(self, git_ops, tmp_path):
        """Returns False when git clone raises CalledProcessError."""
        with patch("subprocess.run", side_effect=subprocess.CalledProcessError(
            1, "git", stderr=b"fatal: not found"
        )):
            result = git_ops.clone_repo("alpha_fw", tmp_path / "alpha_fw")
        assert result is False

    def test_clone_repo_uses_config_ssh_url_when_available(self, git_ops, tmp_path, api_client):
        """Uses the SSH URL from repo config rather than the default pattern."""
        api_client.api_get.return_value = {
            "data": [{"id": "alpha_fw", "sshUrl": "git@custom.host:alpha_fw.git"}]
        }
        git_ops._load_repo_configs()

        calls = []
        def capture_run(cmd, **kwargs):
            calls.append(cmd)
            r = MagicMock()
            r.returncode = 0
            r.stderr = b""
            return r

        with patch("subprocess.run", side_effect=capture_run):
            git_ops.clone_repo("alpha_fw", tmp_path / "alpha_fw")

        clone_call = next(c for c in calls if "clone" in c)
        assert "git@custom.host:alpha_fw.git" in clone_call

    def test_clone_repo_falls_back_to_bitbucket_url_when_no_config(self, git_ops, tmp_path):
        """Falls back to Bitbucket SSH URL pattern when no config available."""
        git_ops._configs_loaded = True  # skip API call
        git_ops._repo_configs = {}

        calls = []
        def capture_run(cmd, **kwargs):
            calls.append(cmd)
            r = MagicMock()
            r.returncode = 0
            r.stderr = b""
            return r

        with patch("subprocess.run", side_effect=capture_run):
            git_ops.clone_repo("my_repo", tmp_path / "my_repo")

        clone_call = next(c for c in calls if "clone" in c)
        assert "bitbucket.org" in " ".join(clone_call)

    def test_clone_repo_returns_false_on_exception(self, git_ops, tmp_path):
        """Returns False gracefully when an unexpected exception occurs."""
        with patch("subprocess.run", side_effect=RuntimeError("disk full")):
            result = git_ops.clone_repo("alpha_fw", tmp_path / "alpha_fw")
        assert result is False

    def test_clone_repo_streams_log_when_job_id_provided(self, git_ops, tmp_path, api_client):
        """Streams clone output to the API when job_id is provided."""
        with patch("subprocess.run", side_effect=self._success_run):
            git_ops.clone_repo("alpha_fw", tmp_path / "alpha_fw", job_id="job-xyz")

        assert api_client.stream_log_chunk.called


# ---------------------------------------------------------------------------
# check_ncs_version / get_builder_image
# ---------------------------------------------------------------------------

class TestBuilderImageResolution:
    """Tests for GitOps.get_builder_image() and check_ncs_version()."""

    def test_get_builder_image_returns_image_from_devcontainer(self, git_ops, tmp_path):
        """Returns the image string from .devcontainer/devcontainer.json."""
        dc = tmp_path / ".devcontainer"
        dc.mkdir()
        (dc / "devcontainer.json").write_text(
            json.dumps({"image": "containers.ad.corekinect.com/ncs-fw-dev:2.7.0"})
        )
        result = git_ops.get_builder_image(tmp_path)
        assert result == "containers.ad.corekinect.com/ncs-fw-dev:2.7.0"

    def test_get_builder_image_returns_none_when_missing(self, git_ops, tmp_path):
        """Returns None when no devcontainer.json exists."""
        result = git_ops.get_builder_image(tmp_path)
        assert result is None

    def test_check_ncs_version_extracts_semver(self, git_ops, tmp_path):
        """Extracts NCS version string from the image tag."""
        dc = tmp_path / ".devcontainer"
        dc.mkdir()
        (dc / "devcontainer.json").write_text(
            json.dumps({"image": "containers.ad.corekinect.com/ncs-fw-dev:2.7.0"})
        )
        result = git_ops.check_ncs_version(tmp_path)
        assert result == "2.7.0"

    def test_check_ncs_version_returns_none_when_no_devcontainer(self, git_ops, tmp_path):
        """Returns None when devcontainer.json is absent."""
        result = git_ops.check_ncs_version(tmp_path)
        assert result is None
