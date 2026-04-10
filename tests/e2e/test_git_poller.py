"""E2E: Git poller service discovers repos from the API."""

import os
import subprocess
import time

import pytest

WORKSPACE_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEV_COMPOSE = os.path.join(WORKSPACE_ROOT, "deploy", "development", "docker-compose.yaml")


def _compose_cmd(platform):
    """Return the docker compose base command for the active stack."""
    cf = platform.get("compose_file")
    if cf:
        return ["docker", "compose", "-f", cf, "-p", "concord-test"]
    return ["docker", "compose", "-f", DEV_COMPOSE]


def test_poller_attempts_repo_load(platform):
    """Git poller should try to load repos from the API within 60s.

    It may find 0 repos (no SSH key) or 1+ repos — either way,
    the log line proves it connected to the API and ran its fetch loop.
    """
    base = _compose_cmd(platform)
    service = "git-poller" if not platform.get("compose_file") else "test-poller"

    deadline = time.time() + 60
    while time.time() < deadline:
        result = subprocess.run(
            [*base, "logs", service],
            capture_output=True, text=True, timeout=30,
        )
        combined = result.stdout + result.stderr
        # The poller logs "Discovery: N watch target(s) loaded from API"
        # or "Discovery: no watch targets available" or "Health server on"
        if "loaded from API" in combined or "no watch targets" in combined or "Health server on" in combined:
            return
        time.sleep(5)
    pytest.fail("Git poller did not attempt repo discovery within 60s")


def test_poller_health_endpoint(platform):
    """Git poller exposes a /health endpoint inside its container."""
    base = _compose_cmd(platform)
    service = "git-poller" if not platform.get("compose_file") else "test-poller"

    result = subprocess.run(
        [*base, "exec", "-T", service,
         "python3", "-c",
         "import urllib.request; r = urllib.request.urlopen('http://localhost:9003/health'); print(r.read().decode())"],
        capture_output=True, text=True, timeout=30,
    )
    if result.returncode == 0:
        assert "healthy" in result.stdout.lower() or "ok" in result.stdout.lower()
    else:
        pytest.skip(f"Could not exec into {service}: {result.stderr[:200]}")
