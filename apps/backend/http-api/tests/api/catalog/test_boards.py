"""Integration tests for the Boards API."""

import json
from datetime import datetime, timezone
from unittest.mock import patch

from tests.conftest import make_obj


def test_list_boards(authed_client, mock_db):
    """Test listing boards for a product."""
    mock_db.product.find_unique.return_value = make_obj(
        id="prod-1",
        name="Test Product",
    )

    mock_db.board.count.return_value = 2
    mock_db.board.find_many.return_value = [
        make_obj(
            id="board-1",
            productId="prod-1",
            name="Main Board",
            description="Primary PCB",
            active=True,
            createdAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
            updatedAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
            revisions=[],
        ),
        make_obj(
            id="board-2",
            productId="prod-1",
            name="Sensor Board",
            description="Sensor addon",
            active=True,
            createdAt=datetime(2025, 1, 2, tzinfo=timezone.utc),
            updatedAt=datetime(2025, 1, 2, tzinfo=timezone.utc),
            revisions=[],
        ),
    ]

    response = authed_client.get("/v2/products/prod-1/boards")
    assert response.status_code == 200

    data = json.loads(response.data)
    assert "data" in data
    assert isinstance(data["data"], list)
    assert len(data["data"]) == 2


def test_list_boards_product_not_found(authed_client, mock_db):
    """Test listing boards for non-existent product returns 404."""
    mock_db.product.find_unique.return_value = None

    response = authed_client.get("/v2/products/nonexistent/boards")
    assert response.status_code == 404


def test_create_board(authed_client, mock_db):
    """Test creating a new board."""
    mock_db.product.find_unique.return_value = make_obj(
        id="prod-1",
        name="Test Product",
    )

    # No duplicate (name check, then ckBoardsName check)
    mock_db.board.find_first.return_value = None

    mock_db.board.create.return_value = make_obj(
        id="board-new",
        productId="prod-1",
        name="New Board",
        ckBoardsName="new_board",
        ckBoardsBranch="main",
        vendor="corekinect",
        description="A new PCB",
        active=True,
        createdAt=datetime(2025, 1, 15, tzinfo=timezone.utc),
        updatedAt=datetime(2025, 1, 15, tzinfo=timezone.utc),
        revisions=[],
    )

    with patch("src.api.v2.products.boards.log_audit"):
        response = authed_client.post(
            "/v2/products/prod-1/boards",
            data=json.dumps({
                "name": "New Board",
                "ckBoardsName": "new_board",
                "description": "A new PCB",
            }),
        )

    assert response.status_code == 201
    data = json.loads(response.data)
    assert data["data"]["name"] == "New Board"
    assert data["data"]["id"] == "board-new"


def test_create_board_duplicate_name(authed_client, mock_db):
    """Test creating a board with duplicate name for same product returns 409."""
    mock_db.product.find_unique.return_value = make_obj(
        id="prod-1",
        name="Test Product",
    )

    mock_db.board.find_first.return_value = make_obj(
        id="existing-board",
        productId="prod-1",
        name="Main Board",
    )

    response = authed_client.post(
        "/v2/products/prod-1/boards",
        data=json.dumps({"name": "Main Board", "ckBoardsName": "main_board"}),
    )

    assert response.status_code == 409


def test_create_board_missing_name(authed_client, mock_db):
    """Test creating board with missing name returns 400."""
    mock_db.product.find_unique.return_value = make_obj(
        id="prod-1",
        name="Test Product",
    )

    response = authed_client.post(
        "/v2/products/prod-1/boards",
        data=json.dumps({}),
    )

    assert response.status_code == 400


def test_get_board(authed_client, mock_db):
    """Test getting a single board with revisions."""
    mock_db.board.find_first.return_value = make_obj(
        id="board-123",
        productId="prod-1",
        name="Main Board",
        description="Primary PCB",
        active=True,
        createdAt=datetime(2025, 1, 10, tzinfo=timezone.utc),
        updatedAt=datetime(2025, 1, 11, tzinfo=timezone.utc),
        revisions=[
            make_obj(
                id="rev-1",
                boardId="board-123",
                version="1.0",
                peripherals=None,
                status="ACTIVE",
                notes="First rev",
                createdAt=datetime(2025, 1, 10, tzinfo=timezone.utc),
                updatedAt=datetime(2025, 1, 10, tzinfo=timezone.utc),
                chipsets=[
                    make_obj(
                        chipset=make_obj(id="chip-1", name="nRF52840", isModem=False),
                    ),
                ],
            ),
        ],
    )

    response = authed_client.get("/v2/products/prod-1/boards/board-123")
    assert response.status_code == 200

    data = json.loads(response.data)
    assert data["data"]["id"] == "board-123"
    assert data["data"]["name"] == "Main Board"
    assert "revisions" in data["data"]
    assert len(data["data"]["revisions"]) == 1


def test_get_board_not_found(authed_client, mock_db):
    """Test getting a non-existent board returns 404."""
    mock_db.board.find_first.return_value = None

    response = authed_client.get("/v2/products/prod-1/boards/nonexistent")
    assert response.status_code == 404


def test_update_board(authed_client, mock_db):
    """Test updating an existing board."""
    existing = make_obj(
        id="board-update",
        productId="prod-1",
        name="Old Name",
        description="Old description",
        active=True,
        createdAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
        updatedAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
    )
    mock_db.board.find_first.return_value = existing

    mock_db.board.update.return_value = make_obj(
        id="board-update",
        productId="prod-1",
        name="Old Name",
        description="New description",
        active=False,
        createdAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
        updatedAt=datetime(2025, 1, 15, tzinfo=timezone.utc),
        revisions=[],
    )

    with patch("src.api.v2.products.boards.log_audit"):
        response = authed_client.put(
            "/v2/products/prod-1/boards/board-update",
            data=json.dumps({
                "description": "New description",
                "active": False,
            }),
        )

    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["data"]["description"] == "New description"
    assert data["data"]["active"] is False


def test_delete_board(authed_client, mock_db):
    """Test deleting a board with no revisions."""
    mock_db.board.find_first.return_value = make_obj(
        id="board-delete",
        productId="prod-1",
        name="Board to Delete",
        description="",
        active=True,
        createdAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
        updatedAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
    )

    # No revisions
    mock_db.boardrevision.find_first.return_value = None

    with patch("src.api.v2.products.boards.log_audit"):
        response = authed_client.delete("/v2/products/prod-1/boards/board-delete")

    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["data"]["deleted"] is True


def test_delete_board_with_revisions(authed_client, mock_db):
    """Test deleting a board with revisions returns 409."""
    mock_db.board.find_first.return_value = make_obj(
        id="board-has-revs",
        productId="prod-1",
        name="Board with Revisions",
        description="",
        active=True,
        createdAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
        updatedAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
        revisions=[
            make_obj(id="rev-1", boardId="board-has-revs", version="1.0"),
        ],
    )

    response = authed_client.delete("/v2/products/prod-1/boards/board-has-revs")
    assert response.status_code == 409


def test_update_board_no_fields(authed_client, mock_db):
    """Test updating a board with no fields returns 400."""
    mock_db.board.find_first.return_value = make_obj(
        id="board-1",
        productId="prod-1",
        name="Main Board",
        description="Primary PCB",
        active=True,
        createdAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
        updatedAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
    )

    response = authed_client.put(
        "/v2/products/prod-1/boards/board-1",
        data=json.dumps({}),
    )

    assert response.status_code == 400


def test_update_board_duplicate_name(authed_client, mock_db):
    """Test updating a board to a duplicate name returns 409."""
    existing = make_obj(
        id="board-update",
        productId="prod-1",
        name="Old Name",
        description="",
        active=True,
        createdAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
        updatedAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
    )
    dup = make_obj(
        id="board-other",
        productId="prod-1",
        name="Taken Name",
    )

    mock_db.board.find_first.side_effect = [existing, dup]

    with patch("src.api.v2.products.boards.log_audit"):
        response = authed_client.put(
            "/v2/products/prod-1/boards/board-update",
            data=json.dumps({"name": "Taken Name"}),
        )

    assert response.status_code == 409


def test_list_boards_empty(authed_client, mock_db):
    """Test listing boards when none exist returns empty array."""
    mock_db.product.find_unique.return_value = make_obj(
        id="prod-1",
        name="Test Product",
    )

    mock_db.board.find_many.return_value = []

    response = authed_client.get("/v2/products/prod-1/boards")
    assert response.status_code == 200

    data = json.loads(response.data)
    assert "data" in data
    assert isinstance(data["data"], list)
    assert len(data["data"]) == 0
