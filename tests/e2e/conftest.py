"""E2E test fixtures -- spin up full platform via docker-compose."""

import atexit
import os
import subprocess
import sys
import time

import pytest
import requests

WORKSPACE_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
COMPOSE_FILE = os.path.join(WORKSPACE_ROOT, "deploy", "development", "docker-compose.test.yaml")

# When running against the development stack (nx start platform), the API is on :9001.
# When running with the test compose stack, it's on :9010.
# If the development API is already up, use it directly and skip compose/seed setup.
_DEV_API_URL = "http://localhost:9001"
_TEST_API_URL = "http://localhost:9010"
API_KEY = "ck_ci_admin_x8K2mP9vL4nQ7wR1tY6uI3oA5sD0fG"

# Prisma paths
PRISMA_DIR = os.path.join(WORKSPACE_ROOT, "prisma")
SEED_MODULE = os.path.join(PRISMA_DIR, "seed", "main.py")


def _compose(*args, timeout=180):
    """Run docker compose against the test compose file."""
    cmd = ["docker", "compose", "-f", COMPOSE_FILE, "-p", "concord-test", *args]
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


def _wait_for_api(base_url=_TEST_API_URL, deadline_seconds=90):
    """Block until the API healthcheck returns 200."""
    deadline = time.time() + deadline_seconds
    while time.time() < deadline:
        try:
            resp = requests.get(f"{base_url}/v2/docs", timeout=3)
            if resp.status_code == 200:
                return True
        except Exception:
            pass
        time.sleep(2)
    return False


def _seed_database():
    """Push schema and seed data into the test-db via prisma on the host."""
    test_db_url = "postgresql://concord:concord-test@localhost:5434/concord"
    env = os.environ.copy()
    env["DATABASE_URL"] = test_db_url
    env["DIRECT_DATABASE_URL"] = test_db_url

    # Push schema
    result = subprocess.run(
        ["prisma", "db", "push", "--skip-generate", "--accept-data-loss",
         f"--schema={os.path.join(PRISMA_DIR, 'schema.prisma')}"],
        capture_output=True, text=True, env=env, cwd=WORKSPACE_ROOT, timeout=120,
    )
    if result.returncode != 0:
        raise RuntimeError(f"prisma db push failed:\n{result.stderr}\n{result.stdout}")

    # Seed
    env["ENVIRONMENT"] = "development"
    env["SEED_ADMIN_EMAIL"] = ""
    python_paths = [
        os.path.join(WORKSPACE_ROOT, "libs", "python"),
        os.path.join(WORKSPACE_ROOT, "libs"),
        os.path.join(WORKSPACE_ROOT, "libs", "protocols"),
    ]
    env["PYTHONPATH"] = ":".join(python_paths)

    result = subprocess.run(
        [sys.executable, "-m", "seed.main"],
        capture_output=True, text=True, env=env, cwd=PRISMA_DIR, timeout=120,
    )
    if result.returncode != 0:
        raise RuntimeError(f"seed failed:\n{result.stderr}\n{result.stdout}")


def _teardown():
    """Tear down all test containers and anonymous volumes."""
    _compose("down", "-v", "--remove-orphans", timeout=60)


# Last-resort cleanup
atexit.register(_teardown)


def _dev_platform_running():
    """Check if the development platform (nx start platform) is already up."""
    try:
        resp = requests.get(f"{_DEV_API_URL}/v2/docs", timeout=3)
        return resp.status_code == 200
    except Exception:
        return False


@pytest.fixture(scope="session")
def platform():
    """Start the full platform, seed the DB, wait for health, yield, tear down.

    If the development platform is already running (e.g. via ``nx start platform``
    in CI or local dev), reuse it directly and skip compose/seed setup.
    """
    # Fast path: reuse already-running development stack
    if _dev_platform_running():
        yield {
            "api_url": _DEV_API_URL,
            "api_key": API_KEY,
            "compose_file": None,
        }
        return

    # Slow path: spin up dedicated test compose stack
    # 1. Build images (noop if already built)
    build = _compose("build")
    if build.returncode != 0:
        pytest.skip(f"docker compose build failed -- images may not exist.\n{build.stderr}")

    # 2. Start infra first so we can seed from the host
    _compose("up", "-d", "test-db", "test-minio")

    # Wait for DB to be ready
    db_deadline = time.time() + 30
    while time.time() < db_deadline:
        check = _compose(
            "exec", "-T", "test-db",
            "pg_isready", "-U", "concord",
        )
        if check.returncode == 0:
            break
        time.sleep(1)
    else:
        _teardown()
        pytest.fail("test-db did not become ready within 30s")

    # 3. Push schema + seed from host (so the API boots into a seeded DB)
    try:
        _seed_database()
    except RuntimeError as e:
        _teardown()
        pytest.fail(str(e))

    # 4. Start all services
    _compose("up", "-d")

    # 5. Wait for API health
    if not _wait_for_api(90):
        logs = _compose("logs", "--tail=80")
        _teardown()
        pytest.fail(
            f"API did not become healthy within 90s.\n"
            f"--- stdout ---\n{logs.stdout[-3000:]}\n"
            f"--- stderr ---\n{logs.stderr[-2000:]}"
        )

    yield {
        "api_url": _TEST_API_URL,
        "api_key": API_KEY,
        "compose_file": COMPOSE_FILE,
    }

    _teardown()


@pytest.fixture(scope="session")
def api(platform):
    """HTTP client wrapper for the running platform."""
    base = platform["api_url"]

    class ApiClient:
        """Thin wrapper around requests that targets the E2E API."""

        def __init__(self):
            self.base_url = base
            self._session = requests.Session()
            # Default to API key auth (admin-level, auth disabled anyway)
            self._session.headers.update({
                "Authorization": f"ApiKey {platform['api_key']}",
                "Content-Type": "application/json",
            })

        def get(self, path, **kw):
            return self._session.get(f"{self.base_url}{path}", **kw)

        def post(self, path, **kw):
            return self._session.post(f"{self.base_url}{path}", **kw)

        def put(self, path, **kw):
            return self._session.put(f"{self.base_url}{path}", **kw)

        def patch(self, path, **kw):
            return self._session.patch(f"{self.base_url}{path}", **kw)

        def delete(self, path, **kw):
            return self._session.delete(f"{self.base_url}{path}", **kw)

    return ApiClient()
