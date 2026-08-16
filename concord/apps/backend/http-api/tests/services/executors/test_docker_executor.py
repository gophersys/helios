"""Tests for DockerExecutor."""

from unittest.mock import MagicMock, patch
import subprocess

import pytest

from services.executors.docker_executor import DockerExecutor
from services.executors.base import VolumeMount


@pytest.fixture
def executor():
    return DockerExecutor(network="bridge", timeout=300)


class TestDockerExecutorSubmit:
    def test_submit_success(self, executor):
        with patch("services.executors.docker_executor.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="abc123def456\n", stderr="")
            result = executor.submit(
                image="concord/test-runner:dev",
                job_id="job-001",
                env={"CONCORD_API_URL": "http://localhost:9001", "STAGE": "smoke"},
                command=["/app/entrypoint.sh"],
            )
            assert result.success is True
            assert result.job_name is not None
            assert result.error is None

            # Verify docker run was called with detached mode
            # (no --rm: detached containers need to survive for post-mortem
            # inspection; cleanup is handled by the cancel/docker rm path)
            call_args = mock_run.call_args[0][0]
            assert "docker" in call_args
            assert "run" in call_args
            assert "-d" in call_args

    def test_submit_includes_env_vars(self, executor):
        with patch("services.executors.docker_executor.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="abc123\n", stderr="")
            executor.submit(
                image="img:latest",
                job_id="job-002",
                env={"KEY_A": "val_a", "KEY_B": "val_b"},
                command=["bash", "-c", "echo hi"],
            )
            call_args = mock_run.call_args[0][0]
            # Env vars are passed as -e KEY=VALUE pairs
            env_pairs = []
            for i, arg in enumerate(call_args):
                if arg == "-e" and i + 1 < len(call_args):
                    env_pairs.append(call_args[i + 1])
            assert "KEY_A=val_a" in env_pairs
            assert "KEY_B=val_b" in env_pairs

    def test_submit_includes_volumes(self, executor):
        with patch("services.executors.docker_executor.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="abc\n", stderr="")
            executor.submit(
                image="img:latest",
                job_id="job-003",
                env={},
                command=["true"],
                volumes=[VolumeMount(name="logs", host_path="/tmp/logs", mount_path="/var/log")],
            )
            call_args = mock_run.call_args[0][0]
            vol_args = [call_args[i + 1] for i, a in enumerate(call_args) if a == "-v" and i + 1 < len(call_args)]
            assert any("/tmp/logs:/var/log" in v for v in vol_args)

    def test_submit_docker_failure(self, executor):
        with patch("services.executors.docker_executor.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="image not found")
            result = executor.submit(
                image="nonexistent:latest",
                job_id="job-004",
                env={},
                command=["true"],
            )
            assert result.success is False
            assert "image not found" in result.error

    def test_submit_docker_not_installed(self, executor):
        with patch("services.executors.docker_executor.subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError("docker not found")
            result = executor.submit(
                image="img:latest",
                job_id="job-005",
                env={},
                command=["true"],
            )
            assert result.success is False
            assert "docker CLI not found" in result.error

    def test_submit_timeout(self, executor):
        with patch("services.executors.docker_executor.subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired(cmd="docker", timeout=30)
            result = executor.submit(
                image="img:latest",
                job_id="job-006",
                env={},
                command=["true"],
            )
            assert result.success is False
            assert "timed out" in result.error

    def test_submit_with_resource_limits(self, executor):
        with patch("services.executors.docker_executor.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="abc\n", stderr="")
            executor.submit(
                image="img:latest",
                job_id="job-007",
                env={},
                command=["true"],
                resource_limits={"memory": "2Gi", "cpu": "2"},
            )
            call_args = mock_run.call_args[0][0]
            assert "--memory" in call_args
            assert "--cpus" in call_args

    def test_submit_uses_configured_network(self, executor):
        with patch("services.executors.docker_executor.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="abc\n", stderr="")
            executor.submit(
                image="img:latest",
                job_id="job-008",
                env={},
                command=["true"],
            )
            call_args = mock_run.call_args[0][0]
            net_idx = call_args.index("--network")
            assert call_args[net_idx + 1] == "bridge"


class TestDockerExecutorCancel:
    def test_cancel_success(self, executor):
        with patch("services.executors.docker_executor.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            assert executor.cancel("concord-abc123") is True

    def test_cancel_not_found(self, executor):
        with patch("services.executors.docker_executor.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stderr="no such container")
            assert executor.cancel("nonexistent") is False


class TestDockerExecutorIsAlive:
    def test_is_alive_running(self, executor):
        with patch("services.executors.docker_executor.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="true\n")
            assert executor.is_alive("concord-abc") is True

    def test_is_alive_stopped(self, executor):
        with patch("services.executors.docker_executor.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="false\n")
            assert executor.is_alive("concord-abc") is False

    def test_is_alive_not_found(self, executor):
        with patch("services.executors.docker_executor.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="not found")
            assert executor.is_alive("nonexistent") is False

    def test_is_alive_error(self, executor):
        with patch("services.executors.docker_executor.subprocess.run") as mock_run:
            mock_run.side_effect = Exception("socket error")
            assert executor.is_alive("concord-abc") is None


class TestContainerNaming:
    def test_name_from_labels(self):
        name = DockerExecutor._make_container_name("cuid-abc123", labels={"app": "validation-alpha"})
        assert name.startswith("validation-alpha-")
        assert len(name) <= 63

    def test_name_sanitized(self):
        name = DockerExecutor._make_container_name("CUID_ABC!@#123", labels={"app": "My App"})
        assert all(c in "abcdefghijklmnopqrstuvwxyz0123456789-" for c in name)

    def test_name_default_prefix(self):
        name = DockerExecutor._make_container_name("abc123")
        assert name.startswith("concord-")
