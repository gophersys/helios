"""Integration tests for the Products API."""

import json
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

from tests.conftest import make_obj


def test_list_products(authed_client, mock_db):
    """Test listing products with pagination."""
    # Mock DB responses
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
            boardRevisions=[],
            firmwareApplications=[],
            firmwareBuilds=[],
        ),
        make_obj(
            id="prod-2",
            name="Product Beta",
            description="Second product",
            active=False,
            metadata={"key": "value"},
            createdAt=datetime(2025, 1, 2, tzinfo=timezone.utc),
            updatedAt=datetime(2025, 1, 2, tzinfo=timezone.utc),
            boardRevisions=[],
            firmwareApplications=[],
            firmwareBuilds=[],
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
    # Mock find_unique returns None (no duplicate)
    mock_db.product.find_unique.return_value = None

    # Mock create returns new product
    mock_db.product.create.return_value = make_obj(
        id="prod-new",
        name="New Product",
        description="A new product",
        active=True,
        metadata={},
        createdAt=datetime(2025, 1, 15, tzinfo=timezone.utc),
        updatedAt=datetime(2025, 1, 15, tzinfo=timezone.utc),
        boardRevisions=[],
        firmwareApplications=[],
        firmwareBuilds=[],
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
    # Mock find_unique returns existing product
    mock_db.product.find_unique.return_value = make_obj(
        id="existing-prod",
        name="Existing Product",
        description="",
        active=True,
        metadata={},
        createdAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
        updatedAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
    )

    response = authed_client.post(
        "/v2/products",
        data=json.dumps({"name": "Existing Product"}),
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
    # Mock find_unique returns product with children
    mock_db.product.find_unique.return_value = make_obj(
        id="prod-123",
        name="Test Product",
        description="A test product",
        active=True,
        metadata={"foo": "bar"},
        createdAt=datetime(2025, 1, 10, tzinfo=timezone.utc),
        updatedAt=datetime(2025, 1, 11, tzinfo=timezone.utc),
        boardRevisions=[
            make_obj(
                id="rev-1",
                productId="prod-123",
                version="1.0",
                chipsets=["nRF9160"],
                status="ACTIVE",
                notes="First revision",
                createdAt=datetime(2025, 1, 10, tzinfo=timezone.utc),
                updatedAt=datetime(2025, 1, 10, tzinfo=timezone.utc),
            ),
        ],
        firmwareApplications=[
            make_obj(
                id="app-1",
                productId="prod-123",
                applicationId=1,
                name="Main App",
                targetMcu="nRF9160",
                chipset="Sigma5 Cx",
                coreCloudDeviceType="device",
                coreCloudVariant="v1",
                notes=None,
                createdAt=datetime(2025, 1, 10, tzinfo=timezone.utc),
                updatedAt=datetime(2025, 1, 10, tzinfo=timezone.utc),
                firmwareBuilds=[],
            ),
        ],
        firmwareBuilds=[],
    )

    response = authed_client.get("/v2/products/prod-123")
    assert response.status_code == 200

    data = json.loads(response.data)
    assert data["data"]["id"] == "prod-123"
    assert data["data"]["name"] == "Test Product"
    assert "boardRevisions" in data["data"]
    assert len(data["data"]["boardRevisions"]) == 1
    assert "firmwareApplications" in data["data"]
    assert len(data["data"]["firmwareApplications"]) == 1


def test_get_product_not_found(authed_client, mock_db):
    """Test getting a non-existent product returns 404."""
    mock_db.product.find_unique.return_value = None

    response = authed_client.get("/v2/products/nonexistent")
    assert response.status_code == 404


def test_update_product(authed_client, mock_db):
    """Test updating an existing product."""
    # Mock find_unique returns existing product
    existing = make_obj(
        id="prod-update",
        name="Old Name",
        description="Old description",
        active=True,
        metadata={},
        createdAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
        updatedAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
    )
    mock_db.product.find_unique.return_value = existing

    # Mock update returns updated product
    mock_db.product.update.return_value = make_obj(
        id="prod-update",
        name="Old Name",
        description="New description",
        active=False,
        metadata={"updated": True},
        createdAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
        updatedAt=datetime(2025, 1, 15, tzinfo=timezone.utc),
        boardRevisions=[],
        firmwareApplications=[],
        firmwareBuilds=[],
    )

    with patch("src.api.v2.products.products.log_audit"):
        response = authed_client.put(
            "/v2/products/prod-update",
            data=json.dumps({
                "description": "New description",
                "active": False,
                "metadata": {"updated": True},
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
    # Mock find_unique returns existing product
    mock_db.product.find_unique.return_value = make_obj(
        id="prod-delete",
        name="Product to Delete",
        description="",
        active=True,
        metadata={},
        createdAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
        updatedAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
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
    # Mock find_unique returns existing product
    mock_db.product.find_unique.return_value = make_obj(
        id="prod-has-sessions",
        name="Product with Sessions",
        description="",
        active=True,
        metadata={},
        createdAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
        updatedAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
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
