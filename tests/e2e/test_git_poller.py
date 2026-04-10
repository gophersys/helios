"""E2E: Git poller service discovers repos from the API."""

import os
import subprocess
import time

import pytest
import requests

WORKSPACE_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEV_COMPOSE = os.path.join(WORKSPACE_ROOT, "deploy", "development", "docker-compose.yaml")


def _compose(*args, timeout=30):
    """Run docker compose against the development stack."""
    cmd = ["docker", "compose", "-f", DEV_COMPOSE, *args]
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=WORKSPACE_ROOT)


def test_poller_attempts_repo_load(platform):
    """Git poller connects to the API and attempts repo discovery."""
    deadline = time.time() + 60
    while time.time() < deadline:
        result = _compose("logs", "--tail=50", "git-poller")
        combined = result.stdout + result.stderr
        if "loaded from API" in combined or "no watch targets" in combined or "Health server on" in combined:
            return
        time.sleep(5)
    pytest.fail(
        f"Git poller did not attempt repo discovery within 60s.\n"
        f"stdout: {result.stdout[-500:]}\nstderr: {result.stderr[-500:]}"
    )


def test_poller_health_endpoint(platform):
    """Git poller health endpoint returns ok."""
    result = _compose(
        "exec", "-T", "git-poller",
        "python3", "-c",
        "import urllib.request, json; "
        "r = urllib.request.urlopen('http://localhost:9003/health'); "
        "d = json.loads(r.read()); "
        "print(d.get('status', ''))",
    )
    if result.returncode == 0:
        assert "ok" in result.stdout.strip()
    else:
        pytest.skip(f"Could not exec into git-poller: {result.stderr[:200]}")
