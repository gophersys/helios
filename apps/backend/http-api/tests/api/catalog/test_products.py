"""Integration tests for the Products API."""

import json
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

from tests.conftest import make_obj


def _product_defaults() -> dict:
    """Common product fields for test mocks."""
    return {
        "slug": None,
        "buildConfig": None,
    }


def test_list_products(authed_client, mock_db):
    """Test listing products with pagination."""
    mock_db.product.count.return_value = 2
    mock_db.product.find_many.return_value = [
        make_obj(
            id="prod-1",
            name="Product Alpha",
            description="First product",
            active=True,
            metadata={},
            createdAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
            updatedAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
            boards=[],
            firmwareSets=[],
            **_product_defaults(),
        ),
        make_obj(
            id="prod-2",
            name="Product Beta",
            description="Second product",
            active=False,
            metadata={"key": "value"},
            createdAt=datetime(2025, 1, 2, tzinfo=timezone.utc),
            updatedAt=datetime(2025, 1, 2, tzinfo=timezone.utc),
            boards=[],
            firmwareSets=[],
            **_product_defaults(),
        ),
    ]

    response = authed_client.get("/v2/products")
    assert response.status_code == 200

    data = json.loads(response.data)
    assert "data" in data
    assert "errors" in data
    assert len(data["errors"]) == 0

    # Check nested structure
    assert "data" in data["data"]
    assert "pagination" in data["data"]
    assert len(data["data"]["data"]) == 2
    assert data["data"]["pagination"]["total"] == 2
    assert data["data"]["pagination"]["page"] == 1


def test_list_products_unauthorized(client):
    """Test listing products without auth returns 401."""
    response = client.get("/v2/products")
    assert response.status_code == 401


def test_create_product(authed_client, mock_db):
    """Test creating a new product."""
    mock_db.product.find_unique.return_value = None

    mock_db.product.create.return_value = make_obj(
        id="prod-new",
        name="New Product",
        description="A new product",
        active=True,
        metadata={},
        createdAt=datetime(2025, 1, 15, tzinfo=timezone.utc),
        updatedAt=datetime(2025, 1, 15, tzinfo=timezone.utc),
        boards=[],
        firmwareSets=[],
        **_product_defaults(),
    )

    with patch("src.api.v2.products.products.log_audit"):
        response = authed_client.post(
            "/v2/products",
            data=json.dumps({
                "name": "New Product",
                "description": "A new product",
                "active": True,
            }),
        )

    assert response.status_code == 201
    data = json.loads(response.data)
    assert data["data"]["name"] == "New Product"
    assert data["data"]["id"] == "prod-new"


def test_create_product_duplicate_name(authed_client, mock_db):
    """Test creating a product with duplicate name returns 409."""
    mock_db.product.find_unique.return_value = make_obj(
        id="existing-prod",
        name="Existing Product",
        description="",
        active=True,
        metadata={},
        createdAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
        updatedAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
        **_product_defaults(),
    )

    response = authed_client.post(
        "/v2/products",
        data=json.dumps({
            "name": "Existing Product",
        }),
    )

    assert response.status_code == 409
    data = json.loads(response.data)
    assert len(data["errors"]) > 0


def test_create_product_missing_name(authed_client, mock_db):
    """Test creating product with missing name returns 400."""
    response = authed_client.post(
        "/v2/products",
        data=json.dumps({}),
    )

    assert response.status_code == 400
    data = json.loads(response.data)
    assert len(data["errors"]) > 0


def test_get_product(authed_client, mock_db):
    """Test getting a single product with children."""
    mock_db.product.find_unique.return_value = make_obj(
        id="prod-123",
        name="Test Product",
        description="A test product",
        active=True,
        metadata={"foo": "bar"},
        createdAt=datetime(2025, 1, 10, tzinfo=timezone.utc),
        updatedAt=datetime(2025, 1, 11, tzinfo=timezone.utc),
        boards=[
            make_obj(
                id="board-1",
                productId="prod-123",
                name="Main Board",
                description=None,
                active=True,
                createdAt=datetime(2025, 1, 10, tzinfo=timezone.utc),
                updatedAt=datetime(2025, 1, 10, tzinfo=timezone.utc),
                revisions=[
                    make_obj(
                        id="rev-1",
                        boardId="board-1",
                        version="1.0",
                        peripherals=None,
                        status="ACTIVE",
                        notes="First revision",
                        createdAt=datetime(2025, 1, 10, tzinfo=timezone.utc),
                        updatedAt=datetime(2025, 1, 10, tzinfo=timezone.utc),
                    ),
                ],
            ),
        ],
        firmwareSets=[],
        **_product_defaults(),
    )

    response = authed_client.get("/v2/products/prod-123")
    assert response.status_code == 200

    data = json.loads(response.data)
    assert data["data"]["id"] == "prod-123"
    assert data["data"]["name"] == "Test Product"
    assert "boards" in data["data"]
    assert len(data["data"]["boards"]) == 1
    assert "firmwareSets" in data["data"]


def test_get_product_not_found(authed_client, mock_db):
    """Test getting a non-existent product returns 404."""
    mock_db.product.find_unique.return_value = None

    response = authed_client.get("/v2/products/nonexistent")
    assert response.status_code == 404


def test_update_product(authed_client, mock_db):
    """Test updating an existing product."""
    existing = make_obj(
        id="prod-update",
        name="Old Name",
        description="Old description",
        active=True,
        metadata={},
        createdAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
        updatedAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
        **_product_defaults(),
    )
    mock_db.product.find_unique.return_value = existing

    mock_db.product.update.return_value = make_obj(
        id="prod-update",
        name="Old Name",
        description="New description",
        active=False,
        metadata={"updated": True},
        createdAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
        updatedAt=datetime(2025, 1, 15, tzinfo=timezone.utc),
        boards=[],
        firmwareSets=[],
        **_product_defaults(),
    )

    with patch("src.api.v2.products.products.log_audit"):
        response = authed_client.put(
            "/v2/products/prod-update",
            data=json.dumps({
                "description": "New description",
                "active": False,
            }),
        )

    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["data"]["description"] == "New description"
    assert data["data"]["active"] is False


def test_update_product_not_found(authed_client, mock_db):
    """Test updating a non-existent product returns 404."""
    mock_db.product.find_unique.return_value = None

    response = authed_client.put(
        "/v2/products/nonexistent",
        data=json.dumps({"name": "New Name"}),
    )

    assert response.status_code == 404


def test_delete_product(authed_client, mock_db):
    """Test deleting a product with no sessions or tests."""
    mock_db.product.find_unique.return_value = make_obj(
        id="prod-delete",
        name="Product to Delete",
        description="",
        active=True,
        metadata={},
        createdAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
        updatedAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
        **_product_defaults(),
    )

    # Mock session and test checks return None
    mock_db.session.find_first.return_value = None
    mock_db.test.find_first.return_value = None

    with patch("src.api.v2.products.products.log_audit"):
        response = authed_client.delete("/v2/products/prod-delete")

    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["data"]["deleted"] is True


def test_delete_product_with_sessions(authed_client, mock_db):
    """Test deleting a product with sessions returns 409."""
    mock_db.product.find_unique.return_value = make_obj(
        id="prod-has-sessions",
        name="Product with Sessions",
        description="",
        active=True,
        metadata={},
        createdAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
        updatedAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
        **_product_defaults(),
    )

    # Mock session check returns a session
    mock_db.session.find_first.return_value = make_obj(
        id="session-1",
        productId="prod-has-sessions",
    )

    response = authed_client.delete("/v2/products/prod-has-sessions")
    assert response.status_code == 409
    data = json.loads(response.data)
    assert len(data["errors"]) > 0


def test_update_product_duplicate_name(authed_client, mock_db):
    """Test updating a product to a duplicate name returns 409."""
    existing = make_obj(
        id="prod-update",
        name="Old Name",
        description="",
        active=True,
        metadata={},
        createdAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
        updatedAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
        **_product_defaults(),
    )
    dup = make_obj(
        id="prod-other",
        name="Taken Name",
        **_product_defaults(),
    )

    mock_db.product.find_unique.side_effect = [existing, dup]

    with patch("src.api.v2.products.products.log_audit"):
        response = authed_client.put(
            "/v2/products/prod-update",
            data=json.dumps({"name": "Taken Name"}),
        )

    assert response.status_code == 409


def test_delete_product_with_tests(authed_client, mock_db):
    """Test deleting a product with associated tests returns 409."""
    mock_db.product.find_unique.return_value = make_obj(
        id="prod-has-tests",
        name="Product with Tests",
        description="",
        active=True,
        metadata={},
        createdAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
        updatedAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
        **_product_defaults(),
    )

    mock_db.session.find_first.return_value = None
    mock_db.test.find_first.return_value = make_obj(
        id="test-1",
        productId="prod-has-tests",
    )

    response = authed_client.delete("/v2/products/prod-has-tests")
    assert response.status_code == 409
    data = json.loads(response.data)
    assert len(data["errors"]) > 0


# ── Target tests ───────────────────────────────────────────


def test_create_product_no_targets_in_product_create(authed_client, mock_db):
    """Product create no longer includes targets — targets live on BoardRevision."""
    mock_db.product.find_unique.return_value = None

    created = make_obj(
        id="prod-t1",
        name="Alpha",
        description="",
        active=True,
        metadata={},
        slug=None,
        buildConfig=None,
        createdAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
        updatedAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
        boards=[],
        firmwareSets=[],
    )
    mock_db.product.create.return_value = created

    with patch("api.v2.products.products.log_audit"):
        authed_client.post(
            "/v2/products",
            data=json.dumps({
                "name": "Alpha",
            }),
        )

    call_kwargs = mock_db.product.create.call_args[1]
    assert "targets" not in call_kwargs["data"]


def test_get_product_includes_targets_in_response(authed_client, mock_db):
    """GET /v2/products/<id> includes targets collected from board revisions."""
    mock_db.product.find_unique.return_value = make_obj(
        id="prod-with-targets",
        name="Alpha",
        description="",
        active=True,
        metadata={},
        slug=None,
        buildConfig=None,
        createdAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
        updatedAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
        boards=[
            make_obj(
                id="board-1",
                productId="prod-with-targets",
                name="Main Board",
                description=None,
                active=True,
                createdAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
                updatedAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
                revisions=[
                    make_obj(
                        id="rev-1",
                        boardId="board-1",
                        version="B0",
                        status="ACTIVE",
                        notes=None,
                        createdAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
                        updatedAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
                        targets=[
                            make_obj(id="tgt-1", role="app", soc="nrf52840", appId=109),
                        ],
                    ),
                ],
            ),
        ],
        firmwareSets=[],
    )

    response = authed_client.get("/v2/products/prod-with-targets")
    assert response.status_code == 200

    data = json.loads(response.data)
    targets = data["data"]["targets"]
    assert len(targets) == 1
    assert targets[0]["role"] == "app"
    assert targets[0]["soc"] == "nrf52840"
    assert targets[0]["appId"] == 109


def test_get_product_empty_targets_returns_empty_list(authed_client, mock_db):
    """GET /v2/products/<id> returns targets=[] when no board revisions have targets."""
    mock_db.product.find_unique.return_value = make_obj(
        id="prod-no-targets",
        name="Alpha",
        description="",
        active=True,
        metadata={},
        slug=None,
        buildConfig=None,
        createdAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
        updatedAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
        boards=[],
        firmwareSets=[],
    )

    response = authed_client.get("/v2/products/prod-no-targets")
    assert response.status_code == 200

    data = json.loads(response.data)
    assert data["data"]["targets"] == []


def test_delete_product_with_board_targets_succeeds(authed_client, mock_db):
    """Products with board revision targets can be deleted — Prisma cascade handles cleanup."""
    mock_db.product.find_unique.return_value = make_obj(
        id="prod-cascade",
        name="Alpha",
        description="",
        active=True,
        metadata={},
        createdAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
        updatedAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
        **_product_defaults(),
    )
    mock_db.session.find_first.return_value = None
    mock_db.test.find_first.return_value = None

    with patch("api.v2.products.products.log_audit"):
        response = authed_client.delete("/v2/products/prod-cascade")

    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["data"]["deleted"] is True
    mock_db.product.delete.assert_called_once_with(where={"id": "prod-cascade"})
