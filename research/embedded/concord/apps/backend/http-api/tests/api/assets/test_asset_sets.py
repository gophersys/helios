"""Integration tests for the Asset Sets API."""

import json
from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from tests.conftest import make_obj


# ── Helpers ──────────────────────────────────────────────────


def _asset_set_defaults(**overrides) -> dict:
    """Common asset set fields for test mocks."""
    defaults = {
        "productId": "prod-1",
        "boardRevisionId": None,
        "version": "0.5.0",
        "variant": "debug",
        "stage": 1,
        "source": "MANUAL_UPLOAD",
        "buildRunId": None,
        "externalBuildId": None,
        "commitSha": None,
        "branch": None,
        "recipeVersionId": None,
        "status": "PENDING",
        "notes": None,
        "createdById": None,
        "createdAt": datetime(2025, 3, 1, tzinfo=timezone.utc),
        "updatedAt": datetime(2025, 3, 1, tzinfo=timezone.utc),
        "product": make_obj(id="prod-1", name="Alpha", slug="alpha"),
        "boardRevision": None,
        "createdBy": None,
        "assets": [],
    }
    defaults.update(overrides)
    return defaults


def _make_asset_set(id="as-1", **overrides):
    return make_obj(id=id, **_asset_set_defaults(**overrides))


# ── List ─────────────────────────────────────────────────────


def test_list_asset_sets(authed_client, mock_db):
    """GET /v2/products/<id>/asset-sets returns paginated list."""
    mock_db.product.find_unique.return_value = make_obj(id="prod-1", name="Alpha")
    mock_db.assetset.count.return_value = 1
    mock_db.assetset.find_many.return_value = [_make_asset_set()]

    response = authed_client.get("/v2/products/prod-1/asset-sets")
    assert response.status_code == 200
    data = json.loads(response.data)
    assert isinstance(data["data"], list)
    assert len(data["data"]) == 1


def test_list_asset_sets_product_not_found(authed_client, mock_db):
    """GET /v2/products/<id>/asset-sets returns 404 when product missing."""
    mock_db.product.find_unique.return_value = None

    response = authed_client.get("/v2/products/missing/asset-sets")
    assert response.status_code == 404


# ── Create ───────────────────────────────────────────────────


def test_create_asset_set(authed_client, mock_db):
    """POST /v2/products/<id>/asset-sets creates a new asset set."""
    mock_db.product.find_unique.return_value = make_obj(id="prod-1", name="Alpha")

    created = _make_asset_set(id="as-new", version="1.0.0")
    mock_db.assetset.create.return_value = created

    with patch("src.api.v2.assets.asset_sets.log_audit"):
        response = authed_client.post(
            "/v2/products/prod-1/asset-sets",
            data=json.dumps({"version": "1.0.0", "source": "MANUAL_UPLOAD"}),
        )

    assert response.status_code == 201
    data = json.loads(response.data)
    assert data["data"]["id"] == "as-new"
    assert data["data"]["version"] == "1.0.0"


def test_create_asset_set_product_not_found(authed_client, mock_db):
    """POST /v2/products/<id>/asset-sets returns 404 when product missing."""
    mock_db.product.find_unique.return_value = None

    response = authed_client.post(
        "/v2/products/missing/asset-sets",
        data=json.dumps({"version": "1.0.0"}),
    )
    assert response.status_code == 404


def test_create_asset_set_missing_version(authed_client, mock_db):
    """POST /v2/products/<id>/asset-sets returns 400 without version."""
    mock_db.product.find_unique.return_value = make_obj(id="prod-1", name="Alpha")

    response = authed_client.post(
        "/v2/products/prod-1/asset-sets",
        data=json.dumps({}),
    )
    assert response.status_code == 400
    data = json.loads(response.data)
    assert len(data["errors"]) > 0


# ── Get ──────────────────────────────────────────────────────


def test_get_asset_set(authed_client, mock_db):
    """GET /v2/asset-sets/<id> returns a single asset set with assets."""
    asset_set = _make_asset_set(
        id="as-123",
        assets=[
            make_obj(
                id="asset-1",
                assetSetId="as-123",
                label="app_hex",
                role="APP",
                processor="nrf52840",
                artifactType="HEX",
                storageKey="fw/app.hex",
                filename="app.hex",
                sizeBytes=1024,
                checksum="abc123",
                contentType="application/octet-stream",
                createdAt=datetime(2025, 3, 1, tzinfo=timezone.utc),
            ),
        ],
    )
    mock_db.assetset.find_unique.return_value = asset_set

    response = authed_client.get("/v2/asset-sets/as-123")
    assert response.status_code == 200

    data = json.loads(response.data)
    assert data["data"]["id"] == "as-123"
    assert len(data["data"]["assets"]) == 1
    assert data["data"]["assets"][0]["filename"] == "app.hex"


def test_get_asset_set_not_found(authed_client, mock_db):
    """GET /v2/asset-sets/<id> returns 404 when not found."""
    mock_db.assetset.find_unique.return_value = None

    response = authed_client.get("/v2/asset-sets/nonexistent")
    assert response.status_code == 404


# ── Complete ─────────────────────────────────────────────────


def test_complete_asset_set(authed_client, mock_db):
    """POST /v2/asset-sets/<id>/complete marks PENDING asset set as COMPLETE."""
    mock_db.assetset.find_unique.return_value = _make_asset_set(
        id="as-complete", status="PENDING",
    )
    mock_db.assetset.update.return_value = _make_asset_set(
        id="as-complete", status="COMPLETE",
    )

    with patch("src.api.v2.assets.asset_sets.log_audit"):
        response = authed_client.post("/v2/asset-sets/as-complete/complete")

    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["data"]["status"] == "COMPLETE"


def test_complete_asset_set_not_found(authed_client, mock_db):
    """POST /v2/asset-sets/<id>/complete returns 404 when not found."""
    mock_db.assetset.find_unique.return_value = None

    response = authed_client.post("/v2/asset-sets/missing/complete")
    assert response.status_code == 404


def test_complete_asset_set_already_complete(authed_client, mock_db):
    """POST /v2/asset-sets/<id>/complete returns 400 if not PENDING."""
    mock_db.assetset.find_unique.return_value = _make_asset_set(
        id="as-done", status="COMPLETE",
    )

    response = authed_client.post("/v2/asset-sets/as-done/complete")
    assert response.status_code == 400
    data = json.loads(response.data)
    assert len(data["errors"]) > 0


# ── Delete ───────────────────────────────────────────────────


def test_delete_asset_set(authed_client, mock_db):
    """DELETE /v2/asset-sets/<id> deletes asset set with no linked runs."""
    mock_db.assetset.find_unique.return_value = _make_asset_set(id="as-del")
    mock_db.testrun.count.return_value = 0

    with patch("src.api.v2.assets.asset_sets.log_audit"):
        response = authed_client.delete("/v2/asset-sets/as-del")

    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["data"]["deleted"] is True
    mock_db.assetset.delete.assert_called_once_with(where={"id": "as-del"})


def test_delete_asset_set_not_found(authed_client, mock_db):
    """DELETE /v2/asset-sets/<id> returns 404 when not found."""
    mock_db.assetset.find_unique.return_value = None

    response = authed_client.delete("/v2/asset-sets/missing")
    assert response.status_code == 404


def test_delete_asset_set_has_runs(authed_client, mock_db):
    """DELETE /v2/asset-sets/<id> returns 400 when test runs reference it."""
    mock_db.assetset.find_unique.return_value = _make_asset_set(id="as-linked")
    mock_db.testrun.count.return_value = 3

    response = authed_client.delete("/v2/asset-sets/as-linked")
    assert response.status_code == 400
    data = json.loads(response.data)
    assert len(data["errors"]) > 0
