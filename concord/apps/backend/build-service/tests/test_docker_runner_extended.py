"""Extended tests for DockerBuildRunner — ensure_image, run_build, cleanup,
cleanup_orphaned_containers, and host-path volume mounts.

All subprocess.run / subprocess.Popen calls are mocked.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch, call

import pytest

from src.worker.docker_runner import DockerBuildRunner


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def runner() -> DockerBuildRunner:
    """DockerBuildRunner with test defaults."""
    return DockerBuildRunner(
        workspace_volume="",
        ccache_volume="",
        builder_network="host",
        builder_timeout=1800,
        default_image="containers.ad.corekinect.com/ncs-fw-dev:2.7.0",
    )


# ---------------------------------------------------------------------------
# ensure_image
# ---------------------------------------------------------------------------

class TestEnsureImage:
    """Tests for DockerBuildRunner.ensure_image()."""

    def test_ensure_image_returns_true_when_cached(self, runner):
        """Returns True immediately when the image inspect command succeeds."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        with patch("subprocess.run", return_value=mock_result):
            result = runner.ensure_image("containers.ad.corekinect.com/ncs-fw-dev:2.7.0")
        assert result is True

    def test_ensure_image_pulls_when_not_cached(self, runner):
        """Calls docker pull when inspect fails, returns True on pull success."""
        inspect_fail = MagicMock()
        inspect_fail.returncode = 1

        pull_ok = MagicMock()
        pull_ok.returncode = 0
        pull_ok.stderr = ""

        with patch("subprocess.run", side_effect=[inspect_fail, pull_ok]):
            result = runner.ensure_image("containers.ad.corekinect.com/ncs-fw-dev:2.7.0")

        assert result is True

    def test_ensure_image_returns_false_when_pull_fails(self, runner):
        """Returns False when docker pull also fails."""
        inspect_fail = MagicMock()
        inspect_fail.returncode = 1

        pull_fail = MagicMock()
        pull_fail.returncode = 1
        pull_fail.stderr = "manifest unknown"

        with patch("subprocess.run", side_effect=[inspect_fail, pull_fail]):
            result = runner.ensure_image("containers.ad.corekinect.com/ncs-fw-dev:2.7.0")

        assert result is False


# ---------------------------------------------------------------------------
# cleanup_orphaned_containers
# ---------------------------------------------------------------------------

class TestCleanupOrphanedContainers:
    """Tests for DockerBuildRunner.cleanup_orphaned_containers()."""

    def test_cleanup_orphaned_kills_listed_containers(self):
        """docker kill and rm are called for each listed container."""
        ps_result = MagicMock()
        ps_result.returncode = 0
        ps_result.stdout = "concord-build-abc\nconcord-build-xyz\n"

        kill_result = MagicMock()
        kill_result.returncode = 0

        with patch("subprocess.run", side_effect=[ps_result, kill_result, kill_result, kill_result, kill_result]) as mock_run:
            DockerBuildRunner.cleanup_orphaned_containers()

        # docker ps + 2x(kill + rm) = 5 calls
        assert mock_run.call_count >= 3

    def test_cleanup_orphaned_skips_when_no_containers(self):
        """Skips kill/rm calls when docker ps returns empty output."""
        ps_result = MagicMock()
        ps_result.returncode = 0
        ps_result.stdout = ""

        with patch("subprocess.run", return_value=ps_result) as mock_run:
            DockerBuildRunner.cleanup_orphaned_containers()

        # Only the ps call should be made
        assert mock_run.call_count == 1

    def test_cleanup_orphaned_handles_docker_ps_failure(self):
        """Does not raise when docker ps returns non-zero exit code."""
        ps_result = MagicMock()
        ps_result.returncode = 1
        ps_result.stdout = ""

        with patch("subprocess.run", return_value=ps_result):
            DockerBuildRunner.cleanup_orphaned_containers()  # Should not raise

    def test_cleanup_orphaned_handles_exception(self):
        """Does not raise when subprocess.run itself throws."""
        with patch("subprocess.run", side_effect=Exception("docker not found")):
            DockerBuildRunner.cleanup_orphaned_containers()  # Should not raise


# ---------------------------------------------------------------------------
# run_build
# ---------------------------------------------------------------------------

class TestRunBuild:
    """Tests for DockerBuildRunner.run_build()."""

    def _make_process(self, lines: list[str], returncode: int = 0) -> MagicMock:
        proc = MagicMock()
        proc.stdout.__iter__ = MagicMock(return_value=iter(lines))
        proc.stdout.readline.side_effect = lines + [""]
        proc.wait.return_value = returncode
        proc.returncode = returncode
        return proc

    def test_run_build_returns_true_on_zero_exit(self, runner, tmp_path):
        """Returns (True, output) when container exits 0."""
        proc = self._make_process(["Building...", "Done"])

        with patch("subprocess.Popen", return_value=proc):
            success, output = runner.run_build(
                image="img:1.0",
                job_id="job-abc",
                work_dir=tmp_path,
                output_dir=tmp_path / "artifacts",
                env={"FOO": "bar"},
                cmd=["bash", "build.sh"],
            )

        assert success is True

    def test_run_build_returns_false_on_nonzero_exit(self, runner, tmp_path):
        """Returns (False, output) when container exits non-zero."""
        proc = self._make_process(["Build FAILED"], returncode=1)

        with patch("subprocess.Popen", return_value=proc):
            success, output = runner.run_build(
                image="img:1.0",
                job_id="job-abc",
                work_dir=tmp_path,
                output_dir=tmp_path / "artifacts",
                env={},
                cmd=["bash", "build.sh"],
            )

        assert success is False

    def test_run_build_batches_log_callback(self, runner, tmp_path):
        """log_callback is invoked with batched output lines."""
        # 15 lines to force at least one batch flush (threshold=10)
        lines = [f"line {i}" for i in range(15)]
        proc = self._make_process(lines, returncode=0)

        received_chunks = []

        def capture_chunk(chunk: str):
            received_chunks.append(chunk)

        with patch("subprocess.Popen", return_value=proc):
            runner.run_build(
                image="img:1.0",
                job_id="job-abc",
                work_dir=tmp_path,
                output_dir=tmp_path / "artifacts",
                env={},
                cmd=["bash", "build.sh"],
                log_callback=capture_chunk,
            )

        assert len(received_chunks) >= 1

    def test_run_build_clears_current_container_in_finally(self, runner, tmp_path):
        """_current_container is reset to None after run_build, even on success."""
        proc = self._make_process(["done"], returncode=0)

        with patch("subprocess.Popen", return_value=proc):
            runner.run_build(
                image="img:1.0",
                job_id="job-abc",
                work_dir=tmp_path,
                output_dir=tmp_path / "artifacts",
                env={},
                cmd=["bash", "build.sh"],
            )

        assert runner._current_container is None

    def test_run_build_handles_exception_gracefully(self, runner, tmp_path):
        """Returns (False, ...[ERROR:...]) when Popen raises an unexpected exception."""
        with patch("subprocess.Popen", side_effect=RuntimeError("no docker socket")):
            success, output = runner.run_build(
                image="img:1.0",
                job_id="job-abc",
                work_dir=tmp_path,
                output_dir=tmp_path / "artifacts",
                env={},
                cmd=["bash", "build.sh"],
            )

        assert success is False
        assert "ERROR" in output


# ---------------------------------------------------------------------------
# cleanup / _kill_container
# ---------------------------------------------------------------------------

class TestCleanup:
    """Tests for DockerBuildRunner.cleanup() and _kill_container()."""

    def test_cleanup_kills_current_container_when_set(self, runner):
        """Calls docker kill when _current_container is set."""
        runner._current_container = "concord-build-abc"

        with patch("subprocess.run") as mock_run:
            runner.cleanup()

        mock_run.assert_called()
        kill_call_args = mock_run.call_args[0][0]
        assert "kill" in kill_call_args
        assert "concord-build-abc" in kill_call_args

    def test_cleanup_is_noop_when_no_container(self, runner):
        """Does nothing when no container is currently running."""
        runner._current_container = None
        with patch("subprocess.run") as mock_run:
            runner.cleanup()
        mock_run.assert_not_called()

    def test_kill_container_handles_exception(self, runner):
        """Does not raise when docker kill fails."""
        with patch("subprocess.run", side_effect=Exception("timeout")):
            runner._kill_container("concord-build-abc")  # Should not raise


# ---------------------------------------------------------------------------
# _build_docker_cmd — host path mounts
# ---------------------------------------------------------------------------

class TestBuildDockerCmdHostPaths:
    """Tests for workspace / ccache host path bind mounts."""

    def test_uses_host_path_bind_mount_when_env_set(self, runner, monkeypatch):
        """When WORKSPACE_HOST_PATH is set, uses -v bind mount."""
        monkeypatch.setenv("WORKSPACE_HOST_PATH", "/mnt/builds")

        cmd = runner._build_docker_cmd(
            image="img:1.0",
            container_name="concord-build-abc",
            job_id="job-abc",
            env={},
            cmd=["bash", "build.sh"],
        )

        cmd_str = " ".join(cmd)
        assert "/mnt/builds:/workspace" in cmd_str

    def test_no_workspace_mount_when_no_volume_or_env(self, runner, monkeypatch):
        """No -v or --mount for workspace when neither volume nor env var is set."""
        monkeypatch.delenv("WORKSPACE_HOST_PATH", raising=False)
        monkeypatch.delenv("CCACHE_HOST_PATH", raising=False)

        cmd = runner._build_docker_cmd(
            image="img:1.0",
            container_name="concord-build-abc",
            job_id="job-abc",
            env={},
            cmd=["bash", "build.sh"],
        )

        cmd_str = " ".join(cmd)
        assert ":/workspace" not in cmd_str


# ---------------------------------------------------------------------------
# parse_devcontainer
# ---------------------------------------------------------------------------

class TestParseDevcontainer:
    """Tests for DockerBuildRunner.parse_devcontainer()."""

    def test_parse_devcontainer_extracts_all_fields(self, tmp_path):
        """Extracts image, containerEnv, and postCreateCommand."""
        dc_dir = tmp_path / ".devcontainer"
        dc_dir.mkdir()
        import json
        (dc_dir / "devcontainer.json").write_text(json.dumps({
            "image": "containers.ad.corekinect.com/ncs-fw-dev:2.7.0",
            "containerEnv": {"WEST_TOPDIR": "/workspace"},
            "postCreateCommand": "west init",
        }))
        config = DockerBuildRunner.parse_devcontainer(tmp_path)
        assert config.image == "containers.ad.corekinect.com/ncs-fw-dev:2.7.0"
        assert config.container_env == {"WEST_TOPDIR": "/workspace"}
        assert config.post_create_command == "west init"

    def test_parse_devcontainer_post_create_list_joined(self, tmp_path):
        """postCreateCommand as list is joined with ' && '."""
        dc_dir = tmp_path / ".devcontainer"
        dc_dir.mkdir()
        import json
        (dc_dir / "devcontainer.json").write_text(json.dumps({
            "image": "img:1.0",
            "postCreateCommand": ["cmd1", "cmd2"],
        }))
        config = DockerBuildRunner.parse_devcontainer(tmp_path)
        assert config.post_create_command == "cmd1 && cmd2"

    def test_parse_devcontainer_returns_defaults_when_no_file(self, tmp_path):
        """Returns DevcontainerConfig with empty defaults when no file exists."""
        config = DockerBuildRunner.parse_devcontainer(tmp_path)
        assert config.image == ""
        assert config.container_env == {}
        assert config.post_create_command is None
