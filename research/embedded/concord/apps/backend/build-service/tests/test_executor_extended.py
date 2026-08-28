"""Extended tests for BuildExecutor — covering run_build (local subprocess mode),
upload_artifacts, verify_artifacts, write_manifest, and version-bump logic.

Subprocess and filesystem interactions are mocked.  No Docker, no real build.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Optional
from unittest.mock import MagicMock, patch, call

import pytest

from src.worker.executor import BuildExecutor, BuildJob


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def executor(mock_api_client) -> BuildExecutor:
    """BuildExecutor with a mocked API client."""
    return BuildExecutor(api_client=mock_api_client)


@pytest.fixture
def job_with_script(tmp_path: Path, sample_job: BuildJob):
    """Sample job plus a workspace that contains scripts/build.sh."""
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "build.sh").write_text("#!/bin/bash\necho done")
    (tmp_path / "artifacts").mkdir()
    sample_job.config_flags = {}
    return sample_job, tmp_path


# ---------------------------------------------------------------------------
# get_base_build_version
# ---------------------------------------------------------------------------

class TestGetBaseBuildVersion:
    """Tests for BuildExecutor.get_base_build_version()."""

    def test_returns_build_number_from_version_string(self, executor, mock_api_client):
        """Returns the patch component of the version string."""
        mock_api_client.api_get.return_value = {"data": {"versionString": "0.8.3"}}
        result = executor.get_base_build_version("base-job-001")
        assert result == 3

    def test_returns_build_number_with_v_prefix(self, executor, mock_api_client):
        """Handles version strings prefixed with 'v'."""
        mock_api_client.api_get.return_value = {"data": {"versionString": "v1.2.5"}}
        result = executor.get_base_build_version("base-job-001")
        assert result == 5

    def test_returns_none_when_no_base_job_id(self, executor):
        """Returns None immediately when base_job_id is None/empty."""
        assert executor.get_base_build_version(None) is None
        assert executor.get_base_build_version("") is None

    def test_returns_none_when_api_fails(self, executor, mock_api_client):
        """Returns None when the API returns None."""
        mock_api_client.api_get.return_value = None
        assert executor.get_base_build_version("base-job-001") is None

    def test_returns_none_when_version_string_malformed(self, executor, mock_api_client):
        """Returns None when version string does not contain semver."""
        mock_api_client.api_get.return_value = {"data": {"versionString": "no-version-here"}}
        assert executor.get_base_build_version("base-job-001") is None


# ---------------------------------------------------------------------------
# prepare_build_env — version bump via base job
# ---------------------------------------------------------------------------

class TestPrepareBuildEnvVersionBump:
    """Version bump behaviour in prepare_build_env."""

    def test_version_bump_fetches_base_and_increments(self, executor, mock_api_client, job_with_script):
        """When version_bump=True, fetches base version and adds 1."""
        mock_api_client.api_get.return_value = {"data": {"versionString": "0.8.3"}}
        job, work_dir = job_with_script
        job.version_bump = True
        job.base_job_id = "base-001"

        env, cmd, target = executor.prepare_build_env(job, work_dir, work_dir / "artifacts")

        assert env.get("VERSION_BUILD_OVERRIDE") == "4"

    def test_version_bump_skipped_when_base_not_found(self, executor, mock_api_client, job_with_script):
        """No VERSION_BUILD_OVERRIDE set when base job version cannot be fetched."""
        mock_api_client.api_get.return_value = None
        job, work_dir = job_with_script
        job.version_bump = True
        job.base_job_id = "missing-base"

        env, cmd, target = executor.prepare_build_env(job, work_dir, work_dir / "artifacts")

        assert "VERSION_BUILD_OVERRIDE" not in env

    def test_force_log_flag_appended_to_cmd(self, executor, job_with_script):
        """When configFlags.forceLog is True, --force-log is appended to the command."""
        job, work_dir = job_with_script
        job.config_flags = {"forceLog": True}

        env, cmd, target = executor.prepare_build_env(job, work_dir, work_dir / "artifacts")

        assert "--force-log" in cmd

    def test_non_standard_variant_appended_to_cmd(self, executor, job_with_script):
        """Variant other than 'mfg'/'release' is appended with --variant flag."""
        job, work_dir = job_with_script
        job.variant = "debug"

        env, cmd, target = executor.prepare_build_env(job, work_dir, work_dir / "artifacts")

        assert "--variant" in cmd
        assert "debug" in cmd

    def test_mfg_variant_not_appended(self, executor, job_with_script):
        """'mfg' variant is not appended as --variant (it's built-in)."""
        job, work_dir = job_with_script
        job.variant = "mfg"

        env, cmd, target = executor.prepare_build_env(job, work_dir, work_dir / "artifacts")

        assert "--variant" not in cmd


# ---------------------------------------------------------------------------
# run_build — local subprocess path
# ---------------------------------------------------------------------------

class TestRunBuildLocalMode:
    """Tests for BuildExecutor.run_build() in local (non-Docker) mode."""

    def _make_process(self, lines: list[str], returncode: int = 0) -> MagicMock:
        """Build a MagicMock Popen with a readline sequence."""
        proc = MagicMock()
        # stdout.readline() yields each line then "" to signal EOF
        proc.stdout.readline.side_effect = lines + [""]
        proc.poll.return_value = returncode
        proc.wait.return_value = returncode
        proc.returncode = returncode
        return proc

    def test_run_build_returns_true_on_success(self, executor, job_with_script):
        """Returns (True, output) when the build script exits 0."""
        job, work_dir = job_with_script
        proc = self._make_process(["Building...\n", "Done\n"], returncode=0)

        with patch("subprocess.Popen", return_value=proc):
            success, output = executor.run_build(job, work_dir, work_dir / "artifacts")

        assert success is True
        assert "Done" in output

    def test_run_build_returns_false_on_nonzero_exit(self, executor, job_with_script):
        """Returns (False, output) when the build script exits non-zero."""
        job, work_dir = job_with_script
        proc = self._make_process(["error output\n"], returncode=1)

        with patch("subprocess.Popen", return_value=proc):
            success, output = executor.run_build(job, work_dir, work_dir / "artifacts")

        assert success is False

    def test_run_build_returns_false_when_no_script(self, executor, tmp_path, sample_job):
        """Returns (False, error_message) when build.sh is absent."""
        output_dir = tmp_path / "artifacts"
        output_dir.mkdir()

        success, output = executor.run_build(sample_job, tmp_path, output_dir)

        assert success is False
        assert "build.sh" in output

    def test_run_build_streams_log_chunks(self, executor, mock_api_client, job_with_script):
        """Accumulated log lines are flushed to the API client."""
        job, work_dir = job_with_script
        # Generate 11 lines so the batch flush logic triggers (threshold=10)
        lines = [f"line {i}\n" for i in range(11)]
        proc = self._make_process(lines, returncode=0)

        with patch("subprocess.Popen", return_value=proc):
            executor.run_build(job, work_dir, work_dir / "artifacts")

        assert mock_api_client.stream_log_chunk.called

    def test_run_build_handles_timeout(self, executor, job_with_script):
        """Returns (False, ...[TIMEOUT]) when the build times out."""
        job, work_dir = job_with_script
        proc = MagicMock()
        proc.stdout.readline.side_effect = subprocess.TimeoutExpired("build.sh", 1800)
        proc.returncode = None

        with patch("subprocess.Popen", return_value=proc):
            success, output = executor.run_build(job, work_dir, work_dir / "artifacts")

        assert success is False
        assert "timed out" in output.lower() or "TIMEOUT" in output

    def test_run_build_delegates_to_docker_runner(self, executor, job_with_script):
        """When docker_runner is provided, delegates to docker_runner.run_build()."""
        job, work_dir = job_with_script
        docker_runner = MagicMock()
        docker_runner.run_build.return_value = (True, "docker output")
        builder_image = "containers.ad.corekinect.com/ncs-fw-dev:2.7.0"

        success, output = executor.run_build(
            job, work_dir, work_dir / "artifacts",
            docker_runner=docker_runner,
            builder_image=builder_image,
        )

        assert success is True
        assert output == "docker output"
        docker_runner.run_build.assert_called_once()


# ---------------------------------------------------------------------------
# upload_artifacts
# ---------------------------------------------------------------------------

class TestUploadArtifacts:
    """Tests for BuildExecutor.upload_artifacts()."""

    def test_upload_artifacts_returns_count_of_successes(self, executor, mock_api_client, tmp_path):
        """Returns the number of successfully uploaded artifacts."""
        mock_api_client.upload_file.return_value = True
        artifacts = [tmp_path / "109.0.8.3.hex", tmp_path / "build.json"]
        for a in artifacts:
            a.write_text("data")

        count = executor.upload_artifacts("job-001", artifacts)

        assert count == 2

    def test_upload_artifacts_passes_role_from_build_config(self, executor, mock_api_client, tmp_path, sample_build_config):
        """Role and processor are looked up from buildConfig.targets by appId."""
        mock_api_client.upload_file.return_value = True
        hex_file = tmp_path / "109.0.8.3.hex"
        hex_file.write_text("data")

        executor.upload_artifacts("job-001", [hex_file], build_config=sample_build_config)

        call_kwargs = mock_api_client.upload_file.call_args
        metadata = call_kwargs[1].get("metadata") or call_kwargs[0][3]
        assert metadata.get("role") == "app"
        assert metadata.get("processor") == "nrf52840"

    def test_upload_artifacts_handles_upload_failure(self, executor, mock_api_client, tmp_path):
        """Does not raise when upload_file returns False; count reflects failures."""
        mock_api_client.upload_file.return_value = False
        artifact = tmp_path / "109.0.8.3.hex"
        artifact.write_text("hex")

        count = executor.upload_artifacts("job-001", [artifact])

        assert count == 0

    def test_upload_artifacts_assigns_manifest_metadata_to_build_json(self, executor, mock_api_client, tmp_path):
        """build.json gets role=manifest, artifactType=manifest metadata."""
        mock_api_client.upload_file.return_value = True
        build_json = tmp_path / "build.json"
        build_json.write_text("{}")

        executor.upload_artifacts("job-001", [build_json])

        call_kwargs = mock_api_client.upload_file.call_args
        metadata = call_kwargs[1].get("metadata") or call_kwargs[0][3]
        assert metadata.get("role") == "manifest"

    def test_upload_artifacts_handles_dict_format_targets(self, executor, mock_api_client, tmp_path):
        """Handles buildConfig.targets as a dict rather than a list."""
        mock_api_client.upload_file.return_value = True
        hex_file = tmp_path / "109.0.8.3.hex"
        hex_file.write_text("hex")

        build_config_dict_targets = {
            "targets": {
                "app": {"appId": 109, "role": "app", "processor": "nrf52840"},
            }
        }
        executor.upload_artifacts("job-001", [hex_file], build_config=build_config_dict_targets)

        call_kwargs = mock_api_client.upload_file.call_args
        metadata = call_kwargs[1].get("metadata") or call_kwargs[0][3]
        assert metadata.get("role") == "app"


# ---------------------------------------------------------------------------
# verify_artifacts
# ---------------------------------------------------------------------------

class TestVerifyArtifacts:
    """Tests for BuildExecutor.verify_artifacts()."""

    def test_verify_artifacts_returns_true_when_no_validator(self, executor, tmp_path):
        """Returns (True, 'Validator not available') when HAS_VALIDATOR is False."""
        with patch("src.worker.executor.HAS_VALIDATOR", False):
            ok, msg = executor.verify_artifacts(tmp_path)
        assert ok is True
        assert "not available" in msg

    def test_verify_artifacts_returns_false_when_no_artifacts(self, executor, tmp_path):
        """Returns (False, ...) when no hex or build.json found and validator present."""
        with patch("src.worker.executor.HAS_VALIDATOR", True):
            ok, msg = executor.verify_artifacts(tmp_path)
        assert ok is False
        assert "No artifacts" in msg

    def test_verify_artifacts_skips_validation_without_build_json_but_hex_present(self, executor, tmp_path):
        """Returns (True, skip msg) when hex exists but no build.json."""
        (tmp_path / "109.0.8.3.hex").write_text("hex")
        with patch("src.worker.executor.HAS_VALIDATOR", True):
            ok, msg = executor.verify_artifacts(tmp_path)
        assert ok is True
        assert "skipping" in msg.lower()


# ---------------------------------------------------------------------------
# write_manifest
# ---------------------------------------------------------------------------

class TestWriteManifest:
    """Tests for BuildExecutor.write_manifest()."""

    def test_write_manifest_creates_build_json(self, executor, tmp_path, sample_build_config):
        """Creates build.json in the output directory when manifest generation succeeds."""
        with patch("src.worker.executor.generate_build_manifest", return_value={"version": "0.8.3"}):
            path = executor.write_manifest(
                build_config=sample_build_config,
                output_dir=tmp_path,
                product="alpha",
                board="alpha_b0",
                version="0.8.3",
                variant="release",
                commit_sha="deadbeef",
                branch="main",
            )
        assert path == tmp_path / "build.json"
        assert (tmp_path / "build.json").exists()

    def test_write_manifest_returns_none_on_exception(self, executor, tmp_path, sample_build_config):
        """Returns None when generate_build_manifest raises."""
        with patch("src.worker.executor.generate_build_manifest", side_effect=RuntimeError("fail")):
            path = executor.write_manifest(
                build_config=sample_build_config,
                output_dir=tmp_path,
                product="alpha",
                board="alpha_b0",
                version="0.8.3",
                variant="release",
                commit_sha="deadbeef",
                branch="main",
            )
        assert path is None

    def test_write_manifest_content_is_valid_json(self, executor, tmp_path, sample_build_config):
        """Written build.json is valid JSON."""
        manifest = {"product": "alpha", "version": "0.8.3", "targets": []}
        with patch("src.worker.executor.generate_build_manifest", return_value=manifest):
            executor.write_manifest(
                build_config=sample_build_config,
                output_dir=tmp_path,
                product="alpha",
                board="alpha_b0",
                version="0.8.3",
                variant="release",
                commit_sha="deadbeef",
                branch="main",
            )
        data = json.loads((tmp_path / "build.json").read_text())
        assert data["product"] == "alpha"
