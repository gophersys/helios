"""Tests for BuildExecutor methods (no subprocess or Docker required)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.worker.executor import BuildExecutor, BuildJob, _extract_version_override


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def executor(mock_api_client) -> BuildExecutor:
    """BuildExecutor with a mocked API client."""
    return BuildExecutor(api_client=mock_api_client)


@pytest.fixture
def job_with_script(tmp_path: Path, sample_job: BuildJob) -> tuple[BuildJob, Path]:
    """A sample job plus a workspace that actually contains scripts/build.sh."""
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "build.sh").write_text("#!/bin/bash\necho done")
    (tmp_path / "artifacts").mkdir()
    sample_job.config_flags = {}
    return sample_job, tmp_path


# ---------------------------------------------------------------------------
# _extract_version_override (module-level function)
# ---------------------------------------------------------------------------

class TestExtractVersionOverride:
    """Tests for _extract_version_override() helper."""

    def test_extracts_from_config_flags(self):
        """versionOverride in configFlags takes precedence."""
        data = {"configFlags": {"versionOverride": "0.5.3"}}
        assert _extract_version_override(data) == "0.5.3"

    def test_extracts_from_direct_field(self):
        """Falls back to top-level versionOverride field."""
        data = {"versionOverride": "1.2.3"}
        assert _extract_version_override(data) == "1.2.3"

    def test_extracts_from_firmware_version(self):
        """Falls back to firmwareVersion field."""
        data = {"firmwareVersion": "0.8.0"}
        assert _extract_version_override(data) == "0.8.0"

    def test_returns_none_when_absent(self):
        """Returns None when no version override key exists."""
        assert _extract_version_override({}) is None

    def test_config_flags_none_handled(self):
        """configFlags=None does not raise."""
        data = {"configFlags": None, "versionOverride": "1.0.0"}
        assert _extract_version_override(data) == "1.0.0"


# ---------------------------------------------------------------------------
# prepare_build_env
# ---------------------------------------------------------------------------

class TestPrepareBuildEnv:
    """Tests for BuildExecutor.prepare_build_env()."""

    def test_prepare_build_env_local_has_concord_vars(self, executor, job_with_script):
        """Local-mode env dict contains all CONCORD_* variables."""
        job, work_dir = job_with_script
        output_dir = work_dir / "artifacts"

        env, cmd, target = executor.prepare_build_env(job, work_dir, output_dir, docker_mode=False)

        assert "CONCORD_BOARD" in env
        assert "CONCORD_VARIANT" in env
        assert "CONCORD_FW_TYPE" in env
        assert "CONCORD_COMMIT_SHA" in env
        assert "CONCORD_BRANCH" in env
        assert "CONCORD_PRODUCT" in env
        assert "CONCORD_TARGETS" in env

    def test_prepare_build_env_local_sets_zephyr_paths(self, executor, job_with_script):
        """Local mode injects ZEPHYR_BASE from the host environment."""
        job, work_dir = job_with_script
        output_dir = work_dir / "artifacts"

        env, cmd, target = executor.prepare_build_env(job, work_dir, output_dir, docker_mode=False)

        assert "ZEPHYR_BASE" in env
        assert "ZEPHYR_TOOLCHAIN_VARIANT" in env
        assert "ZEPHYR_SDK_INSTALL_DIR" in env

    def test_prepare_build_env_docker_omits_zephyr_paths(self, executor, job_with_script):
        """Docker mode does NOT inject ZEPHYR_* vars (image provides them)."""
        job, work_dir = job_with_script
        job.config_flags = {"_primary_slug": "alpha_fw"}
        output_dir = work_dir / "artifacts"

        env, cmd, target = executor.prepare_build_env(job, work_dir, output_dir, docker_mode=True)

        assert "ZEPHYR_BASE" not in env
        assert "ZEPHYR_SDK_INSTALL_DIR" not in env

    def test_prepare_build_env_docker_uses_container_paths(self, executor, job_with_script):
        """Docker mode sets BUILD_DIR / OUTPUT_DIR / REPO_DIR to /workspace/{job_id}."""
        job, work_dir = job_with_script
        job.config_flags = {"_primary_slug": "alpha_fw"}
        output_dir = work_dir / "artifacts"

        env, cmd, target = executor.prepare_build_env(job, work_dir, output_dir, docker_mode=True)

        assert env["BUILD_DIR"].startswith("/workspace/")
        assert env["OUTPUT_DIR"].startswith("/workspace/")
        assert env["REPO_DIR"].startswith("/workspace/")

    def test_prepare_build_env_raises_if_no_script(self, executor, tmp_path, sample_job):
        """Raises FileNotFoundError when scripts/build.sh does not exist."""
        output_dir = tmp_path / "artifacts"
        output_dir.mkdir()
        with pytest.raises(FileNotFoundError, match="build.sh"):
            executor.prepare_build_env(sample_job, tmp_path, output_dir, docker_mode=False)

    def test_prepare_build_env_version_override_sets_env_var(self, executor, job_with_script):
        """A version_override of '0.5.3' sets VERSION_BUILD_OVERRIDE to '3'."""
        job, work_dir = job_with_script
        job.version_override = "0.5.3"
        output_dir = work_dir / "artifacts"

        env, cmd, target = executor.prepare_build_env(job, work_dir, output_dir, docker_mode=False)

        assert env.get("VERSION_BUILD_OVERRIDE") == "3"
        assert env.get("CONCORD_VERSION_OVERRIDE") == "3"


# ---------------------------------------------------------------------------
# collect_artifacts
# ---------------------------------------------------------------------------

class TestCollectArtifacts:
    """Tests for BuildExecutor.collect_artifacts()."""

    def test_collect_artifacts_finds_hex_and_cfw(self, executor, tmp_path):
        """Collects versioned hex and cfw files from output directory."""
        (tmp_path / "109.0.8.3.hex").write_text("hex")
        (tmp_path / "108.0.8.3-BM.cfw").write_text("cfw")

        artifacts = executor.collect_artifacts(tmp_path)
        names = [a.name for a in artifacts]

        assert "109.0.8.3.hex" in names
        assert "108.0.8.3-BM.cfw" in names

    def test_collect_artifacts_includes_build_json(self, executor, tmp_path):
        """collect_artifacts includes build.json if present."""
        (tmp_path / "build.json").write_text("{}")
        artifacts = executor.collect_artifacts(tmp_path)
        names = [a.name for a in artifacts]
        assert "build.json" in names

    def test_collect_artifacts_ignores_zephyr_hex(self, executor, tmp_path):
        """zephyr.hex (no appId prefix) is NOT collected."""
        (tmp_path / "zephyr.hex").write_text("zephyr")
        artifacts = executor.collect_artifacts(tmp_path)
        names = [a.name for a in artifacts]
        assert "zephyr.hex" not in names

    def test_collect_artifacts_empty_dir(self, executor, tmp_path):
        """Empty output directory returns empty list."""
        assert executor.collect_artifacts(tmp_path) == []

    def test_collect_artifacts_recursive(self, executor, tmp_path):
        """Finds hex/cfw files in subdirectories."""
        subdir = tmp_path / "0.8.3" / "release"
        subdir.mkdir(parents=True)
        (subdir / "109.0.8.3.hex").write_text("hex")
        (subdir / "108.0.8.3-BM.cfw").write_text("cfw")

        artifacts = executor.collect_artifacts(tmp_path)
        names = [a.name for a in artifacts]

        assert "109.0.8.3.hex" in names
        assert "108.0.8.3-BM.cfw" in names

    # TODO: test_collect_artifacts_does_not_include_build_log
    # TODO: test_collect_artifacts_ignores_partial_hex_names
