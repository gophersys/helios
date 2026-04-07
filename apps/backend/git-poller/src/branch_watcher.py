"""Branch watcher — resolves the current HEAD SHA of a remote branch.

Uses ``git ls-remote`` over SSH so no clone is required.  The SSH key path
is injected at construction time so the subprocess environment is predictable
and fully testable via dependency injection of the runner callable.
"""

import logging
import os
import subprocess
from typing import Callable, Optional

log = logging.getLogger("git-poller")

# Type alias for the subprocess runner so tests can inject a fake.
SubprocessRunner = Callable[..., subprocess.CompletedProcess]


def _default_runner(*args, **kwargs) -> subprocess.CompletedProcess:
    """Thin wrapper around subprocess.run used as the default runner.

    Args:
        *args: Positional arguments forwarded to subprocess.run.
        **kwargs: Keyword arguments forwarded to subprocess.run.

    Returns:
        The CompletedProcess result from subprocess.run.
    """
    return subprocess.run(*args, **kwargs)


class BranchWatcher:
    """Resolve the current HEAD SHA of a remote branch via git ls-remote."""

    def __init__(
        self,
        ssh_key_path: str,
        runner: SubprocessRunner = _default_runner,
    ) -> None:
        self._ssh_key_path = ssh_key_path
        self._runner = runner

    def get_branch_sha(self, ssh_url: str, branch: str) -> Optional[str]:
        """Return the current commit SHA for *branch* in *ssh_url*, or None on error."""
        env = self._build_env()
        try:
            result = self._runner(
                ["git", "ls-remote", ssh_url, f"refs/heads/{branch}"],
                capture_output=True,
                text=True,
                timeout=30,
                env=env,
            )
        except subprocess.TimeoutExpired:
            log.error("BranchWatcher: git ls-remote timed out for %s %s", ssh_url, branch)
            return None
        except Exception as exc:
            log.error("BranchWatcher: subprocess error for %s %s: %s", ssh_url, branch, exc)
            return None

        if result.returncode != 0:
            log.error(
                "BranchWatcher: git ls-remote failed for %s [%s]: %s",
                ssh_url,
                branch,
                result.stderr.strip(),
            )
            return None

        line = result.stdout.strip()
        if not line:
            log.warning("BranchWatcher: branch %s not found in %s", branch, ssh_url)
            return None

        # Output format: "<sha>\trefs/heads/<branch>"
        sha = line.split()[0]
        return sha

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _build_env(self) -> dict:
        """Build the subprocess environment with GIT_SSH_COMMAND set.

        Prefers an active SSH agent when SSH_AUTH_SOCK is set and exists.
        Falls back to specifying the key file path directly.

        Returns:
            A copy of the current environment with GIT_SSH_COMMAND configured.
        """
        env = os.environ.copy()
        sock = env.get("SSH_AUTH_SOCK", "")
        if sock and os.path.exists(sock):
            # Prefer the agent — no key file needed.
            env["GIT_SSH_COMMAND"] = (
                "ssh -o StrictHostKeyChecking=no -o BatchMode=yes"
            )
        else:
            env["GIT_SSH_COMMAND"] = (
                f"ssh -i {self._ssh_key_path} "
                "-o StrictHostKeyChecking=no "
                "-o BatchMode=yes"
            )
        return env
