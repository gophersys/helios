"""Staging smoke tests — verify live API endpoints after deploy.

Run against a live staging instance:
    STAGING_URL=https://staging.concord.local \
    STAGING_API_KEY=ck_ci_admin_x8K2mP9vL4nQ7wR1tY6uI3oA5sD0fG \
    pytest tests/integration/test_staging_smoke.py -v

Requires:
    - STAGING_URL: Base URL of the staging API (no trailing slash)
    - STAGING_API_KEY: Valid API key with products:view + builds:view permissions

These tests are excluded from the normal test suite by the @pytest.mark.staging marker.
"""

import os

import pytest
import requests

STAGING_URL = os.environ.get("STAGING_URL", "")
STAGING_API_KEY = os.environ.get("STAGING_API_KEY", "")

pytestmark = pytest.mark.staging


def _skip_if_not_configured():
    if not STAGING_URL:
        pytest.skip("STAGING_URL not set")
    if not STAGING_API_KEY:
        pytest.skip("STAGING_API_KEY not set")


def _get(path: str, auth: bool = True, **kwargs) -> requests.Response:
    """Make a GET request to the staging API."""
    headers = {}
    if auth:
        headers["Authorization"] = f"ApiKey {STAGING_API_KEY}"
    return requests.get(
        f"{STAGING_URL}{path}",
        headers=headers,
        timeout=10,
        verify=False,
        **kwargs,
    )


class TestStagingHealth:
    """Basic health and docs endpoint."""

    def test_docs_returns_200_without_auth(self):
        """OpenAPI docs should be publicly accessible."""
        _skip_if_not_configured()
        resp = _get("/v2/docs", auth=False)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"


class TestStagingProducts:
    """Product endpoints with auth."""

    def test_list_products_returns_seeded_data(self):
        """GET /v2/products should return seeded products (Alpha, Sigma5, Theta, IWSCK)."""
        _skip_if_not_configured()
        resp = _get("/v2/products?limit=50")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"

        body = resp.json()
        products = body.get("data", {}).get("data", [])
        names = {p["name"] for p in products}
        assert len(products) >= 4, f"Expected at least 4 products, got {len(products)}: {names}"

    def test_alpha_product_has_build_config(self):
        """Alpha product should have buildConfig with targets and cfw fields."""
        _skip_if_not_configured()
        resp = _get("/v2/products?limit=50")
        assert resp.status_code == 200

        body = resp.json()
        products = body.get("data", {}).get("data", [])
        alpha = next((p for p in products if "Alpha" in p.get("name", "")), None)
        assert alpha is not None, f"Alpha product not found in: {[p['name'] for p in products]}"

        bc = alpha.get("buildConfig")
        assert bc is not None, "Alpha buildConfig is null — run seed.py against staging DB"
        assert "targets" in bc, f"buildConfig missing 'targets': {list(bc.keys())}"
        assert "cfw" in bc, f"buildConfig missing 'cfw': {list(bc.keys())}"
        assert "app" in bc["targets"], "buildConfig.targets missing 'app'"
        assert "comms" in bc["targets"], "buildConfig.targets missing 'comms'"


class TestStagingPipelines:
    """Pipeline endpoints with auth."""

    def test_list_pipelines_returns_200(self):
        """GET /v2/builds/pipelines should return a paginated response."""
        _skip_if_not_configured()
        resp = _get("/v2/builds/pipelines?limit=5")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"

        body = resp.json()
        assert "data" in body, f"Missing 'data' envelope: {list(body.keys())}"


class TestStagingBoardDiscovery:
    """Board discovery endpoints — expected to fail until ck_boards repo is configured."""

    def test_board_branches_returns_clean_error(self):
        """GET /v2/products/boards/branches should return a structured error, not a 500 traceback."""
        _skip_if_not_configured()
        resp = _get("/v2/products/boards/branches")
        # Accept 200 (if configured) or 4xx/5xx (if not) — but body must be JSON, not raw traceback
        try:
            body = resp.json()
        except Exception:
            pytest.fail(
                f"Response is not valid JSON (status {resp.status_code}): {resp.text[:300]}"
            )
        # If it's an error, the envelope should have an errors array
        if resp.status_code >= 400:
            assert "errors" in body or "error" in body or "message" in body, (
                f"Error response missing structured error field (status {resp.status_code}): {body}"
            )
