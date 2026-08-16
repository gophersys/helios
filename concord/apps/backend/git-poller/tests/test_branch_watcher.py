"""Tests for BranchWatcher."""

import subprocess
from unittest.mock import MagicMock

import pytest

from branch_watcher import BranchWatcher


def _make_result(returncode: int, stdout: str = "", stderr: str = "") -> MagicMock:
    r = MagicMock(spec=subprocess.CompletedProcess)
    r.returncode = returncode
    r.stdout = stdout
    r.stderr = stderr
    return r


SSH_URL = "git@bitbucket.org:corekinect/alpha_fw.git"
BRANCH = "concord-main"
SHA = "abc123def456789012345678901234567890abcd"


class TestBranchWatcherGetBranchSha:
    def test_returns_sha_on_success(self):
        runner = MagicMock(return_value=_make_result(0, f"{SHA}\trefs/heads/{BRANCH}\n"))
        watcher = BranchWatcher(ssh_key_path="/tmp/key", runner=runner)
        result = watcher.get_branch_sha(SSH_URL, BRANCH)
        assert result == SHA

    def test_returns_none_on_nonzero_exit(self):
        runner = MagicMock(return_value=_make_result(128, stderr="Connection refused"))
        watcher = BranchWatcher(ssh_key_path="/tmp/key", runner=runner)
        result = watcher.get_branch_sha(SSH_URL, BRANCH)
        assert result is None

    def test_returns_none_on_empty_output(self):
        runner = MagicMock(return_value=_make_result(0, ""))
        watcher = BranchWatcher(ssh_key_path="/tmp/key", runner=runner)
        result = watcher.get_branch_sha(SSH_URL, BRANCH)
        assert result is None

    def test_returns_none_on_timeout(self):
        runner = MagicMock(side_effect=subprocess.TimeoutExpired(["git"], 30))
        watcher = BranchWatcher(ssh_key_path="/tmp/key", runner=runner)
        result = watcher.get_branch_sha(SSH_URL, BRANCH)
        assert result is None

    def test_returns_none_on_os_error(self):
        runner = MagicMock(side_effect=OSError("git not found"))
        watcher = BranchWatcher(ssh_key_path="/tmp/key", runner=runner)
        result = watcher.get_branch_sha(SSH_URL, BRANCH)
        assert result is None

    def test_calls_git_ls_remote_with_correct_args(self):
        runner = MagicMock(return_value=_make_result(0, f"{SHA}\trefs/heads/{BRANCH}\n"))
        watcher = BranchWatcher(ssh_key_path="/tmp/key", runner=runner)
        watcher.get_branch_sha(SSH_URL, BRANCH)

        call_args = runner.call_args[0][0]
        assert call_args[0] == "git"
        assert call_args[1] == "ls-remote"
        assert call_args[2] == SSH_URL
        assert call_args[3] == f"refs/heads/{BRANCH}"

    def test_parses_sha_from_tab_separated_output(self):
        # ls-remote output has sha<TAB>ref_name
        raw = f"{SHA}\trefs/heads/{BRANCH}"
        runner = MagicMock(return_value=_make_result(0, raw))
        watcher = BranchWatcher(ssh_key_path="/tmp/key", runner=runner)
        result = watcher.get_branch_sha(SSH_URL, BRANCH)
        assert result == SHA

    def test_sets_git_ssh_command_in_env(self, monkeypatch):
        monkeypatch.delenv("SSH_AUTH_SOCK", raising=False)
        captured_env = {}

        def capturing_runner(*args, **kwargs):
            captured_env.update(kwargs.get("env", {}))
            return _make_result(0, f"{SHA}\trefs/heads/{BRANCH}\n")

        watcher = BranchWatcher(ssh_key_path="/custom/id_rsa", runner=capturing_runner)
        watcher.get_branch_sha(SSH_URL, BRANCH)
        assert "GIT_SSH_COMMAND" in captured_env
        assert "/custom/id_rsa" in captured_env["GIT_SSH_COMMAND"]

    def test_uses_ssh_agent_when_sock_present(self, monkeypatch, tmp_path):
        # Create a fake socket file
        fake_sock = str(tmp_path / "ssh-agent.sock")
        open(fake_sock, "w").close()
        monkeypatch.setenv("SSH_AUTH_SOCK", fake_sock)

        captured_env = {}

        def capturing_runner(*args, **kwargs):
            captured_env.update(kwargs.get("env", {}))
            return _make_result(0, f"{SHA}\trefs/heads/{BRANCH}\n")

        watcher = BranchWatcher(ssh_key_path="/tmp/key", runner=capturing_runner)
        watcher.get_branch_sha(SSH_URL, BRANCH)
        # With agent, the key path should NOT appear in GIT_SSH_COMMAND
        assert "/tmp/key" not in captured_env.get("GIT_SSH_COMMAND", "")
