"""Extended integration tests for Products API — archive, unarchive, export, slug, batch, delete guards."""

import json
from datetime import datetime, timezone
from unittest.mock import patch

from tests.conftest import make_obj


def _product_defaults() -> dict:
    return {"slug": None, "buildConfig": None}


def _active_product(pid="prod-1", name="Product Alpha"):
    return make_obj(
        id=pid,
        name=name,
        status="ACTIVE",
        description="desc",
        metadata={},
        createdAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
        updatedAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
        boards=[],
        firmwareSets=[],
        **_product_defaults(),
    )


def _archived_product(pid="prod-1", name="Product Alpha"):
    return make_obj(
        id=pid,
        name=name,
        status="ARCHIVED",
        description="desc",
        metadata={},
        createdAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
        updatedAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
        boards=[],
        firmwareSets=[],
        **_product_defaults(),
    )


def _err_msg(data: dict) -> str:
    return data["errors"][0]["message"]


# ── archive_product ──────────────────────────────────────────


def test_archive_product_success(authed_client, mock_db):
    mock_db.product.find_unique.return_value = _active_product()
    mock_db.productstageconfig.count.return_value = 0
    mock_db.buildrun.count.return_value = 0
    mock_db.testrun.count.return_value = 0
    mock_db.manufacturingsession.count.return_value = 0
    mock_db.product.update.return_value = _archived_product()

    with patch("src.api.v2.products.products.log_audit"):
        response = authed_client.post("/v2/products/prod-1/archive")

    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["data"]["status"] == "ARCHIVED"


def test_archive_product_already_archived(authed_client, mock_db):
    mock_db.product.find_unique.return_value = _archived_product()

    response = authed_client.post("/v2/products/prod-1/archive")

    assert response.status_code == 400
    data = json.loads(response.data)
    assert len(data["errors"]) > 0
    assert "already archived" in _err_msg(data).lower()


def test_archive_product_enabled_stages_block(authed_client, mock_db):
    mock_db.product.find_unique.return_value = _active_product()
    mock_db.productstageconfig.count.return_value = 2

    response = authed_client.post("/v2/products/prod-1/archive")

    assert response.status_code == 409
    data = json.loads(response.data)
    assert "2 stage(s)" in _err_msg(data)


def test_archive_product_active_builds_block(authed_client, mock_db):
    mock_db.product.find_unique.return_value = _active_product()
    mock_db.productstageconfig.count.return_value = 0
    mock_db.buildrun.count.return_value = 3

    response = authed_client.post("/v2/products/prod-1/archive")

    assert response.status_code == 409
    data = json.loads(response.data)
    assert "3 build run(s)" in _err_msg(data)


def test_archive_product_active_tests_block(authed_client, mock_db):
    mock_db.product.find_unique.return_value = _active_product()
    mock_db.productstageconfig.count.return_value = 0
    mock_db.buildrun.count.return_value = 0
    mock_db.testrun.count.return_value = 5

    response = authed_client.post("/v2/products/prod-1/archive")

    assert response.status_code == 409
    data = json.loads(response.data)
    assert "5 test run(s)" in _err_msg(data)


def test_archive_product_active_mfg_sessions_block(authed_client, mock_db):
    mock_db.product.find_unique.return_value = _active_product()
    mock_db.productstageconfig.count.return_value = 0
    mock_db.buildrun.count.return_value = 0
    mock_db.testrun.count.return_value = 0
    mock_db.manufacturingsession.count.return_value = 1

    response = authed_client.post("/v2/products/prod-1/archive")

    assert response.status_code == 409
    data = json.loads(response.data)
    assert "1 manufacturing session(s)" in _err_msg(data)


def test_archive_product_not_found(authed_client, mock_db):
    mock_db.product.find_unique.return_value = None

    response = authed_client.post("/v2/products/nonexistent/archive")

    assert response.status_code == 404


# ── unarchive_product ────────────────────────────────────────


def test_unarchive_product_success(authed_client, mock_db):
    mock_db.product.find_unique.return_value = _archived_product()
    mock_db.product.update.return_value = _active_product()

    with patch("src.api.v2.products.products.log_audit"):
        response = authed_client.post("/v2/products/prod-1/unarchive")

    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["data"]["status"] == "ACTIVE"


def test_unarchive_product_not_archived(authed_client, mock_db):
    mock_db.product.find_unique.return_value = _active_product()

    response = authed_client.post("/v2/products/prod-1/unarchive")

    assert response.status_code == 400
    data = json.loads(response.data)
    assert "not archived" in _err_msg(data).lower()


def test_unarchive_product_not_found(authed_client, mock_db):
    mock_db.product.find_unique.return_value = None

    response = authed_client.post("/v2/products/nonexistent/unarchive")

    assert response.status_code == 404


# ── export_product ───────────────────────────────────────────


def test_export_product_returns_501(authed_client, mock_db):
    mock_db.product.find_unique.return_value = _active_product()

    response = authed_client.post("/v2/products/prod-1/export")

    assert response.status_code == 501
    data = json.loads(response.data)
    assert "not yet implemented" in data["data"]["message"].lower()


def test_export_product_not_found(authed_client, mock_db):
    mock_db.product.find_unique.return_value = None

    response = authed_client.post("/v2/products/nonexistent/export")

    assert response.status_code == 404


# ── get_product_by_slug ──────────────────────────────────────


def test_get_product_by_slug_success(authed_client, mock_db):
    mock_db.product.find_first.return_value = make_obj(
        id="prod-slug",
        name="Slugged Product",
        slug="slugged-product",
        status="ACTIVE",
        description="desc",
        metadata={},
        buildConfig=None,
        createdAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
        updatedAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
        boards=[],
        firmwareSets=[],
    )

    response = authed_client.get("/v2/products/by-slug/slugged-product")

    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["data"]["slug"] == "slugged-product"
    assert data["data"]["id"] == "prod-slug"


def test_get_product_by_slug_not_found(authed_client, mock_db):
    mock_db.product.find_first.return_value = None

    response = authed_client.get("/v2/products/by-slug/no-such-slug")

    assert response.status_code == 404
    data = json.loads(response.data)
    assert "no-such-slug" in _err_msg(data)


# ── batch_products_action ────────────────────────────────────


def test_batch_archive_success(authed_client, mock_db):
    mock_db.product.find_unique.side_effect = [
        _active_product("p1", "Alpha"),
        _active_product("p2", "Beta"),
    ]
    mock_db.buildrun.count.return_value = 0
    mock_db.testrun.count.return_value = 0

    with patch("src.api.v2.products.products.log_audit"):
        response = authed_client.post(
            "/v2/products/batch",
            data=json.dumps({"action": "archive", "ids": ["p1", "p2"]}),
        )

    assert response.status_code == 200
    data = json.loads(response.data)
    assert set(data["data"]["succeeded"]) == {"p1", "p2"}
    assert data["data"]["failed"] == []


def test_batch_archive_skips_already_archived(authed_client, mock_db):
    mock_db.product.find_unique.return_value = _archived_product("p1")

    with patch("src.api.v2.products.products.log_audit"):
        response = authed_client.post(
            "/v2/products/batch",
            data=json.dumps({"action": "archive", "ids": ["p1"]}),
        )

    assert response.status_code == 200
    data = json.loads(response.data)
    assert "p1" in data["data"]["succeeded"]
    mock_db.product.update.assert_not_called()


def test_batch_delete_success(authed_client, mock_db):
    mock_db.product.find_unique.return_value = _archived_product("p1")

    with patch("src.api.v2.products.products.log_audit"):
        response = authed_client.post(
            "/v2/products/batch",
            data=json.dumps({"action": "delete", "ids": ["p1"]}),
        )

    assert response.status_code == 200
    data = json.loads(response.data)
    assert "p1" in data["data"]["succeeded"]
    mock_db.product.delete.assert_called_once()


def test_batch_invalid_action(authed_client, mock_db):
    response = authed_client.post(
        "/v2/products/batch",
        data=json.dumps({"action": "explode", "ids": ["p1"]}),
    )

    assert response.status_code == 400
    data = json.loads(response.data)
    assert len(data["errors"]) > 0


def test_batch_empty_ids(authed_client, mock_db):
    response = authed_client.post(
        "/v2/products/batch",
        data=json.dumps({"action": "archive", "ids": []}),
    )

    assert response.status_code == 400


def test_batch_not_found_in_list(authed_client, mock_db):
    mock_db.product.find_unique.return_value = None

    with patch("src.api.v2.products.products.log_audit"):
        response = authed_client.post(
            "/v2/products/batch",
            data=json.dumps({"action": "archive", "ids": ["ghost-id"]}),
        )

    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["data"]["succeeded"] == []
    assert len(data["data"]["failed"]) == 1
    assert data["data"]["failed"][0]["id"] == "ghost-id"
    assert "Not found" in data["data"]["failed"][0]["reason"]


def test_batch_delete_non_archived_fails(authed_client, mock_db):
    mock_db.product.find_unique.return_value = _active_product("p1")

    with patch("src.api.v2.products.products.log_audit"):
        response = authed_client.post(
            "/v2/products/batch",
            data=json.dumps({"action": "delete", "ids": ["p1"]}),
        )

    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["data"]["succeeded"] == []
    assert len(data["data"]["failed"]) == 1
    assert "archived" in data["data"]["failed"][0]["reason"].lower()


def test_batch_archive_with_active_builds_fails(authed_client, mock_db):
    mock_db.product.find_unique.return_value = _active_product("p1")
    mock_db.buildrun.count.return_value = 2

    with patch("src.api.v2.products.products.log_audit"):
        response = authed_client.post(
            "/v2/products/batch",
            data=json.dumps({"action": "archive", "ids": ["p1"]}),
        )

    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["data"]["succeeded"] == []
    assert len(data["data"]["failed"]) == 1
    assert "active build" in data["data"]["failed"][0]["reason"].lower()


def test_batch_archive_with_active_tests_fails(authed_client, mock_db):
    mock_db.product.find_unique.return_value = _active_product("p1")
    mock_db.buildrun.count.return_value = 0
    mock_db.testrun.count.return_value = 4

    with patch("src.api.v2.products.products.log_audit"):
        response = authed_client.post(
            "/v2/products/batch",
            data=json.dumps({"action": "archive", "ids": ["p1"]}),
        )

    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["data"]["succeeded"] == []
    assert len(data["data"]["failed"]) == 1
    assert "active test" in data["data"]["failed"][0]["reason"].lower()


# ── delete_product — expanded guards ─────────────────────────


def test_delete_product_not_archived_returns_400(authed_client, mock_db):
    mock_db.product.find_unique.return_value = _active_product()

    response = authed_client.delete("/v2/products/prod-1")

    assert response.status_code == 400
    data = json.loads(response.data)
    assert "archived" in _err_msg(data).lower()


def test_delete_product_not_found(authed_client, mock_db):
    mock_db.product.find_unique.return_value = None

    response = authed_client.delete("/v2/products/nonexistent")

    assert response.status_code == 404


def test_delete_product_build_runs_block(authed_client, mock_db):
    mock_db.product.find_unique.return_value = _archived_product()
    mock_db.buildrun.count.return_value = 3

    response = authed_client.delete("/v2/products/prod-1")

    assert response.status_code == 409
    data = json.loads(response.data)
    assert "3 build run(s)" in _err_msg(data)


def test_delete_product_asset_sets_block(authed_client, mock_db):
    mock_db.product.find_unique.return_value = _archived_product()
    mock_db.buildrun.count.return_value = 0
    mock_db.assetset.count.return_value = 5

    response = authed_client.delete("/v2/products/prod-1")

    assert response.status_code == 409
    data = json.loads(response.data)
    assert "5 asset set(s)" in _err_msg(data)


def test_delete_product_fixtures_block(authed_client, mock_db):
    mock_db.product.find_unique.return_value = _archived_product()
    mock_db.buildrun.count.return_value = 0
    mock_db.assetset.count.return_value = 0
    mock_db.fixture.count.return_value = 2

    response = authed_client.delete("/v2/products/prod-1")

    assert response.status_code == 409
    data = json.loads(response.data)
    assert "2 fixture(s)" in _err_msg(data)


def test_delete_product_test_runs_block(authed_client, mock_db):
    mock_db.product.find_unique.return_value = _archived_product()
    mock_db.buildrun.count.return_value = 0
    mock_db.assetset.count.return_value = 0
    mock_db.fixture.count.return_value = 0
    mock_db.testrun.find_first.return_value = make_obj(id="run-1", productId="prod-1")

    response = authed_client.delete("/v2/products/prod-1")

    assert response.status_code == 409
    data = json.loads(response.data)
    assert "test runs" in _err_msg(data).lower()


def test_delete_product_active_mfg_sessions_block(authed_client, mock_db):
    mock_db.product.find_unique.return_value = _archived_product()
    mock_db.buildrun.count.return_value = 0
    mock_db.assetset.count.return_value = 0
    mock_db.fixture.count.return_value = 0
    mock_db.testrun.find_first.return_value = None
    mock_db.manufacturingsession.find_first.return_value = make_obj(
        id="sess-1", productId="prod-1", status="ACTIVE"
    )

    response = authed_client.delete("/v2/products/prod-1")

    assert response.status_code == 409
    data = json.loads(response.data)
    assert "manufacturing sessions" in _err_msg(data).lower()


def test_delete_product_all_guards_pass(authed_client, mock_db):
    mock_db.product.find_unique.return_value = _archived_product()
    mock_db.buildrun.count.return_value = 0
    mock_db.assetset.count.return_value = 0
    mock_db.fixture.count.return_value = 0
    mock_db.testrun.find_first.return_value = None
    mock_db.manufacturingsession.find_first.return_value = None

    with patch("src.api.v2.products.products.log_audit"):
        response = authed_client.delete("/v2/products/prod-1")

    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["data"]["deleted"] is True
    mock_db.product.delete.assert_called_once_with(where={"id": "prod-1"})
