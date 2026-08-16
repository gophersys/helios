"""Tests for DockerBuildRunner pure-logic methods (no Docker daemon required)."""

from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.worker.docker_runner import DockerBuildRunner


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def runner() -> DockerBuildRunner:
    """DockerBuildRunner with sensible test defaults."""
    return DockerBuildRunner(
        workspace_volume="",
        ccache_volume="",
        builder_network="host",
        builder_timeout=1800,
        default_image="containers.ad.corekinect.com/ncs-fw-dev:2.7.0",
    )


@pytest.fixture
def repo_with_devcontainer(tmp_path: Path) -> Path:
    """Minimal repo directory containing a valid .devcontainer/devcontainer.json."""
    devcontainer_dir = tmp_path / ".devcontainer"
    devcontainer_dir.mkdir()
    devcontainer_json = {
        "image": "containers.ad.corekinect.com/ncs-fw-dev:2.7.0",
        "name": "NCS Firmware Dev",
    }
    (devcontainer_dir / "devcontainer.json").write_text(json.dumps(devcontainer_json))
    return tmp_path


@pytest.fixture
def repo_with_commented_devcontainer(tmp_path: Path) -> Path:
    """Repo with a devcontainer.json that has // comments (common pattern)."""
    devcontainer_dir = tmp_path / ".devcontainer"
    devcontainer_dir.mkdir()
    content = """\
// This is a comment
{
    // Registry image
    "image": "containers.ad.corekinect.com/ncs-fw-dev:2.7.0",
    "name": "NCS Firmware Dev"
}
"""
    (devcontainer_dir / "devcontainer.json").write_text(content)
    return tmp_path


# ---------------------------------------------------------------------------
# extract_builder_image
# ---------------------------------------------------------------------------

class TestExtractBuilderImage:
    """Tests for DockerBuildRunner.extract_builder_image()."""

    def test_extract_builder_image_reads_image_field(self, repo_with_devcontainer):
        """Returns image from devcontainer.json 'image' key."""
        result = DockerBuildRunner.extract_builder_image(repo_with_devcontainer)
        assert result == "containers.ad.corekinect.com/ncs-fw-dev:2.7.0"

    def test_extract_builder_image_strips_comments(self, repo_with_commented_devcontainer):
        """Parses devcontainer.json correctly even when it contains // comments."""
        result = DockerBuildRunner.extract_builder_image(repo_with_commented_devcontainer)
        assert result == "containers.ad.corekinect.com/ncs-fw-dev:2.7.0"

    def test_extract_builder_image_no_file(self, tmp_path):
        """Returns None when .devcontainer/devcontainer.json is absent."""
        result = DockerBuildRunner.extract_builder_image(tmp_path)
        assert result is None

    def test_extract_builder_image_missing_image_key(self, tmp_path):
        """Returns None when devcontainer.json exists but has no 'image' key."""
        devcontainer_dir = tmp_path / ".devcontainer"
        devcontainer_dir.mkdir()
        (devcontainer_dir / "devcontainer.json").write_text('{"name": "no-image"}')
        result = DockerBuildRunner.extract_builder_image(tmp_path)
        assert result is None

    def test_extract_builder_image_malformed_json(self, tmp_path):
        """Returns None gracefully when devcontainer.json contains invalid JSON."""
        devcontainer_dir = tmp_path / ".devcontainer"
        devcontainer_dir.mkdir()
        (devcontainer_dir / "devcontainer.json").write_text("{ not valid json }")
        result = DockerBuildRunner.extract_builder_image(tmp_path)
        assert result is None


# ---------------------------------------------------------------------------
# extract_ncs_version
# ---------------------------------------------------------------------------

class TestExtractNcsVersion:
    """Tests for DockerBuildRunner.extract_ncs_version()."""

    def test_extract_ncs_version_semver_tag(self):
        """Extracts '2.7.0' from a full registry URL with semver tag."""
        result = DockerBuildRunner.extract_ncs_version(
            "containers.ad.corekinect.com/ncs-fw-dev:2.7.0"
        )
        assert result == "2.7.0"

    def test_extract_ncs_version_no_tag(self):
        """Returns None when image has no version tag."""
        assert DockerBuildRunner.extract_ncs_version("ubuntu:latest") is None

    def test_extract_ncs_version_no_colon(self):
        """Returns None when image string has no colon."""
        assert DockerBuildRunner.extract_ncs_version("myimage") is None

    @pytest.mark.parametrize("image,expected", [
        ("containers.ad.corekinect.com/ncs-fw-dev:2.7.0", "2.7.0"),
        ("someregistry/image:1.0.0", "1.0.0"),
        ("someregistry/image:10.20.30", "10.20.30"),
    ])
    def test_extract_ncs_version_various_images(self, image, expected):
        """Correctly extracts semver from various image formats."""
        assert DockerBuildRunner.extract_ncs_version(image) == expected


# ---------------------------------------------------------------------------
# _build_docker_cmd
# ---------------------------------------------------------------------------

class TestBuildDockerCmd:
    """Tests for DockerBuildRunner._build_docker_cmd()."""

    def test_build_docker_cmd_contains_image(self, runner):
        """Generated command includes the builder image."""
        cmd = runner._build_docker_cmd(
            image="myimage:1.0",
            container_name="concord-build-abc",
            job_id="job-abc",
            env={},
            cmd=["bash", "build.sh"],
        )
        assert "myimage:1.0" in cmd

    def test_build_docker_cmd_sets_working_dir(self, runner):
        """Working directory is set to /workspace/{job_id}."""
        cmd = runner._build_docker_cmd(
            image="myimage:1.0",
            container_name="concord-build-abc",
            job_id="job-abc-123",
            env={},
            cmd=["bash", "build.sh"],
        )
        assert "-w" in cmd
        idx = cmd.index("-w")
        assert cmd[idx + 1] == "/workspace/job-abc-123"

    def test_build_docker_cmd_passes_env_vars(self, runner):
        """Environment variables are passed with -e flags."""
        cmd = runner._build_docker_cmd(
            image="myimage:1.0",
            container_name="concord-build-abc",
            job_id="job-abc",
            env={"MY_VAR": "my_value"},
            cmd=["bash", "build.sh"],
        )
        assert "-e" in cmd
        assert "MY_VAR=my_value" in cmd

    def test_build_docker_cmd_skips_zephyr_env_vars(self, runner):
        """Zephyr path env vars are not passed to the container."""
        cmd = runner._build_docker_cmd(
            image="myimage:1.0",
            container_name="concord-build-abc",
            job_id="job-abc",
            env={
                "ZEPHYR_BASE": "/workdir/zephyr",
                "ZEPHYR_SDK_INSTALL_DIR": "/workdir/zephyr-sdk",
                "ZEPHYR_TOOLCHAIN_VARIANT": "zephyr",
                "MY_VAR": "kept",
            },
            cmd=["bash", "build.sh"],
        )
        env_values = [arg for arg in cmd if arg.startswith("ZEPHYR_")]
        assert len(env_values) == 0
        assert "MY_VAR=kept" in cmd

    def test_build_docker_cmd_sets_network(self, runner):
        """--network flag is set to builder_network."""
        cmd = runner._build_docker_cmd(
            image="myimage:1.0",
            container_name="concord-build-abc",
            job_id="job-abc",
            env={},
            cmd=["bash", "build.sh"],
        )
        assert "--network" in cmd
        idx = cmd.index("--network")
        assert cmd[idx + 1] == "host"

    def test_build_docker_cmd_includes_ccache_env(self, runner):
        """CCACHE_DIR and CMAKE_*_COMPILER_LAUNCHER are always included."""
        cmd = runner._build_docker_cmd(
            image="myimage:1.0",
            container_name="concord-build-abc",
            job_id="job-abc",
            env={},
            cmd=["bash", "build.sh"],
        )
        env_str = " ".join(cmd)
        assert "CCACHE_DIR=/ccache" in env_str
        assert "CMAKE_C_COMPILER_LAUNCHER=ccache" in env_str

    def test_build_docker_cmd_uses_named_volume_when_set(self):
        """With workspace_volume set, uses --mount type=volume syntax."""
        runner = DockerBuildRunner(
            workspace_volume="concord-workspace",
            ccache_volume="concord-ccache",
        )
        cmd = runner._build_docker_cmd(
            image="img:1.0",
            container_name="concord-build-abc",
            job_id="job-abc",
            env={},
            cmd=["bash", "build.sh"],
        )
        cmd_str = " ".join(cmd)
        assert "type=volume,source=concord-workspace" in cmd_str
        assert "type=volume,source=concord-ccache" in cmd_str

    # TODO: test_build_docker_cmd_uses_host_path_when_no_volume_but_env_set
    # TODO: test_build_docker_cmd_rm_flag_present
