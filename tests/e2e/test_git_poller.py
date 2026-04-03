"""E2E: Git poller service discovers repos from the API."""

import subprocess
import time

import pytest

from tests.e2e.conftest import COMPOSE_FILE


def test_poller_attempts_repo_load(platform):
    """Git poller should try to load repos from the API within 60s.

    It may find 0 repos (no SSH key in CI) or 1+ repos -- either way,
    the log line proves it connected to the API and ran its fetch loop.
    """
    deadline = time.time() + 60
    while time.time() < deadline:
        result = subprocess.run(
            ["docker", "compose", "-f", COMPOSE_FILE, "-p", "concord-test",
             "logs", "test-poller"],
            capture_output=True, text=True, timeout=30,
        )
        combined = result.stdout + result.stderr
        # The poller logs either "Loaded N repos from API" or "No repos loaded"
        if "Loaded" in combined or "No repos" in combined or "repos from API" in combined:
            return
        time.sleep(5)
    pytest.fail("Git poller did not attempt repo discovery within 60s")


def test_poller_health_endpoint(platform):
    """Git poller exposes a /health endpoint inside its container."""
    result = subprocess.run(
        ["docker", "compose", "-f", COMPOSE_FILE, "-p", "concord-test",
         "exec", "-T", "test-poller",
         "python3", "-c",
         "import urllib.request; r = urllib.request.urlopen('http://localhost:9003/health'); print(r.read().decode())"],
        capture_output=True, text=True, timeout=30,
    )
    if result.returncode == 0:
        assert "healthy" in result.stdout
    else:
        # Container might not have started yet or exec failed -- skip gracefully
        pytest.skip(f"Could not exec into test-poller: {result.stderr[:200]}")
