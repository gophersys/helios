"""Tests for DevcontainerConfig parsing from devcontainer.json."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.worker.docker_runner import DevcontainerConfig, DockerBuildRunner


@pytest.fixture
def repo_with_devcontainer(tmp_path):
    """Create a repo dir with a .devcontainer/devcontainer.json."""
    def _create(content: dict) -> Path:
        repo = tmp_path / "test_repo"
        dc_dir = repo / ".devcontainer"
        dc_dir.mkdir(parents=True)
        (dc_dir / "devcontainer.json").write_text(json.dumps(content))
        return repo
    return _create


class TestParseDevcontainer:
    """Test devcontainer.json parsing."""

    def test_full_config(self, repo_with_devcontainer):
        """Parses all CI-relevant fields."""
        repo = repo_with_devcontainer({
            "name": "Test Dev",
            "image": "containers.ad.corekinect.com/ncs-fw-dev:2.7.0",
            "containerEnv": {
                "PYTHONPATH": "/app/libs",
                "MY_VAR": "hello",
            },
            "postCreateCommand": "pip install -r requirements.txt",
        })
        config = DockerBuildRunner.parse_devcontainer(repo)

        assert config.image == "containers.ad.corekinect.com/ncs-fw-dev:2.7.0"
        assert config.container_env == {"PYTHONPATH": "/app/libs", "MY_VAR": "hello"}
        assert config.post_create_command == "pip install -r requirements.txt"

    def test_image_only(self, repo_with_devcontainer):
        """Parses when only image is present."""
        repo = repo_with_devcontainer({"image": "ncs-fw-dev:3.0.0"})
        config = DockerBuildRunner.parse_devcontainer(repo)

        assert config.image == "ncs-fw-dev:3.0.0"
        assert config.container_env == {}
        assert config.post_create_command is None

    def test_no_devcontainer(self, tmp_path):
        """Returns empty config when no devcontainer.json exists."""
        repo = tmp_path / "empty_repo"
        repo.mkdir()
        config = DockerBuildRunner.parse_devcontainer(repo)

        assert config.image == ""
        assert config.container_env == {}
        assert config.post_create_command is None

    def test_post_create_command_as_list(self, repo_with_devcontainer):
        """postCreateCommand as a list is joined with &&."""
        repo = repo_with_devcontainer({
            "image": "test:1.0",
            "postCreateCommand": ["pip install -r req.txt", "west update"],
        })
        config = DockerBuildRunner.parse_devcontainer(repo)

        assert config.post_create_command == "pip install -r req.txt && west update"

    def test_comments_in_json(self, tmp_path):
        """Handles // comments in devcontainer.json (common in VS Code files)."""
        repo = tmp_path / "commented_repo"
        dc_dir = repo / ".devcontainer"
        dc_dir.mkdir(parents=True)
        (dc_dir / "devcontainer.json").write_text('''{
            // This is a comment
            "image": "registry/image:1.0",
            "containerEnv": {
                // Another comment
                "FOO": "bar"
            }
        }''')
        config = DockerBuildRunner.parse_devcontainer(repo)

        assert config.image == "registry/image:1.0"
        assert config.container_env == {"FOO": "bar"}

    def test_malformed_json(self, tmp_path):
        """Returns empty config on malformed JSON."""
        repo = tmp_path / "bad_repo"
        dc_dir = repo / ".devcontainer"
        dc_dir.mkdir(parents=True)
        (dc_dir / "devcontainer.json").write_text("not json at all {{{")
        config = DockerBuildRunner.parse_devcontainer(repo)

        assert config.image == ""

    def test_extra_fields_ignored(self, repo_with_devcontainer):
        """Non-CI fields (extensions, mounts, runArgs) are ignored."""
        repo = repo_with_devcontainer({
            "image": "test:2.0",
            "runArgs": ["--privileged"],
            "mounts": ["source=/dev,target=/dev"],
            "customizations": {"vscode": {"extensions": ["ms-python.python"]}},
        })
        config = DockerBuildRunner.parse_devcontainer(repo)

        assert config.image == "test:2.0"
        assert config.container_env == {}


class TestDockerCmdContainerEnv:
    """Test that containerEnv is merged into Docker command."""

    def test_container_env_added(self):
        """containerEnv vars are added to docker command."""
        runner = DockerBuildRunner(builder_network="host")
        cmd = runner._build_docker_cmd(
            image="test:1.0",
            container_name="test-build",
            job_id="job-123",
            env={"BUILD_VAR": "1"},
            cmd=["bash", "build.sh"],
            container_env={"PYTHONPATH": "/libs", "EXTRA": "val"},
        )
        cmd_str = " ".join(cmd)
        assert "PYTHONPATH=/libs" in cmd_str
        assert "EXTRA=val" in cmd_str

    def test_build_env_takes_precedence(self):
        """Build env vars override containerEnv when keys conflict."""
        runner = DockerBuildRunner(builder_network="host")
        cmd = runner._build_docker_cmd(
            image="test:1.0",
            container_name="test-build",
            job_id="job-123",
            env={"PYTHONPATH": "/build/libs"},
            cmd=["bash", "build.sh"],
            container_env={"PYTHONPATH": "/container/libs"},
        )
        # PYTHONPATH should appear only once (from build env, not containerEnv)
        env_entries = [c for c in cmd if c.startswith("PYTHONPATH=")]
        assert len(env_entries) == 1
        assert env_entries[0] == "PYTHONPATH=/build/libs"

    def test_zephyr_vars_excluded_from_container_env(self):
        """Zephyr-specific vars in containerEnv are excluded."""
        runner = DockerBuildRunner(builder_network="host")
        cmd = runner._build_docker_cmd(
            image="test:1.0",
            container_name="test-build",
            job_id="job-123",
            env={},
            cmd=["bash", "build.sh"],
            container_env={"ZEPHYR_BASE": "/zephyr", "SAFE_VAR": "ok"},
        )
        cmd_str = " ".join(cmd)
        assert "ZEPHYR_BASE" not in cmd_str
        assert "SAFE_VAR=ok" in cmd_str

    def test_no_container_env(self):
        """None containerEnv doesn't crash."""
        runner = DockerBuildRunner(builder_network="host")
        cmd = runner._build_docker_cmd(
            image="test:1.0",
            container_name="test-build",
            job_id="job-123",
            env={"A": "1"},
            cmd=["bash", "build.sh"],
            container_env=None,
        )
        assert "test:1.0" in cmd
