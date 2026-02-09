"""Tests for ZephyrHandler."""

import subprocess
from unittest.mock import MagicMock, patch

import pytest

from src.providers.handlers.zephyr import ZephyrHandler
from src.shared.types import (
    TwisterRunRequest,
    ZephyrDevicetreeRequest,
    ZephyrShellRequest,
    ZephyrThreadsRequest,
)


@pytest.fixture
def zephyr_handler(logger, hardware):
    return ZephyrHandler(logger, hardware)


class TestZephyrShell:
    def test_shell_returns_not_implemented(self, zephyr_handler, context):
        """Shell command should return not-implemented status for now."""
        response = zephyr_handler.shell(
            ZephyrShellRequest(session_id="test", command="kernel version"),
            context,
        )
        assert response.success is False
        assert "TODO" in response.message

    def test_shell_with_timeout(self, zephyr_handler, context):
        """Shell command should accept a timeout parameter."""
        response = zephyr_handler.shell(
            ZephyrShellRequest(session_id="test", command="help", timeout_s=10.0),
            context,
        )
        assert response.success is False  # Not yet implemented


class TestZephyrDevicetree:
    def test_devicetree_returns_not_implemented(self, zephyr_handler, context):
        """Devicetree inspection should return not-implemented for now."""
        response = zephyr_handler.devicetree(
            ZephyrDevicetreeRequest(session_id="test"),
            context,
        )
        assert response.success is False
        assert "TODO" in response.message


class TestZephyrThreads:
    def test_threads_returns_not_implemented(self, zephyr_handler, context):
        """Thread listing should return not-implemented for now."""
        response = zephyr_handler.threads(
            ZephyrThreadsRequest(session_id="test"),
            context,
        )
        assert response.success is False
        assert "TODO" in response.message


class TestTwisterRun:
    def test_twister_run_success(self, zephyr_handler, context):
        """Test successful twister execution."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "All tests passed"
        mock_result.stderr = ""

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            response = zephyr_handler.twister_run(
                TwisterRunRequest(
                    target_id="nrf52840dk",
                    test_path="tests/subsys/logging",
                    timeout_s=60.0,
                ),
                context,
            )

        assert response.success is True
        assert len(response.results) > 0
        # Verify correct command was built
        call_args = mock_run.call_args[0][0]
        assert "west" in call_args
        assert "twister" in call_args
        assert "-p" in call_args
        assert "nrf52840dk" in call_args

    def test_twister_run_failure(self, zephyr_handler, context):
        """Test twister execution failure."""
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "Test failed"

        with patch("subprocess.run", return_value=mock_result):
            response = zephyr_handler.twister_run(
                TwisterRunRequest(test_path="tests/failing"),
                context,
            )

        assert response.success is False

    def test_twister_run_west_not_found(self, zephyr_handler, context):
        """Test when west/twister is not in PATH."""
        with patch("subprocess.run", side_effect=FileNotFoundError):
            response = zephyr_handler.twister_run(
                TwisterRunRequest(test_path="tests/any"),
                context,
            )

        assert response.success is False
        assert "not found" in response.message

    def test_twister_run_timeout(self, zephyr_handler, context):
        """Test twister execution timeout."""
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("west", 300)):
            response = zephyr_handler.twister_run(
                TwisterRunRequest(test_path="tests/slow", timeout_s=300.0),
                context,
            )

        assert response.success is False
        assert "timed out" in response.message

    def test_twister_run_rejects_shell_metacharacters(self, zephyr_handler, context):
        """Extra args with shell metacharacters should be rejected."""
        response = zephyr_handler.twister_run(
            TwisterRunRequest(
                test_path="tests/any",
                extra_args=["--board=nrf52840dk", "; rm -rf /"],
            ),
            context,
        )

        assert response.success is False
        assert "Invalid character" in response.message

    def test_twister_run_allows_safe_extra_args(self, zephyr_handler, context):
        """Safe extra args should pass validation."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "OK"
        mock_result.stderr = ""

        with patch("subprocess.run", return_value=mock_result):
            response = zephyr_handler.twister_run(
                TwisterRunRequest(
                    test_path="tests/any",
                    extra_args=["--inline-logs", "-v", "--retry-failed=3"],
                ),
                context,
            )

        assert response.success is True
