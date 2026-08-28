"""
API contract tests for /v2/products/<id>/stages endpoints.

Shapes derived from _serialize_stage_config() in
src/api/v2/builds/stage_config.py.
"""

import json
from datetime import datetime, timezone

import pytest

from tests.conftest import make_obj
from tests.contracts.validate import assert_envelope, assert_response_shape

# ---------------------------------------------------------------------------
# Shape definitions
# ---------------------------------------------------------------------------

_BOARD_REVISION_INLINE_SHAPE = {
    "id": str,
    "version": str,
    "ckBoardsName": (str, type(None)),
}

_SIGNING_KEY_INLINE_SHAPE = {
    "id": str,
    "name": str,
    "type": str,
}

_STAGE_CONFIG_SHAPE = {
    "id": str,
    "productId": str,
    "type": str,
    "stage": int,
    "name": str,
    "enabled": bool,
    "boardRevisionId": (str, type(None)),
    "watchBranch": (str, type(None)),
    "triggerTypes": (str, type(None)),
    "signingKeyId": (str, type(None)),
    "createdAt": str,
    "updatedAt": str,
    "boardRevision": (dict, type(None)),
    "signingKey": (dict, type(None)),
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_stage_config(**kwargs):
    defaults = dict(
        id="stage-1",
        productId="prod-1",
        type="VALIDATION",
        stage=1,
        name="Smoke",
        enabled=True,
        boardRevisionId="rev-1",
        watchBranch="main",
        triggerTypes="pr",
        assetSources=["BUILD_SERVICE"],
        signingKeyId=None,
        createdAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
        updatedAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
        boardRevision=make_obj(
            id="rev-1",
            version="B0",
            ckBoardsName="alpha_b0",
        ),
        signingKey=None,
        buildMatrixEntries=[],
    )
    defaults.update(kwargs)
    return make_obj(**defaults)


def _make_product():
    return make_obj(id="prod-1", name="Alpha B0")


# ---------------------------------------------------------------------------
# Test: GET /v2/products/<id>/stages
# ---------------------------------------------------------------------------


@pytest.mark.contract
def test_list_stage_configs_response_shape(authed_client, mock_db):
    """GET /v2/products/<id>/stages returns a list of stage config objects."""
    mock_db.product.find_unique.return_value = _make_product()
    mock_db.productstageconfig.find_many.return_value = [
        _make_stage_config(stage=1, name="Smoke"),
        _make_stage_config(id="stage-2", stage=2, name="Driver", boardRevision=None),
    ]

    resp = authed_client.get("/v2/products/prod-1/stages")

    assert resp.status_code == 200
    data = assert_envelope(json.loads(resp.data))

    assert isinstance(data, list), "Response must be a list of stage configs"
    assert len(data) == 2

    assert_response_shape(data[0], _STAGE_CONFIG_SHAPE)

    # boardRevision can be None when no revision is assigned
    if data[1]["boardRevision"] is not None:
        assert_response_shape(data[1]["boardRevision"], _BOARD_REVISION_INLINE_SHAPE)

    # TODO: test_list_stage_configs_product_not_found_returns_404
    # TODO: test_list_stage_configs_empty_product_returns_empty_list


# ---------------------------------------------------------------------------
# Test: GET /v2/products/<id>/stages/<stage>
# ---------------------------------------------------------------------------


@pytest.mark.contract
def test_get_stage_config_response_shape(authed_client, mock_db):
    """GET /v2/products/<id>/stages/<n> returns a single stage config object."""
    mock_db.product.find_unique.return_value = _make_product()
    mock_db.productstageconfig.find_first.return_value = _make_stage_config()

    resp = authed_client.get("/v2/products/prod-1/stages/1")

    assert resp.status_code == 200
    data = assert_envelope(json.loads(resp.data))
    assert_response_shape(data, _STAGE_CONFIG_SHAPE)

    # boardRevision is present and has correct shape when assigned
    assert data["boardRevision"] is not None
    assert_response_shape(data["boardRevision"], _BOARD_REVISION_INLINE_SHAPE)

    # TODO: test_get_stage_config_not_found_returns_404
    # TODO: test_get_stage_config_invalid_stage_number_returns_400
    # TODO: test_get_stage_config_with_signing_key_shape
