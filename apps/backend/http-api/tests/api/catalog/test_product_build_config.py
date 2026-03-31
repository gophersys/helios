"""Tests for Product.buildConfig JSON field — create, update, retrieve."""

import json
from datetime import datetime, timezone
from unittest.mock import patch

from tests.conftest import make_obj


ALPHA_BUILD_CONFIG = {
    "board": "alpha",
    "ncsVersion": "v2.9.0",
    "boardRoot": "ck_boards",
    "targets": {
        "app": {"soc": "nrf52840", "appId": 109, "role": "application"},
        "comms": {"soc": "nrf9151", "appId": 108, "role": "communications"},
    },
    "hasVsmMerge": True,
    "hasFips": False,
    "confFiles": {
        "app": ["prj.conf", "boards/alpha_b0_nrf52840.conf"],
        "comms": ["prj.conf", "boards/alpha_b0_nrf9151.conf"],
    },
    "overlays": {
        "app": ["boards/alpha_b0_nrf52840.overlay"],
        "comms": [],
    },
    "postBuild": ["sign_mcuboot", "generate_dfu_package"],
    "cfw": {"deviceType": 2, "deviceVariant": 3},
}


def _product_defaults() -> dict:
    return {
        "slug": None,
        "buildConfig": None,
    }


def test_create_product_with_build_config(authed_client, mock_db):
    """Creating a product with buildConfig stores and returns it."""
    mock_db.product.find_unique.return_value = None
    mock_db.product.create.return_value = make_obj(
        id="prod-alpha",
        name="Alpha B0",
        description="Alpha product",
        active=True,
        metadata={},
        buildConfig=ALPHA_BUILD_CONFIG,
        createdAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
        updatedAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
        boards=[],
        firmwareBuilds=[],
        **{k: v for k, v in _product_defaults().items() if k != "buildConfig"},
    )

    with patch("src.api.v2.products.products.log_audit"):
        response = authed_client.post(
            "/v2/products",
            data=json.dumps({
                "name": "Alpha B0",
                "buildConfig": ALPHA_BUILD_CONFIG,
            }),
        )

    assert response.status_code == 201
    body = json.loads(response.data)
    assert body["data"]["buildConfig"] == ALPHA_BUILD_CONFIG
    assert body["data"]["buildConfig"]["targets"]["app"]["appId"] == 109


def test_create_product_without_build_config(authed_client, mock_db):
    """Creating a product without buildConfig returns null for the field."""
    mock_db.product.find_unique.return_value = None
    mock_db.product.create.return_value = make_obj(
        id="prod-sigma",
        name="Sigma5",
        description=None,
        active=True,
        metadata={},
        createdAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
        updatedAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
        boards=[],
        firmwareBuilds=[],
        **_product_defaults(),
    )

    with patch("src.api.v2.products.products.log_audit"):
        response = authed_client.post(
            "/v2/products",
            data=json.dumps({
                "name": "Sigma5",
            }),
        )

    assert response.status_code == 201
    body = json.loads(response.data)
    assert body["data"]["buildConfig"] is None


def test_create_product_build_config_not_dict_rejected(authed_client, mock_db):
    """buildConfig must be a JSON object, not a string or array."""
    response = authed_client.post(
        "/v2/products",
        data=json.dumps({
            "name": "Bad",
            "buildConfig": "not-a-dict",
        }),
    )
    assert response.status_code == 400


def test_update_product_build_config(authed_client, mock_db):
    """Updating buildConfig replaces the entire JSON blob."""
    mock_db.product.find_unique.return_value = make_obj(
        id="prod-alpha",
        name="Alpha B0",
        slug=None,
    )

    updated_config = {**ALPHA_BUILD_CONFIG, "ncsVersion": "v2.10.0"}
    mock_db.product.update.return_value = make_obj(
        id="prod-alpha",
        name="Alpha B0",
        description=None,
        active=True,
        metadata={},
        buildConfig=updated_config,
        createdAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
        updatedAt=datetime(2025, 2, 1, tzinfo=timezone.utc),
        boards=[],
        firmwareBuilds=[],
        **{k: v for k, v in _product_defaults().items() if k != "buildConfig"},
    )

    with patch("src.api.v2.products.products.log_audit"):
        response = authed_client.put(
            "/v2/products/prod-alpha",
            data=json.dumps({"buildConfig": updated_config}),
        )

    assert response.status_code == 200
    body = json.loads(response.data)
    assert body["data"]["buildConfig"]["ncsVersion"] == "v2.10.0"


def test_update_product_build_config_to_null(authed_client, mock_db):
    """Setting buildConfig to null clears it."""
    mock_db.product.find_unique.return_value = make_obj(
        id="prod-alpha",
        name="Alpha B0",
        slug=None,
    )

    mock_db.product.update.return_value = make_obj(
        id="prod-alpha",
        name="Alpha B0",
        description=None,
        active=True,
        metadata={},
        buildConfig=None,
        createdAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
        updatedAt=datetime(2025, 2, 1, tzinfo=timezone.utc),
        boards=[],
        firmwareBuilds=[],
        **{k: v for k, v in _product_defaults().items() if k != "buildConfig"},
    )

    with patch("src.api.v2.products.products.log_audit"):
        response = authed_client.put(
            "/v2/products/prod-alpha",
            data=json.dumps({"buildConfig": None}),
        )

    assert response.status_code == 200
    body = json.loads(response.data)
    assert body["data"]["buildConfig"] is None


def test_get_product_includes_build_config(authed_client, mock_db):
    """GET /v2/products/<id> includes buildConfig in response."""
    mock_db.product.find_unique.return_value = make_obj(
        id="prod-alpha",
        name="Alpha B0",
        description="Alpha product",
        active=True,
        metadata={},
        buildConfig=ALPHA_BUILD_CONFIG,
        createdAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
        updatedAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
        boards=[],
        firmwareBuilds=[],
        **{k: v for k, v in _product_defaults().items() if k != "buildConfig"},
    )

    response = authed_client.get("/v2/products/prod-alpha")
    assert response.status_code == 200
    body = json.loads(response.data)
    assert body["data"]["buildConfig"] == ALPHA_BUILD_CONFIG
    assert body["data"]["buildConfig"]["cfw"]["deviceType"] == 2


def test_list_products_includes_build_config(authed_client, mock_db):
    """GET /v2/products includes buildConfig in each product."""
    mock_db.product.count.return_value = 1
    mock_db.product.find_many.return_value = [
        make_obj(
            id="prod-alpha",
            name="Alpha B0",
            description=None,
            active=True,
            metadata={},
            buildConfig=ALPHA_BUILD_CONFIG,
            createdAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
            updatedAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
            boards=[],
            firmwareBuilds=[],
            **{k: v for k, v in _product_defaults().items() if k != "buildConfig"},
        ),
    ]

    response = authed_client.get("/v2/products")
    assert response.status_code == 200
    body = json.loads(response.data)
    products = body["data"]["data"]
    assert len(products) == 1
    assert products[0]["buildConfig"] == ALPHA_BUILD_CONFIG
