"""Tests for orphaned Docker container cleanup on startup."""

from __future__ import annotations

from unittest.mock import MagicMock, patch, call

import pytest

from src.worker.docker_runner import DockerBuildRunner


class TestCleanupOrphanedContainers:
    @patch("src.worker.docker_runner.subprocess")
    def test_kills_orphaned_containers(self, mock_subprocess):
        """Finds and kills orphaned concord-build-* containers."""
        mock_subprocess.run.return_value = MagicMock(
            returncode=0,
            stdout="concord-build-abc123\nconcord-build-def456\n",
        )

        DockerBuildRunner.cleanup_orphaned_containers()

        # First call: docker ps to list containers
        ps_call = mock_subprocess.run.call_args_list[0]
        assert "docker" in ps_call[0][0]
        assert "ps" in ps_call[0][0]

        # Subsequent calls: docker kill + docker rm for each container
        all_calls = mock_subprocess.run.call_args_list
        kill_calls = [c for c in all_calls if "kill" in str(c)]
        assert len(kill_calls) >= 2  # One kill per orphan

    @patch("src.worker.docker_runner.subprocess")
    def test_no_orphans(self, mock_subprocess):
        """No-op when no orphaned containers exist."""
        mock_subprocess.run.return_value = MagicMock(
            returncode=0,
            stdout="",
        )

        DockerBuildRunner.cleanup_orphaned_containers()

        # Only the ps call, no kill calls
        assert mock_subprocess.run.call_count == 1

    @patch("src.worker.docker_runner.subprocess")
    def test_docker_ps_failure(self, mock_subprocess):
        """Handles docker ps failure gracefully."""
        mock_subprocess.run.return_value = MagicMock(
            returncode=1,
            stdout="",
        )

        # Should not raise
        DockerBuildRunner.cleanup_orphaned_containers()

    @patch("src.worker.docker_runner.subprocess")
    def test_docker_kill_failure_continues(self, mock_subprocess):
        """Continues cleanup even if individual kill fails."""
        def side_effect(cmd, **kwargs):
            if "ps" in cmd:
                return MagicMock(returncode=0, stdout="container-1\ncontainer-2\n")
            if "kill" in cmd and "container-1" in cmd:
                raise Exception("kill failed")
            return MagicMock(returncode=0)

        mock_subprocess.run.side_effect = side_effect

        # Should not raise — continues to container-2
        DockerBuildRunner.cleanup_orphaned_containers()


class TestCleanupOnShutdown:
    def test_cleanup_kills_current_container(self):
        """cleanup() kills the currently tracked container."""
        runner = DockerBuildRunner()
        runner._current_container = "concord-build-active-1"

        with patch("src.worker.docker_runner.subprocess") as mock_sub:
            runner.cleanup()

        mock_sub.run.assert_called()
        kill_call = mock_sub.run.call_args_list[0]
        assert "kill" in kill_call[0][0]
        assert "concord-build-active-1" in kill_call[0][0]

    def test_cleanup_no_current_container(self):
        """cleanup() is a no-op when no container is tracked."""
        runner = DockerBuildRunner()
        runner._current_container = None

        with patch("src.worker.docker_runner.subprocess") as mock_sub:
            runner.cleanup()

        mock_sub.run.assert_not_called()
