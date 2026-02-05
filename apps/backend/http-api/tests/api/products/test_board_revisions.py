"""Integration tests for Board Revisions API."""

import json
from datetime import datetime, timezone
from unittest.mock import patch

from tests.conftest import make_obj


def test_create_board_revision(authed_client, mock_db):
    """Test creating a new board revision."""
    # Mock product exists
    mock_db.product.find_unique.return_value = make_obj(
        id="prod-1",
        name="Test Product",
        description="",
        active=True,
        metadata={},
        createdAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
        updatedAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
    )

    # Mock no existing revision with same version
    mock_db.productboardrevision.find_first.return_value = None

    # Mock create returns new revision
    mock_db.productboardrevision.create.return_value = make_obj(
        id="rev-new",
        productId="prod-1",
        version="2.0",
        chipsets=["nRF9160", "nRF52840"],
        status="ACTIVE",
        notes="New revision",
        createdAt=datetime(2025, 1, 15, tzinfo=timezone.utc),
        updatedAt=datetime(2025, 1, 15, tzinfo=timezone.utc),
    )

    with patch("src.api.v2.products.board_revisions.log_audit"):
        response = authed_client.post(
            "/v2/products/prod-1/board-revisions",
            data=json.dumps({
                "version": "2.0",
                "chipsets": ["nRF9160", "nRF52840"],
                "status": "ACTIVE",
                "notes": "New revision",
            }),
        )

    assert response.status_code == 201
    data = json.loads(response.data)
    assert data["data"]["version"] == "2.0"
    assert data["data"]["chipsets"] == ["nRF9160", "nRF52840"]
    assert data["data"]["status"] == "ACTIVE"


def test_create_board_revision_product_not_found(authed_client, mock_db):
    """Test creating board revision for non-existent product returns 404."""
    mock_db.product.find_unique.return_value = None

    response = authed_client.post(
        "/v2/products/nonexistent/board-revisions",
        data=json.dumps({"version": "1.0"}),
    )

    assert response.status_code == 404


def test_create_board_revision_duplicate_version(authed_client, mock_db):
    """Test creating board revision with duplicate version returns 409."""
    # Mock product exists
    mock_db.product.find_unique.return_value = make_obj(
        id="prod-1",
        name="Test Product",
        description="",
        active=True,
        metadata={},
        createdAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
        updatedAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
    )

    # Mock existing revision with same version
    mock_db.productboardrevision.find_first.return_value = make_obj(
        id="rev-existing",
        productId="prod-1",
        version="1.0",
        chipsets=[],
        status="ACTIVE",
        notes=None,
        createdAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
        updatedAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
    )

    response = authed_client.post(
        "/v2/products/prod-1/board-revisions",
        data=json.dumps({"version": "1.0"}),
    )

    assert response.status_code == 409
    data = json.loads(response.data)
    assert len(data["errors"]) > 0


def test_update_board_revision(authed_client, mock_db):
    """Test updating an existing board revision."""
    # Mock find_first returns existing revision
    existing = make_obj(
        id="rev-1",
        productId="prod-1",
        version="1.0",
        chipsets=["nRF9160"],
        status="ACTIVE",
        notes="Old notes",
        createdAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
        updatedAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
    )
    mock_db.productboardrevision.find_first.return_value = existing

    # Mock update returns updated revision
    mock_db.productboardrevision.update.return_value = make_obj(
        id="rev-1",
        productId="prod-1",
        version="1.0",
        chipsets=["nRF9151", "nRF52840"],
        status="DEPRECATED",
        notes="Updated notes",
        createdAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
        updatedAt=datetime(2025, 1, 15, tzinfo=timezone.utc),
    )

    with patch("src.api.v2.products.board_revisions.log_audit"):
        response = authed_client.put(
            "/v2/products/prod-1/board-revisions/rev-1",
            data=json.dumps({
                "chipsets": ["nRF9151", "nRF52840"],
                "status": "DEPRECATED",
                "notes": "Updated notes",
            }),
        )

    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["data"]["status"] == "DEPRECATED"
    assert data["data"]["chipsets"] == ["nRF9151", "nRF52840"]


def test_delete_board_revision(authed_client, mock_db):
    """Test deleting a board revision with no firmware build references."""
    # Mock find_first returns existing revision
    mock_db.productboardrevision.find_first.return_value = make_obj(
        id="rev-delete",
        productId="prod-1",
        version="1.0",
        chipsets=[],
        status="ACTIVE",
        notes=None,
        createdAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
        updatedAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
    )

    # Mock no firmware build references
    mock_db.firmwarebuild.find_first.return_value = None

    with patch("src.api.v2.products.board_revisions.log_audit"):
        response = authed_client.delete("/v2/products/prod-1/board-revisions/rev-delete")

    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["data"]["deleted"] is True


def test_delete_board_revision_with_builds(authed_client, mock_db):
    """Test deleting a board revision with firmware build refs returns 409."""
    # Mock find_first returns existing revision
    mock_db.productboardrevision.find_first.return_value = make_obj(
        id="rev-has-builds",
        productId="prod-1",
        version="1.0",
        chipsets=[],
        status="ACTIVE",
        notes=None,
        createdAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
        updatedAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
    )

    # Mock firmware build reference exists
    mock_db.firmwarebuild.find_first.return_value = make_obj(
        id="build-1",
        boardRevisionId="rev-has-builds",
    )

    response = authed_client.delete("/v2/products/prod-1/board-revisions/rev-has-builds")
    assert response.status_code == 409
    data = json.loads(response.data)
    assert len(data["errors"]) > 0
