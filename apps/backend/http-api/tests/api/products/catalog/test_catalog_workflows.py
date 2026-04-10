"""Cross-entity workflow integration tests for the Catalog API."""

import json
from datetime import datetime, timezone
from io import BytesIO
from unittest.mock import MagicMock, patch

import pytest

from tests.conftest import make_obj


@pytest.fixture(autouse=True)
def _mock_presigned_url():
    """Mock presigned_url in catalog.shared so no real storage connection is made."""
    with patch("api.v2.products.shared.presigned_get_url", return_value=None):
        yield


# ── 1. Board with revisions blocks delete ──


def test_board_with_revisions_blocks_delete(authed_client, mock_db):
    """Deleting a board that has revisions should return 409."""
    mock_db.board.find_first.return_value = make_obj(
        id="board-1",
        productId="prod-1",
        name="Main Board",
        description="Primary PCB",
        active=True,
        createdAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
        updatedAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
        revisions=[
            make_obj(id="rev-1", boardId="board-1", version="1.0"),
        ],
    )

    response = authed_client.delete("/v2/products/prod-1/boards/board-1")
    assert response.status_code == 409
    data = json.loads(response.data)
    assert "revisions" in data["errors"][0]["message"].lower()


# ── 2. Product with sessions blocks delete ──


def test_product_with_runs_blocks_delete(authed_client, mock_db):
    """Deleting a product that has test runs should return 409."""
    mock_db.product.find_unique.return_value = make_obj(
        id="prod-1",
        name="Product Alpha",
        description="",
        active=True,
        metadata={},
        createdAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
        updatedAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
    )

    mock_db.testrun.find_first.return_value = make_obj(
        id="run-1",
        productId="prod-1",
    )

    response = authed_client.delete("/v2/products/prod-1")
    assert response.status_code == 409


# ── 3. Board name unique per product ──


def test_board_name_unique_per_product(authed_client, mock_db):
    """Same board name should conflict in the same product but succeed in a different product."""
    mock_db.product.find_unique.return_value = make_obj(
        id="prod-1",
        name="Product Alpha",
    )

    mock_db.board.find_first.return_value = make_obj(
        id="existing-board",
        productId="prod-1",
        name="Main Board",
    )

    response = authed_client.post(
        "/v2/products/prod-1/boards",
        data=json.dumps({"name": "Main Board", "ckBoardsFamily": "main_board"}),
    )
    assert response.status_code == 409

    mock_db.product.find_unique.return_value = make_obj(
        id="prod-2",
        name="Product Beta",
    )
    mock_db.board.find_first.return_value = None

    mock_db.board.create.return_value = make_obj(
        id="board-new",
        productId="prod-2",
        name="Main Board",
        ckBoardsFamily="main_board_beta",
        vendor="corekinect",
        description=None,
        active=True,
        createdAt=datetime(2025, 2, 1, tzinfo=timezone.utc),
        updatedAt=datetime(2025, 2, 1, tzinfo=timezone.utc),
        revisions=[],
    )

    with patch("src.api.v2.products.boards.log_audit"):
        response = authed_client.post(
            "/v2/products/prod-2/boards",
            data=json.dumps({"name": "Main Board", "ckBoardsFamily": "main_board_beta"}),
        )

    assert response.status_code == 201
    data = json.loads(response.data)
    assert data["data"]["name"] == "Main Board"
    assert data["data"]["productId"] == "prod-2"


# ── 5. Revision version unique per board ──


def test_revision_version_unique_per_board(authed_client, mock_db):
    """Same revision version should conflict on the same board but succeed on a different board."""
    mock_db.board.find_first.return_value = make_obj(
        id="board-1",
        productId="prod-1",
        name="Main Board",
    )

    mock_db.boardrevision.find_first.return_value = make_obj(
        id="rev-existing",
        boardId="board-1",
        version="1.0",
    )

    response = authed_client.post(
        "/v2/products/prod-1/boards/board-1/revisions",
        data=json.dumps({"version": "1.0", "ckBoardsName": "alpha_a0"}),
    )
    assert response.status_code == 409

    mock_db.board.find_first.return_value = make_obj(
        id="board-2",
        productId="prod-1",
        name="Sensor Board",
    )
    mock_db.boardrevision.find_first.return_value = None

    mock_db.boardrevision.create.return_value = make_obj(
        id="rev-new",
        boardId="board-2",
        version="1.0",
        ckBoardsName="sensor_a0",
        socs=[],
        status="ACTIVE",
        notes=None,
        createdAt=datetime(2025, 2, 1, tzinfo=timezone.utc),
        updatedAt=datetime(2025, 2, 1, tzinfo=timezone.utc),
    )

    with patch("src.api.v2.products.board_revisions.log_audit"):
        response = authed_client.post(
            "/v2/products/prod-1/boards/board-2/revisions",
            data=json.dumps({"version": "1.0", "ckBoardsName": "sensor_a0"}),
        )

    assert response.status_code == 201
    data = json.loads(response.data)
    assert data["data"]["version"] == "1.0"
    assert data["data"]["boardId"] == "board-2"


# ── 6. Firmware version unique per product + target ──


def test_firmware_set_list(authed_client, mock_db):
    """FirmwareSet list returns sets for a product."""
    mock_db.product.find_unique.return_value = make_obj(id="prod-1", name="Alpha")
    mock_db.firmwareset.count.return_value = 0
    mock_db.firmwareset.find_many.return_value = []

    response = authed_client.get("/v2/products/prod-1/firmware")
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["data"]["data"] == []
    assert data["data"]["pagination"]["total"] == 0


