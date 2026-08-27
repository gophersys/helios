"""Smoke test fixtures — test against a deployed environment."""

import os
import pytest
import requests


def pytest_addoption(parser):
    parser.addoption("--target-url", default=os.environ.get("SMOKE_TARGET_URL", "https://staging.concord.local"))
    parser.addoption("--api-key", default=os.environ.get("SMOKE_API_KEY", "ck_ci_admin_x8K2mP9vL4nQ7wR1tY6uI3oA5sD0fG"))


@pytest.fixture(scope="session")
def target_url(request):
    return request.config.getoption("--target-url")


@pytest.fixture(scope="session")
def api_key(request):
    return request.config.getoption("--api-key")


@pytest.fixture(scope="session")
def api(target_url, api_key):
    """HTTP client pointing at the deployed environment."""
    session = requests.Session()
    session.verify = False  # self-signed certs
    session.headers.update({
        "Authorization": f"ApiKey {api_key}",
        "Content-Type": "application/json",
    })

    class SmokeClient:
        def get(self, path, **kw): return session.get(f"{target_url}{path}", **kw)
        def post(self, path, **kw): return session.post(f"{target_url}{path}", **kw)

    return SmokeClient()
