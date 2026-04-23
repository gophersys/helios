"""
API contract tests for /v2/products endpoints.

These tests assert that the serialized response shapes match the documented
contract. They do NOT assert exact field values — only that required fields
are present and have the correct types.

Shapes are derived from _serialize_product() in
src/api/v2/products/products.py.
"""

import json
from datetime import datetime, timezone

import pytest

from tests.conftest import make_obj
from tests.contracts.validate import assert_envelope, assert_response_shape

# ---------------------------------------------------------------------------
# Shape definitions — mirrors the serializer output exactly
# ---------------------------------------------------------------------------

_PRODUCT_SHAPE = {
    "id": str,
    "name": str,
    "slug": (str, type(None)),
    "description": (str, type(None)),
    "status": str,
    "fwRepoSlug": (str, type(None)),
    "mfgFwRepoSlug": (str, type(None)),
    "builderImage": (str, type(None)),
    "repoSshUrl": (str, type(None)),
    "mfgRepoSshUrl": (str, type(None)),
    "buildConfig": (dict, type(None)),
    "metadata": (dict, type(None)),
    "createdAt": str,
    "updatedAt": str,
    "targets": list,
}

_PAGINATION_SHAPE = {
    "page": int,
    "limit": int,
    "total": int,
    "pages": int,
}

_BOARD_SUMMARY_SHAPE = {
    "id": str,
    "productId": str,
    "name": str,
    "ckBoardsFamily": (str, type(None)),
    "vendor": (str, type(None)),
    "description": (str, type(None)),
    "active": bool,
    "createdAt": str,
    "updatedAt": str,
}

_BOARD_REVISION_SHAPE = {
    "id": str,
    "boardId": str,
    "version": str,
    "ckBoardsName": (str, type(None)),
    "socs": list,
    "deviceType": (int, type(None)),
    "deviceVariant": (int, type(None)),
    "status": str,
    "notes": (str, type(None)),
    "createdAt": str,
    "updatedAt": str,
    "targets": list,
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_product(**kwargs):
    defaults = dict(
        id="prod-1",
        name="Alpha B0",
        slug="alpha_b0",
        description="Alpha board revision B0",
        status="ACTIVE",
        fwRepoSlug="alpha_fw",
        mfgFwRepoSlug="alpha_mfg_fw",
        builderImage=None,
        buildConfig=None,
        metadata=None,
        createdAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
        updatedAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
        boards=[],
        firmwareSets=[],
    )
    defaults.update(kwargs)
    return make_obj(**defaults)


# ---------------------------------------------------------------------------
# Test: GET /v2/products
# ---------------------------------------------------------------------------


@pytest.mark.contract
def test_list_products_response_shape(authed_client, mock_db):
    """GET /v2/products returns a paginated envelope with product objects."""
    mock_db.product.count.return_value = 1
    mock_db.product.find_many.return_value = [_make_product()]
    mock_db.productaccess.find_many.return_value = []

    resp = authed_client.get("/v2/products")

    assert resp.status_code == 200
    body = assert_envelope(json.loads(resp.data))

    # Outer pagination wrapper
    assert "data" in body, "Response body must have 'data' list"
    assert "pagination" in body, "Response body must have 'pagination'"

    assert_response_shape(body["pagination"], _PAGINATION_SHAPE)
    assert isinstance(body["data"], list)

    if body["data"]:
        assert_response_shape(body["data"][0], _PRODUCT_SHAPE)

    # TODO: test_list_products_filters_by_status
    # TODO: test_list_products_pagination_second_page
    # TODO: test_list_products_developer_role_filters_by_access
    # TODO: test_list_products_empty_returns_zero_total


# ---------------------------------------------------------------------------
# Test: GET /v2/products/<id>
# ---------------------------------------------------------------------------


@pytest.mark.contract
def test_get_product_response_shape(authed_client, mock_db):
    """GET /v2/products/<id> returns a product with boards and revisions."""
    board_rev = make_obj(
        id="rev-1",
        boardId="board-1",
        version="B0",
        ckBoardsName="alpha_b0",
        socs=["nrf52840", "nrf9151"],
        deviceType=2,
        deviceVariant=3,
        status="ACTIVE",
        notes=None,
        createdAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
        updatedAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
        targets=[],
    )
    board = make_obj(
        id="board-1",
        productId="prod-1",
        name="Main Board",
        ckBoardsFamily="alpha",
        vendor="corekinect",
        description=None,
        active=True,
        createdAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
        updatedAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
        revisions=[board_rev],
    )
    product = _make_product(boards=[board])
    mock_db.product.find_unique.return_value = product

    resp = authed_client.get("/v2/products/prod-1")

    assert resp.status_code == 200
    data = assert_envelope(json.loads(resp.data))
    assert_response_shape(data, _PRODUCT_SHAPE)

    # boards are included in detail view (include_children=True)
    assert "boards" in data, "Detail view must include boards"
    assert isinstance(data["boards"], list)
    if data["boards"]:
        assert_response_shape(data["boards"][0], _BOARD_SUMMARY_SHAPE)
        if data["boards"][0].get("revisions"):
            assert_response_shape(data["boards"][0]["revisions"][0], _BOARD_REVISION_SHAPE)

    # TODO: test_get_product_includes_stage_configs
    # TODO: test_get_product_includes_firmware_sets
    # TODO: test_get_product_not_found_returns_404


# ---------------------------------------------------------------------------
# Test: POST /v2/products
# ---------------------------------------------------------------------------


@pytest.mark.contract
def test_create_product_response_shape(authed_client, mock_db):
    """POST /v2/products returns 201 with the created product shape."""
    mock_db.product.find_unique.return_value = None  # no duplicate
    mock_db.product.create.return_value = _make_product()

    resp = authed_client.post(
        "/v2/products",
        data=json.dumps({"name": "Alpha B0"}),
    )

    assert resp.status_code == 201
    data = assert_envelope(json.loads(resp.data))
    assert_response_shape(data, _PRODUCT_SHAPE)

    # TODO: test_create_product_conflict_on_duplicate_name_returns_409
    # TODO: test_create_product_missing_name_returns_400
    # TODO: test_create_product_with_board_inline_creates_board
