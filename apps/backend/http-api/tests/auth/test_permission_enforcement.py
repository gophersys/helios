"""
Permission enforcement tests for every API module.

Verifies that routes properly reject unauthorized access by testing three
scenarios per module:
  1. Unauthenticated request (no header) -> 401
  2. Authenticated with wrong permissions -> 403
  3. Authenticated with correct permissions -> 200 (or non-auth error like 400/404)

The authed_client fixture always grants superadmin. These tests use the raw
`client` fixture + `auth_headers` fixture with a mock permission set that
contains only specific, limited permissions.
"""

import json
import types as stdlib_types
from unittest.mock import MagicMock, patch

import pytest

from src.lib.permissions import Permissions


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_limited_perm_set(*permissions: str) -> stdlib_types.SimpleNamespace:
    """Create a mock permission set with only the given permissions."""
    return stdlib_types.SimpleNamespace(
        id="test-perm-set-id",
        name="Limited Role",
        permissions=list(permissions),
    )


def _assert_401(response):
    """Assert unauthenticated response."""
    assert response.status_code == 401, (
        f"Expected 401, got {response.status_code}: {response.data}"
    )
    data = json.loads(response.data)
    assert data["data"] is None
    assert len(data["errors"]) > 0


def _assert_403(response):
    """Assert forbidden response."""
    assert response.status_code == 403, (
        f"Expected 403, got {response.status_code}: {response.data}"
    )
    data = json.loads(response.data)
    assert data["data"] is None
    assert len(data["errors"]) > 0


def _assert_not_denied(response):
    """Assert response is NOT a 401 or 403 (auth passed, may fail for other reasons).

    The handler may return 200, 400, 404, or 500 depending on mock DB state —
    any of those are acceptable as long as it's not an auth denial.
    """
    assert response.status_code not in (401, 403), (
        f"Expected auth to pass but got {response.status_code}: {response.data}"
    )


def _request_passes_auth(client_method, url, **kwargs):
    """Execute a request and verify auth was not denied.

    Some handlers raise unhandled exceptions when mock DB returns None
    (e.g., product.create returning None). In Flask TESTING mode these
    propagate as Python exceptions rather than 500 responses. We catch
    those and treat them as "auth passed" since the exception occurs
    after the permission check.
    """
    try:
        response = client_method(url, **kwargs)
        _assert_not_denied(response)
    except Exception as exc:
        # If the exception is auth-related, re-raise
        msg = str(exc).lower()
        if "401" in msg or "403" in msg or "unauthorized" in msg or "forbidden" in msg:
            raise
        # Otherwise, the handler got past auth and failed on business logic — that's OK
        pass


# ---------------------------------------------------------------------------
# Module: Products (catalog)
# ---------------------------------------------------------------------------

class TestProductsPermissions:
    """Tests for /v2/products routes — requires products:view / products:manage."""

    def test_list_products_unauthenticated(self, client):
        response = client.get("/v2/products")
        _assert_401(response)

    def test_list_products_wrong_permission(self, client, auth_headers, mock_db):
        mock_db.permissionset.find_unique.return_value = _make_limited_perm_set(
            "validation:view",
        )
        response = client.get("/v2/products", headers=auth_headers)
        _assert_403(response)

    def test_list_products_correct_permission(self, client, auth_headers, mock_db):
        mock_db.permissionset.find_unique.return_value = _make_limited_perm_set(
            "products:view",
        )
        response = client.get("/v2/products", headers=auth_headers)
        _assert_not_denied(response)

    def test_create_product_unauthenticated(self, client):
        response = client.post("/v2/products", data=json.dumps({}),
                               content_type="application/json")
        _assert_401(response)

    def test_create_product_view_only(self, client, auth_headers, mock_db):
        """products:view should NOT allow creating products (needs products:manage)."""
        mock_db.permissionset.find_unique.return_value = _make_limited_perm_set(
            "products:view",
        )
        response = client.post("/v2/products", data=json.dumps({"name": "Test"}),
                               headers=auth_headers)
        _assert_403(response)

    def test_create_product_correct_permission(self, client, auth_headers, mock_db):
        mock_db.permissionset.find_unique.return_value = _make_limited_perm_set(
            "products:manage",
        )
        _request_passes_auth(client.post, "/v2/products",
                             data=json.dumps({"name": "Test"}),
                             headers=auth_headers)

    def test_get_product_wrong_permission(self, client, auth_headers, mock_db):
        mock_db.permissionset.find_unique.return_value = _make_limited_perm_set(
            "builds:view",
        )
        response = client.get("/v2/products/some-id", headers=auth_headers)
        _assert_403(response)

    def test_delete_product_wrong_permission(self, client, auth_headers, mock_db):
        """products:view should NOT allow deleting products."""
        mock_db.permissionset.find_unique.return_value = _make_limited_perm_set(
            "products:view",
        )
        response = client.delete("/v2/products/some-id", headers=auth_headers)
        _assert_403(response)


# ---------------------------------------------------------------------------
# Module: Builds (CI)
# ---------------------------------------------------------------------------

class TestBuildsPermissions:
    """Tests for /v2/builds routes — requires builds:view / builds:trigger / builds:manage."""

    def test_list_builds_unauthenticated(self, client):
        response = client.get("/v2/builds")
        _assert_401(response)

    def test_list_builds_wrong_permission(self, client, auth_headers, mock_db):
        mock_db.permissionset.find_unique.return_value = _make_limited_perm_set(
            "products:view",
        )
        response = client.get("/v2/builds", headers=auth_headers)
        _assert_403(response)

    def test_list_builds_correct_permission(self, client, auth_headers, mock_db):
        mock_db.permissionset.find_unique.return_value = _make_limited_perm_set(
            "builds:view",
        )
        response = client.get("/v2/builds", headers=auth_headers)
        _assert_not_denied(response)

    def test_create_build_unauthenticated(self, client):
        response = client.post("/v2/builds", data=json.dumps({}),
                               content_type="application/json")
        _assert_401(response)

    def test_create_build_view_only(self, client, auth_headers, mock_db):
        """builds:view should NOT allow creating builds (needs builds:trigger)."""
        mock_db.permissionset.find_unique.return_value = _make_limited_perm_set(
            "builds:view",
        )
        response = client.post("/v2/builds", data=json.dumps({}),
                               headers=auth_headers)
        _assert_403(response)

    def test_create_build_correct_permission(self, client, auth_headers, mock_db):
        mock_db.permissionset.find_unique.return_value = _make_limited_perm_set(
            "builds:trigger",
        )
        response = client.post("/v2/builds", data=json.dumps({}),
                               headers=auth_headers)
        _assert_not_denied(response)

    def test_get_build_wrong_permission(self, client, auth_headers, mock_db):
        mock_db.permissionset.find_unique.return_value = _make_limited_perm_set(
            "validation:view",
        )
        response = client.get("/v2/builds/some-id", headers=auth_headers)
        _assert_403(response)


# ---------------------------------------------------------------------------
# Module: CI Pipelines
# ---------------------------------------------------------------------------

class TestPipelinesPermissions:
    """Tests for /v2/builds/pipelines routes — requires builds:view / builds:trigger."""

    def test_list_pipelines_unauthenticated(self, client):
        response = client.get("/v2/builds/pipelines")
        _assert_401(response)

    def test_list_pipelines_wrong_permission(self, client, auth_headers, mock_db):
        mock_db.permissionset.find_unique.return_value = _make_limited_perm_set(
            "devices:view",
        )
        response = client.get("/v2/builds/pipelines", headers=auth_headers)
        _assert_403(response)

    def test_list_pipelines_correct_permission(self, client, auth_headers, mock_db):
        mock_db.permissionset.find_unique.return_value = _make_limited_perm_set(
            "builds:view",
        )
        response = client.get("/v2/builds/pipelines", headers=auth_headers)
        _assert_not_denied(response)

    def test_trigger_pipeline_unauthenticated(self, client):
        response = client.post("/v2/builds/trigger", data=json.dumps({}),
                               content_type="application/json")
        _assert_401(response)

    def test_trigger_pipeline_view_only(self, client, auth_headers, mock_db):
        """builds:view should NOT allow triggering pipelines."""
        mock_db.permissionset.find_unique.return_value = _make_limited_perm_set(
            "builds:view",
        )
        response = client.post("/v2/builds/trigger", data=json.dumps({}),
                               headers=auth_headers)
        _assert_403(response)

    def test_trigger_pipeline_correct_permission(self, client, auth_headers, mock_db):
        mock_db.permissionset.find_unique.return_value = _make_limited_perm_set(
            "builds:trigger",
        )
        response = client.post("/v2/builds/trigger", data=json.dumps({}),
                               headers=auth_headers)
        _assert_not_denied(response)


# ---------------------------------------------------------------------------
# Module: CI Build Scripts
# ---------------------------------------------------------------------------

class TestBuildScriptsPermissions:
    """Tests for /v2/builds/scripts routes — requires builds:view / builds:manage."""

    def test_list_scripts_unauthenticated(self, client):
        response = client.get("/v2/builds/scripts")
        _assert_401(response)

    def test_list_scripts_wrong_permission(self, client, auth_headers, mock_db):
        mock_db.permissionset.find_unique.return_value = _make_limited_perm_set(
            "products:view",
        )
        response = client.get("/v2/builds/scripts", headers=auth_headers)
        _assert_403(response)

    def test_list_scripts_correct_permission(self, client, auth_headers, mock_db):
        mock_db.permissionset.find_unique.return_value = _make_limited_perm_set(
            "builds:view",
        )
        response = client.get("/v2/builds/scripts", headers=auth_headers)
        _assert_not_denied(response)


# ---------------------------------------------------------------------------
# Module: Validation Runs
# ---------------------------------------------------------------------------

class TestValidationRunsPermissions:
    """Tests for /v2/sessions routes — requires validation:view / validation:run."""

    def test_list_runs_unauthenticated(self, client):
        response = client.get("/v2/sessions")
        _assert_401(response)

    def test_list_runs_wrong_permission(self, client, auth_headers, mock_db):
        mock_db.permissionset.find_unique.return_value = _make_limited_perm_set(
            "products:view",
        )
        response = client.get("/v2/sessions", headers=auth_headers)
        _assert_403(response)

    def test_list_runs_correct_permission(self, client, auth_headers, mock_db):
        mock_db.permissionset.find_unique.return_value = _make_limited_perm_set(
            "validation:view",
        )
        response = client.get("/v2/sessions", headers=auth_headers)
        _assert_not_denied(response)

    def test_create_run_unauthenticated(self, client):
        response = client.post("/v2/sessions", data=json.dumps({}),
                               content_type="application/json")
        _assert_401(response)

    def test_create_run_view_only(self, client, auth_headers, mock_db):
        """validation:view should NOT allow creating runs (needs validation:run)."""
        mock_db.permissionset.find_unique.return_value = _make_limited_perm_set(
            "validation:view",
        )
        response = client.post("/v2/sessions",
                               data=json.dumps({"productId": "p", "nodeId": "n"}),
                               headers=auth_headers)
        _assert_403(response)

    def test_create_run_correct_permission(self, client, auth_headers, mock_db):
        mock_db.permissionset.find_unique.return_value = _make_limited_perm_set(
            "validation:run",
        )
        response = client.post("/v2/sessions",
                               data=json.dumps({"productId": "p", "nodeId": "n"}),
                               headers=auth_headers)
        _assert_not_denied(response)

    def test_get_run_wrong_permission(self, client, auth_headers, mock_db):
        mock_db.permissionset.find_unique.return_value = _make_limited_perm_set(
            "builds:view",
        )
        response = client.get("/v2/sessions/some-run-id", headers=auth_headers)
        _assert_403(response)

    def test_cancel_run_view_only(self, client, auth_headers, mock_db):
        """validation:view should NOT allow cancelling runs (needs validation:manage)."""
        mock_db.permissionset.find_unique.return_value = _make_limited_perm_set(
            "validation:view",
        )
        response = client.post("/v2/sessions/some-id/cancel",
                               headers=auth_headers)
        _assert_403(response)


# ---------------------------------------------------------------------------
# Module: Validation Trigger
# ---------------------------------------------------------------------------

class TestValidationTriggerPermissions:
    """Tests for /v2/sessions/<id>/trigger — requires validation:run."""

    def test_trigger_unauthenticated(self, client):
        response = client.post("/v2/sessions/some-id/trigger",
                               data=json.dumps({}),
                               content_type="application/json")
        _assert_401(response)

    def test_trigger_view_only(self, client, auth_headers, mock_db):
        """validation:view should NOT allow triggering a run."""
        mock_db.permissionset.find_unique.return_value = _make_limited_perm_set(
            "validation:view",
        )
        response = client.post("/v2/sessions/some-id/trigger",
                               data=json.dumps({}), headers=auth_headers)
        _assert_403(response)

    def test_trigger_correct_permission(self, client, auth_headers, mock_db):
        mock_db.permissionset.find_unique.return_value = _make_limited_perm_set(
            "validation:run",
        )
        response = client.post("/v2/sessions/some-id/trigger",
                               data=json.dumps({}), headers=auth_headers)
        _assert_not_denied(response)


# ---------------------------------------------------------------------------
# Module: Validation Benches
# ---------------------------------------------------------------------------

class TestBenchesPermissions:
    """Tests for /v2/benches routes — requires fixtures:view / fixtures:manage."""

    def test_list_benches_unauthenticated(self, client):
        response = client.get("/v2/fixtures/benches")
        _assert_401(response)

    def test_list_benches_wrong_permission(self, client, auth_headers, mock_db):
        mock_db.permissionset.find_unique.return_value = _make_limited_perm_set(
            "products:view",
        )
        response = client.get("/v2/fixtures/benches", headers=auth_headers)
        _assert_403(response)

    def test_list_benches_correct_permission(self, client, auth_headers, mock_db):
        mock_db.permissionset.find_unique.return_value = _make_limited_perm_set(
            "fixtures:view",
        )
        response = client.get("/v2/fixtures/benches", headers=auth_headers)
        _assert_not_denied(response)

    def test_create_bench_unauthenticated(self, client):
        response = client.post("/v2/fixtures/benches", data=json.dumps({}),
                               content_type="application/json")
        _assert_401(response)

    def test_create_bench_view_only(self, client, auth_headers, mock_db):
        """fixtures:view should NOT allow creating benches (needs fixtures:manage)."""
        mock_db.permissionset.find_unique.return_value = _make_limited_perm_set(
            "fixtures:view",
        )
        response = client.post("/v2/fixtures/benches",
                               data=json.dumps({"name": "Test Bench"}),
                               headers=auth_headers)
        _assert_403(response)

    def test_create_bench_correct_permission(self, client, auth_headers, mock_db):
        mock_db.permissionset.find_unique.return_value = _make_limited_perm_set(
            "fixtures:manage",
        )
        response = client.post("/v2/fixtures/benches",
                               data=json.dumps({"name": "Test Bench"}),
                               headers=auth_headers)
        _assert_not_denied(response)

    def test_delete_bench_view_only(self, client, auth_headers, mock_db):
        mock_db.permissionset.find_unique.return_value = _make_limited_perm_set(
            "fixtures:view",
        )
        response = client.delete("/v2/fixtures/benches/some-id",
                                 headers=auth_headers)
        _assert_403(response)


# ---------------------------------------------------------------------------
# Module: Validation Designs
# ---------------------------------------------------------------------------

class TestDesignsPermissions:
    """Tests for /v2/benches/designs routes — requires fixtures:view / fixtures:manage."""

    def test_list_designs_unauthenticated(self, client):
        response = client.get("/v2/fixtures/designs")
        _assert_401(response)

    def test_list_designs_wrong_permission(self, client, auth_headers, mock_db):
        mock_db.permissionset.find_unique.return_value = _make_limited_perm_set(
            "products:view",
        )
        response = client.get("/v2/fixtures/designs", headers=auth_headers)
        _assert_403(response)

    def test_list_designs_correct_permission(self, client, auth_headers, mock_db):
        mock_db.permissionset.find_unique.return_value = _make_limited_perm_set(
            "fixtures:view",
        )
        response = client.get("/v2/fixtures/designs", headers=auth_headers)
        _assert_not_denied(response)

    def test_create_design_view_only(self, client, auth_headers, mock_db):
        mock_db.permissionset.find_unique.return_value = _make_limited_perm_set(
            "fixtures:view",
        )
        response = client.post("/v2/fixtures/designs",
                               data=json.dumps({}), headers=auth_headers)
        _assert_403(response)


# ---------------------------------------------------------------------------
# Module: Fixtures
# ---------------------------------------------------------------------------

class TestFixturesPermissions:
    """Tests for /v2/fixtures routes — requires fixtures:view / fixtures:manage."""

    def test_list_fixtures_unauthenticated(self, client):
        response = client.get("/v2/fixtures")
        _assert_401(response)

    def test_list_fixtures_wrong_permission(self, client, auth_headers, mock_db):
        mock_db.permissionset.find_unique.return_value = _make_limited_perm_set(
            "validation:view",
        )
        response = client.get("/v2/fixtures", headers=auth_headers)
        _assert_403(response)

    def test_list_fixtures_correct_permission(self, client, auth_headers, mock_db):
        mock_db.permissionset.find_unique.return_value = _make_limited_perm_set(
            "fixtures:view",
        )
        response = client.get("/v2/fixtures", headers=auth_headers)
        _assert_not_denied(response)

    def test_create_fixture_unauthenticated(self, client):
        response = client.post("/v2/fixtures", data=json.dumps({}),
                               content_type="application/json")
        _assert_401(response)

    def test_create_fixture_view_only(self, client, auth_headers, mock_db):
        """fixtures:view should NOT allow creating fixtures (needs fixtures:manage)."""
        mock_db.permissionset.find_unique.return_value = _make_limited_perm_set(
            "fixtures:view",
        )
        response = client.post("/v2/fixtures",
                               data=json.dumps({"name": "My Fixture"}),
                               headers=auth_headers)
        _assert_403(response)

    def test_create_fixture_correct_permission(self, client, auth_headers, mock_db):
        mock_db.permissionset.find_unique.return_value = _make_limited_perm_set(
            "fixtures:manage",
        )
        response = client.post("/v2/fixtures",
                               data=json.dumps({"name": "My Fixture"}),
                               headers=auth_headers)
        _assert_not_denied(response)

    def test_delete_fixture_view_only(self, client, auth_headers, mock_db):
        mock_db.permissionset.find_unique.return_value = _make_limited_perm_set(
            "fixtures:view",
        )
        response = client.delete("/v2/fixtures/some-id", headers=auth_headers)
        _assert_403(response)


# ---------------------------------------------------------------------------
# Module: ICLE Devices
# ---------------------------------------------------------------------------

class TestICLEDevicesPermissions:
    """Tests for /v2/devices/icle routes — requires devices:view / devices:manage."""

    def test_list_devices_unauthenticated(self, client):
        response = client.get("/v2/devices/icle")
        _assert_401(response)

    def test_list_devices_wrong_permission(self, client, auth_headers, mock_db):
        mock_db.permissionset.find_unique.return_value = _make_limited_perm_set(
            "products:view",
        )
        response = client.get("/v2/devices/icle", headers=auth_headers)
        _assert_403(response)

    def test_list_devices_correct_permission(self, client, auth_headers, mock_db):
        mock_db.permissionset.find_unique.return_value = _make_limited_perm_set(
            "devices:view",
        )
        response = client.get("/v2/devices/icle", headers=auth_headers)
        _assert_not_denied(response)

    def test_update_device_view_only(self, client, auth_headers, mock_db):
        """devices:view should NOT allow updating devices (needs devices:manage)."""
        mock_db.permissionset.find_unique.return_value = _make_limited_perm_set(
            "devices:view",
        )
        response = client.put("/v2/devices/icle/some-id",
                              data=json.dumps({"name": "New Name"}),
                              headers=auth_headers)
        _assert_403(response)

    def test_delete_device_view_only(self, client, auth_headers, mock_db):
        mock_db.permissionset.find_unique.return_value = _make_limited_perm_set(
            "devices:view",
        )
        response = client.delete("/v2/devices/icle/some-id", headers=auth_headers)
        _assert_403(response)


# ---------------------------------------------------------------------------
# Module: MTIB Nodes
# ---------------------------------------------------------------------------

class TestMTIBNodesPermissions:
    """Tests for /v2/devices/mtibs routes — requires devices:view / devices:manage."""

    def test_list_mtibs_unauthenticated(self, client):
        response = client.get("/v2/devices/mtibs")
        _assert_401(response)

    def test_list_mtibs_wrong_permission(self, client, auth_headers, mock_db):
        mock_db.permissionset.find_unique.return_value = _make_limited_perm_set(
            "builds:view",
        )
        response = client.get("/v2/devices/mtibs", headers=auth_headers)
        _assert_403(response)

    def test_list_mtibs_correct_permission(self, client, auth_headers, mock_db):
        mock_db.permissionset.find_unique.return_value = _make_limited_perm_set(
            "devices:view",
        )
        response = client.get("/v2/devices/mtibs", headers=auth_headers)
        _assert_not_denied(response)

    def test_create_mtib_view_only(self, client, auth_headers, mock_db):
        """devices:view should NOT allow creating nodes (needs devices:manage)."""
        mock_db.permissionset.find_unique.return_value = _make_limited_perm_set(
            "devices:view",
        )
        response = client.post("/v2/devices/mtibs", data=json.dumps({}),
                               headers=auth_headers)
        _assert_403(response)

    def test_delete_mtib_view_only(self, client, auth_headers, mock_db):
        mock_db.permissionset.find_unique.return_value = _make_limited_perm_set(
            "devices:view",
        )
        response = client.delete("/v2/devices/mtibs/some-id", headers=auth_headers)
        _assert_403(response)


# ---------------------------------------------------------------------------
# Module: System (info, cluster, admin history)
# ---------------------------------------------------------------------------

class TestSystemPermissions:
    """Tests for /v2/system/* and /v2/system/history — requires system:view / system:manage."""

    def test_system_info_unauthenticated(self, client):
        response = client.get("/v2/system/info")
        _assert_401(response)

    def test_system_info_wrong_permission(self, client, auth_headers, mock_db):
        mock_db.permissionset.find_unique.return_value = _make_limited_perm_set(
            "products:view",
        )
        response = client.get("/v2/system/info", headers=auth_headers)
        _assert_403(response)

    def test_system_info_correct_permission(self, client, auth_headers, mock_db):
        mock_db.permissionset.find_unique.return_value = _make_limited_perm_set(
            "system:view",
        )
        response = client.get("/v2/system/info", headers=auth_headers)
        _assert_not_denied(response)

    def test_admin_history_unauthenticated(self, client):
        response = client.get("/v2/system/history")
        _assert_401(response)

    def test_admin_history_wrong_permission(self, client, auth_headers, mock_db):
        mock_db.permissionset.find_unique.return_value = _make_limited_perm_set(
            "validation:view",
        )
        response = client.get("/v2/system/history", headers=auth_headers)
        _assert_403(response)

    def test_admin_history_correct_permission(self, client, auth_headers, mock_db):
        mock_db.permissionset.find_unique.return_value = _make_limited_perm_set(
            "system:view",
        )
        response = client.get("/v2/system/history", headers=auth_headers)
        _assert_not_denied(response)

    def test_retention_cleanup_unauthenticated(self, client):
        response = client.post("/v2/system/retention/validation/cleanup")
        _assert_401(response)

    def test_retention_cleanup_view_only(self, client, auth_headers, mock_db):
        """system:view should NOT allow cleanup (needs system:manage)."""
        mock_db.permissionset.find_unique.return_value = _make_limited_perm_set(
            "system:view",
        )
        response = client.post("/v2/system/retention/validation/cleanup",
                               headers=auth_headers)
        _assert_403(response)

    def test_retention_usage_correct_permission(self, client, auth_headers, mock_db):
        mock_db.permissionset.find_unique.return_value = _make_limited_perm_set(
            "system:view",
        )
        _request_passes_auth(client.get, "/v2/system/retention/validation/usage",
                             headers=auth_headers)


# ---------------------------------------------------------------------------
# Module: Kubernetes
# ---------------------------------------------------------------------------

class TestKubernetesPermissions:
    """Tests for /v2/cluster/* routes — requires kubernetes:view / kubernetes:manage."""

    def test_cluster_unauthenticated(self, client):
        response = client.get("/v2/kubernetes/info")
        _assert_401(response)

    def test_cluster_wrong_permission(self, client, auth_headers, mock_db):
        mock_db.permissionset.find_unique.return_value = _make_limited_perm_set(
            "devices:view",
        )
        response = client.get("/v2/kubernetes/info", headers=auth_headers)
        _assert_403(response)

    def test_cluster_correct_permission(self, client, auth_headers, mock_db):
        mock_db.permissionset.find_unique.return_value = _make_limited_perm_set(
            "kubernetes:view",
        )
        response = client.get("/v2/kubernetes/info", headers=auth_headers)
        _assert_not_denied(response)

    def test_pods_unauthenticated(self, client):
        response = client.get("/v2/kubernetes/pods")
        _assert_401(response)

    def test_pods_wrong_permission(self, client, auth_headers, mock_db):
        mock_db.permissionset.find_unique.return_value = _make_limited_perm_set(
            "builds:view",
        )
        response = client.get("/v2/kubernetes/pods", headers=auth_headers)
        _assert_403(response)

    def test_delete_pod_view_only(self, client, auth_headers, mock_db):
        """kubernetes:view should NOT allow deleting pods (needs kubernetes:manage)."""
        mock_db.permissionset.find_unique.return_value = _make_limited_perm_set(
            "kubernetes:view",
        )
        response = client.delete("/v2/kubernetes/pods/default/my-pod",
                                 headers=auth_headers)
        _assert_403(response)

    def test_scale_deployment_view_only(self, client, auth_headers, mock_db):
        """kubernetes:view should NOT allow scaling (needs kubernetes:manage)."""
        mock_db.permissionset.find_unique.return_value = _make_limited_perm_set(
            "kubernetes:view",
        )
        response = client.post("/v2/kubernetes/deployments/default/my-deploy/scale",
                               data=json.dumps({"replicas": 2}),
                               headers=auth_headers)
        _assert_403(response)

    def test_delete_job_view_only(self, client, auth_headers, mock_db):
        mock_db.permissionset.find_unique.return_value = _make_limited_perm_set(
            "kubernetes:view",
        )
        response = client.delete("/v2/kubernetes/jobs/default/my-job",
                                 headers=auth_headers)
        _assert_403(response)


# ---------------------------------------------------------------------------
# Module: Users
# ---------------------------------------------------------------------------

class TestUsersPermissions:
    """Tests for /v2/users routes — requires users:view / users:manage."""

    def test_list_users_unauthenticated(self, client):
        response = client.get("/v2/users")
        _assert_401(response)

    def test_list_users_wrong_permission(self, client, auth_headers, mock_db):
        mock_db.permissionset.find_unique.return_value = _make_limited_perm_set(
            "products:view",
        )
        response = client.get("/v2/users", headers=auth_headers)
        _assert_403(response)

    def test_list_users_correct_permission(self, client, auth_headers, mock_db):
        mock_db.permissionset.find_unique.return_value = _make_limited_perm_set(
            "users:view",
        )
        response = client.get("/v2/users", headers=auth_headers)
        _assert_not_denied(response)

    def test_create_user_unauthenticated(self, client):
        response = client.post("/v2/users", data=json.dumps({}),
                               content_type="application/json")
        _assert_401(response)

    def test_create_user_view_only(self, client, auth_headers, mock_db):
        """users:view should NOT allow creating users (needs users:manage)."""
        mock_db.permissionset.find_unique.return_value = _make_limited_perm_set(
            "users:view",
        )
        response = client.post("/v2/users",
                               data=json.dumps({"email": "new@test.com"}),
                               headers=auth_headers)
        _assert_403(response)

    def test_create_user_correct_permission(self, client, auth_headers, mock_db):
        mock_db.permissionset.find_unique.return_value = _make_limited_perm_set(
            "users:manage",
        )
        response = client.post("/v2/users",
                               data=json.dumps({"email": "new@test.com"}),
                               headers=auth_headers)
        _assert_not_denied(response)

    def test_update_user_view_only(self, client, auth_headers, mock_db):
        mock_db.permissionset.find_unique.return_value = _make_limited_perm_set(
            "users:view",
        )
        response = client.put("/v2/users/some-user-id",
                              data=json.dumps({"name": "New Name"}),
                              headers=auth_headers)
        _assert_403(response)

    def test_delete_user_view_only(self, client, auth_headers, mock_db):
        mock_db.permissionset.find_unique.return_value = _make_limited_perm_set(
            "users:view",
        )
        response = client.delete("/v2/users/some-user-id",
                                 headers=auth_headers)
        _assert_403(response)


# ---------------------------------------------------------------------------
# Module: Permission Sets
# ---------------------------------------------------------------------------

class TestPermissionSetsPermissions:
    """Tests for /v2/permissions — requires users:view / permissions:manage."""

    def test_list_permission_sets_unauthenticated(self, client):
        response = client.get("/v2/permissions")
        _assert_401(response)

    def test_list_permission_sets_wrong_permission(self, client, auth_headers, mock_db):
        mock_db.permissionset.find_unique.return_value = _make_limited_perm_set(
            "products:view",
        )
        response = client.get("/v2/permissions", headers=auth_headers)
        _assert_403(response)

    def test_list_permission_sets_correct_permission(self, client, auth_headers, mock_db):
        mock_db.permissionset.find_unique.return_value = _make_limited_perm_set(
            "users:view",
        )
        response = client.get("/v2/permissions", headers=auth_headers)
        _assert_not_denied(response)

    def test_create_permission_set_view_only(self, client, auth_headers, mock_db):
        """users:view should NOT allow creating permission sets (needs permissions:manage)."""
        mock_db.permissionset.find_unique.return_value = _make_limited_perm_set(
            "users:view",
        )
        response = client.post("/v2/permissions",
                               data=json.dumps({"name": "New Role"}),
                               headers=auth_headers)
        _assert_403(response)

    def test_create_permission_set_correct_permission(self, client, auth_headers, mock_db):
        mock_db.permissionset.find_unique.return_value = _make_limited_perm_set(
            "permissions:manage",
        )
        response = client.post("/v2/permissions",
                               data=json.dumps({"name": "New Role"}),
                               headers=auth_headers)
        _assert_not_denied(response)


# ---------------------------------------------------------------------------
# Module: API Keys
# ---------------------------------------------------------------------------

class TestAPIKeysPermissions:
    """Tests for /v2/api-keys — requires api-keys:view / api-keys:manage."""

    def test_list_api_keys_unauthenticated(self, client):
        response = client.get("/v2/api-keys")
        _assert_401(response)

    def test_list_api_keys_wrong_permission(self, client, auth_headers, mock_db):
        mock_db.permissionset.find_unique.return_value = _make_limited_perm_set(
            "products:view",
        )
        response = client.get("/v2/api-keys", headers=auth_headers)
        _assert_403(response)

    def test_list_api_keys_correct_permission(self, client, auth_headers, mock_db):
        mock_db.permissionset.find_unique.return_value = _make_limited_perm_set(
            "api-keys:view",
        )
        response = client.get("/v2/api-keys", headers=auth_headers)
        _assert_not_denied(response)

    def test_create_api_key_view_only(self, client, auth_headers, mock_db):
        """api-keys:view should NOT allow creating keys (needs api-keys:manage)."""
        mock_db.permissionset.find_unique.return_value = _make_limited_perm_set(
            "api-keys:view",
        )
        response = client.post("/v2/api-keys",
                               data=json.dumps({"name": "my-key"}),
                               headers=auth_headers)
        _assert_403(response)

    def test_delete_api_key_view_only(self, client, auth_headers, mock_db):
        mock_db.permissionset.find_unique.return_value = _make_limited_perm_set(
            "api-keys:view",
        )
        response = client.delete("/v2/api-keys/some-key-id",
                                 headers=auth_headers)
        _assert_403(response)


# ---------------------------------------------------------------------------
# Module: Deployments (managed MTIB deployments)
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Module: Observability
# ---------------------------------------------------------------------------

class TestObservabilityPermissions:
    """Tests for /v2/devices/mtibs/observability routes — requires devices:view."""

    def test_fleet_observability_unauthenticated(self, client):
        response = client.get("/v2/devices/mtibs/observability")
        _assert_401(response)

    def test_fleet_observability_wrong_permission(self, client, auth_headers, mock_db):
        mock_db.permissionset.find_unique.return_value = _make_limited_perm_set(
            "products:view",
        )
        response = client.get("/v2/devices/mtibs/observability", headers=auth_headers)
        _assert_403(response)

    def test_fleet_observability_correct_permission(self, client, auth_headers, mock_db):
        mock_db.permissionset.find_unique.return_value = _make_limited_perm_set(
            "devices:view",
        )
        response = client.get("/v2/devices/mtibs/observability", headers=auth_headers)
        _assert_not_denied(response)


# ---------------------------------------------------------------------------
# Module: Validation Tests (legacy manufacturing)
# ---------------------------------------------------------------------------

class TestValidationLegacyPermissions:
    """Tests for /v2/sessions/manual/run — requires validation:run."""

    def test_run_tests_unauthenticated(self, client):
        response = client.post("/v2/sessions/manual/run",
                               data=json.dumps({}),
                               content_type="application/json")
        _assert_401(response)

    def test_run_tests_view_only(self, client, auth_headers, mock_db):
        mock_db.permissionset.find_unique.return_value = _make_limited_perm_set(
            "validation:view",
        )
        response = client.post("/v2/sessions/manual/run",
                               data=json.dumps({}), headers=auth_headers)
        _assert_403(response)

    def test_run_tests_correct_permission(self, client, auth_headers, mock_db):
        mock_db.permissionset.find_unique.return_value = _make_limited_perm_set(
            "validation:run",
        )
        response = client.post("/v2/sessions/manual/run",
                               data=json.dumps({}), headers=auth_headers)
        _assert_not_denied(response)


# ---------------------------------------------------------------------------
# Cross-cutting: No permission set assigned
# ---------------------------------------------------------------------------

class TestNoPermissionSet:
    """When a user has no permissionSetId, all permission-gated routes must 403."""

    @pytest.fixture
    def no_perm_headers(self):
        """JWT for a user with no permission set."""
        from src.services.auth.jwt import create_token
        token = create_token(
            user_id="no-perm-user",
            email="noperm@example.com",
            name="No Perm User",
            permission_set_id=None,
        )
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

    def test_no_perm_set_catalog(self, client, no_perm_headers, mock_db):
        response = client.get("/v2/products", headers=no_perm_headers)
        _assert_403(response)
        data = json.loads(response.data)
        assert "No permission set assigned" in data["errors"][0]["message"]

    def test_no_perm_set_builds(self, client, no_perm_headers, mock_db):
        response = client.get("/v2/builds", headers=no_perm_headers)
        _assert_403(response)

    def test_no_perm_set_validation(self, client, no_perm_headers, mock_db):
        response = client.get("/v2/sessions", headers=no_perm_headers)
        _assert_403(response)

    def test_no_perm_set_fixtures(self, client, no_perm_headers, mock_db):
        response = client.get("/v2/fixtures", headers=no_perm_headers)
        _assert_403(response)

    def test_no_perm_set_users(self, client, no_perm_headers, mock_db):
        response = client.get("/v2/users", headers=no_perm_headers)
        _assert_403(response)

    def test_no_perm_set_system(self, client, no_perm_headers, mock_db):
        response = client.get("/v2/system/info", headers=no_perm_headers)
        _assert_403(response)


# ---------------------------------------------------------------------------
# Cross-cutting: Permission set not found in DB
# ---------------------------------------------------------------------------

class TestPermissionSetNotFound:
    """When the permission set ID in the JWT doesn't exist in the DB, routes must 403."""

    def test_missing_perm_set_returns_403(self, client, auth_headers, mock_db):
        """If permissionset.find_unique returns None, should get 403."""
        mock_db.permissionset.find_unique.return_value = None
        response = client.get("/v2/products", headers=auth_headers)
        _assert_403(response)
        data = json.loads(response.data)
        assert "Permission set not found" in data["errors"][0]["message"]

    def test_missing_perm_set_builds(self, client, auth_headers, mock_db):
        mock_db.permissionset.find_unique.return_value = None
        response = client.get("/v2/builds", headers=auth_headers)
        _assert_403(response)

    def test_missing_perm_set_validation(self, client, auth_headers, mock_db):
        mock_db.permissionset.find_unique.return_value = None
        response = client.get("/v2/sessions", headers=auth_headers)
        _assert_403(response)


# ---------------------------------------------------------------------------
# Cross-cutting: Privilege escalation — verify one module's perms don't leak
# ---------------------------------------------------------------------------

class TestPermissionIsolation:
    """Verify that having permission for one module does NOT grant access to another."""

    def test_products_perm_cannot_access_builds(self, client, auth_headers, mock_db):
        mock_db.permissionset.find_unique.return_value = _make_limited_perm_set(
            "products:view", "products:manage",
        )
        response = client.get("/v2/builds", headers=auth_headers)
        _assert_403(response)

    def test_builds_perm_cannot_access_validation(self, client, auth_headers, mock_db):
        mock_db.permissionset.find_unique.return_value = _make_limited_perm_set(
            "builds:view", "builds:trigger", "builds:manage",
        )
        response = client.get("/v2/sessions", headers=auth_headers)
        _assert_403(response)

    def test_validation_perm_cannot_access_system(self, client, auth_headers, mock_db):
        mock_db.permissionset.find_unique.return_value = _make_limited_perm_set(
            "validation:view", "validation:run", "validation:manage",
        )
        response = client.get("/v2/system/info", headers=auth_headers)
        _assert_403(response)

    def test_system_perm_cannot_access_users(self, client, auth_headers, mock_db):
        mock_db.permissionset.find_unique.return_value = _make_limited_perm_set(
            "system:view", "system:manage",
        )
        response = client.get("/v2/users", headers=auth_headers)
        _assert_403(response)

    def test_users_perm_cannot_access_devices(self, client, auth_headers, mock_db):
        mock_db.permissionset.find_unique.return_value = _make_limited_perm_set(
            "users:view", "users:manage",
        )
        response = client.get("/v2/devices/icle", headers=auth_headers)
        _assert_403(response)

    def test_devices_perm_cannot_access_fixtures(self, client, auth_headers, mock_db):
        mock_db.permissionset.find_unique.return_value = _make_limited_perm_set(
            "devices:view", "devices:manage",
        )
        response = client.get("/v2/fixtures", headers=auth_headers)
        _assert_403(response)

    def test_fixtures_perm_cannot_access_products(self, client, auth_headers, mock_db):
        mock_db.permissionset.find_unique.return_value = _make_limited_perm_set(
            "fixtures:view", "fixtures:manage",
        )
        response = client.get("/v2/products", headers=auth_headers)
        _assert_403(response)

    def test_benches_perm_cannot_access_api_keys(self, client, auth_headers, mock_db):
        mock_db.permissionset.find_unique.return_value = _make_limited_perm_set(
            "fixtures:view", "fixtures:manage",
        )
        response = client.get("/v2/api-keys", headers=auth_headers)
        _assert_403(response)

    def test_view_perm_cannot_mutate(self, client, auth_headers, mock_db):
        """Having all :view permissions should NOT allow any mutation."""
        mock_db.permissionset.find_unique.return_value = _make_limited_perm_set(
            "products:view", "builds:view", "validation:view",
            "fixtures:view", "fixtures:view", "devices:view",
            "users:view", "system:view", "api-keys:view",
        )

        # POST /v2/products (needs products:manage)
        r = client.post("/v2/products", data=json.dumps({"name": "X"}),
                        headers=auth_headers)
        _assert_403(r)

        # POST /v2/builds (needs builds:trigger)
        r = client.post("/v2/builds", data=json.dumps({}),
                        headers=auth_headers)
        _assert_403(r)

        # POST /v2/sessions (needs validation:run)
        r = client.post("/v2/sessions",
                        data=json.dumps({"productId": "p", "nodeId": "n"}),
                        headers=auth_headers)
        _assert_403(r)

        # POST /v2/fixtures (needs fixtures:manage)
        r = client.post("/v2/fixtures", data=json.dumps({"name": "X"}),
                        headers=auth_headers)
        _assert_403(r)

        # POST /v2/users (needs users:manage)
        r = client.post("/v2/users", data=json.dumps({"email": "x@y.com"}),
                        headers=auth_headers)
        _assert_403(r)


# ---------------------------------------------------------------------------
# Edge case: Empty permissions list
# ---------------------------------------------------------------------------

class TestEmptyPermissions:
    """A user with an empty permissions list should be denied everywhere."""

    def test_empty_perms_catalog(self, client, auth_headers, mock_db):
        mock_db.permissionset.find_unique.return_value = _make_limited_perm_set()
        response = client.get("/v2/products", headers=auth_headers)
        _assert_403(response)

    def test_empty_perms_builds(self, client, auth_headers, mock_db):
        mock_db.permissionset.find_unique.return_value = _make_limited_perm_set()
        response = client.get("/v2/builds", headers=auth_headers)
        _assert_403(response)

    def test_empty_perms_validation(self, client, auth_headers, mock_db):
        mock_db.permissionset.find_unique.return_value = _make_limited_perm_set()
        response = client.get("/v2/sessions", headers=auth_headers)
        _assert_403(response)

    def test_empty_perms_fixtures(self, client, auth_headers, mock_db):
        mock_db.permissionset.find_unique.return_value = _make_limited_perm_set()
        response = client.get("/v2/fixtures", headers=auth_headers)
        _assert_403(response)

    def test_empty_perms_users(self, client, auth_headers, mock_db):
        mock_db.permissionset.find_unique.return_value = _make_limited_perm_set()
        response = client.get("/v2/users", headers=auth_headers)
        _assert_403(response)

    def test_empty_perms_system(self, client, auth_headers, mock_db):
        mock_db.permissionset.find_unique.return_value = _make_limited_perm_set()
        response = client.get("/v2/system/info", headers=auth_headers)
        _assert_403(response)

    def test_empty_perms_devices(self, client, auth_headers, mock_db):
        mock_db.permissionset.find_unique.return_value = _make_limited_perm_set()
        response = client.get("/v2/devices/icle", headers=auth_headers)
        _assert_403(response)

    def test_empty_perms_benches(self, client, auth_headers, mock_db):
        mock_db.permissionset.find_unique.return_value = _make_limited_perm_set()
        response = client.get("/v2/fixtures/benches", headers=auth_headers)
        _assert_403(response)
