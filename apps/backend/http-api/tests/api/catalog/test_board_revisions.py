"""Integration tests for Board Revisions API."""

import json
from datetime import datetime, timezone
from unittest.mock import patch

from tests.conftest import make_obj


def test_create_board_revision(authed_client, mock_db):
    """Test creating a new board revision."""
    mock_db.board.find_first.return_value = make_obj(
        id="board-1",
        productId="prod-1",
        name="Main Board",
    )

    mock_db.boardrevision.find_first.return_value = None

    mock_db.boardrevision.create.return_value = make_obj(
        id="rev-new",
        boardId="board-1",
        version="2.0",
        ckBoardsName="alpha_b0",
        socs=["nrf52840", "nrf9151"],
        status="ACTIVE",
        notes="New revision",
        createdAt=datetime(2025, 1, 15, tzinfo=timezone.utc),
        updatedAt=datetime(2025, 1, 15, tzinfo=timezone.utc),
    )

    with patch("src.api.v2.products.board_revisions.log_audit"):
        response = authed_client.post(
            "/v2/products/prod-1/boards/board-1/revisions",
            data=json.dumps({
                "version": "2.0",
                "ckBoardsName": "alpha_b0",
                "socs": ["nrf52840", "nrf9151"],
                "status": "ACTIVE",
                "notes": "New revision",
            }),
        )

    assert response.status_code == 201
    data = json.loads(response.data)
    assert data["data"]["version"] == "2.0"
    assert data["data"]["ckBoardsName"] == "alpha_b0"
    assert data["data"]["status"] == "ACTIVE"


def test_create_board_revision_board_not_found(authed_client, mock_db):
    """Test creating board revision for non-existent board returns 404."""
    mock_db.board.find_first.return_value = None

    response = authed_client.post(
        "/v2/products/prod-1/boards/nonexistent/revisions",
        data=json.dumps({"version": "1.0", "ckBoardsName": "test_a0"}),
    )

    assert response.status_code == 404


def test_create_board_revision_duplicate_version(authed_client, mock_db):
    """Test creating board revision with duplicate version returns 409."""
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
    data = json.loads(response.data)
    assert len(data["errors"]) > 0


def test_update_board_revision(authed_client, mock_db):
    """Test updating an existing board revision."""
    mock_db.board.find_first.return_value = make_obj(
        id="board-1",
        productId="prod-1",
        name="Main Board",
    )

    existing = make_obj(
        id="rev-1",
        boardId="board-1",
        version="1.0",
        status="ACTIVE",
        notes="Old notes",
        createdAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
        updatedAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
    )
    mock_db.boardrevision.find_first.return_value = existing

    mock_db.boardrevision.find_unique.return_value = make_obj(
        id="rev-1",
        boardId="board-1",
        version="1.0",
        status="DEPRECATED",
        notes="Updated notes",
        createdAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
        updatedAt=datetime(2025, 1, 15, tzinfo=timezone.utc),
    )

    with patch("src.api.v2.products.board_revisions.log_audit"):
        response = authed_client.put(
            "/v2/products/prod-1/boards/board-1/revisions/rev-1",
            data=json.dumps({
                "status": "DEPRECATED",
                "notes": "Updated notes",
            }),
        )

    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["data"]["status"] == "DEPRECATED"


def test_delete_board_revision(authed_client, mock_db):
    """Test deleting a board revision."""
    mock_db.board.find_first.return_value = make_obj(
        id="board-1",
        productId="prod-1",
        name="Main Board",
    )

    mock_db.boardrevision.find_first.return_value = make_obj(
        id="rev-delete",
        boardId="board-1",
        version="1.0",
        status="ACTIVE",
        notes=None,
        createdAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
        updatedAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
    )

    with patch("src.api.v2.products.board_revisions.log_audit"):
        response = authed_client.delete("/v2/products/prod-1/boards/board-1/revisions/rev-delete")

    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["data"]["deleted"] is True


def test_create_board_revision_minimal_fields(authed_client, mock_db):
    """Test creating board revision with version + ckBoardsName succeeds."""
    mock_db.board.find_first.return_value = make_obj(
        id="board-1",
        productId="prod-1",
        name="Main Board",
    )

    mock_db.boardrevision.find_first.return_value = None

    mock_db.boardrevision.create.return_value = make_obj(
        id="rev-new",
        boardId="board-1",
        version="3.0",
        ckBoardsName="alpha_c0",
        socs=[],
        status="ACTIVE",
        notes=None,
        createdAt=datetime(2025, 1, 15, tzinfo=timezone.utc),
        updatedAt=datetime(2025, 1, 15, tzinfo=timezone.utc),
    )

    with patch("src.api.v2.products.board_revisions.log_audit"):
        response = authed_client.post(
            "/v2/products/prod-1/boards/board-1/revisions",
            data=json.dumps({"version": "3.0", "ckBoardsName": "alpha_c0"}),
        )

    assert response.status_code == 201
    data = json.loads(response.data)
    assert data["data"]["version"] == "3.0"
    assert data["data"]["ckBoardsName"] == "alpha_c0"


def test_update_board_revision_duplicate_version(authed_client, mock_db):
    """Test updating board revision to a duplicate version returns 409."""
    mock_db.board.find_first.return_value = make_obj(
        id="board-1",
        productId="prod-1",
        name="Main Board",
    )

    existing_rev = make_obj(
        id="rev-1",
        boardId="board-1",
        version="1.0",
        status="ACTIVE",
        notes=None,
        createdAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
        updatedAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
    )
    dup_rev = make_obj(
        id="rev-2",
        boardId="board-1",
        version="2.0",
    )

    mock_db.boardrevision.find_first.side_effect = [existing_rev, dup_rev]

    response = authed_client.put(
        "/v2/products/prod-1/boards/board-1/revisions/rev-1",
        data=json.dumps({"version": "2.0"}),
    )

    assert response.status_code == 409


def test_update_board_revision_not_found(authed_client, mock_db):
    """Test updating a non-existent board revision returns 404."""
    mock_db.board.find_first.return_value = make_obj(
        id="board-1",
        productId="prod-1",
        name="Main Board",
    )

    mock_db.boardrevision.find_first.return_value = None

    response = authed_client.put(
        "/v2/products/prod-1/boards/board-1/revisions/nonexistent",
        data=json.dumps({"status": "DEPRECATED"}),
    )

    assert response.status_code == 404


def test_delete_board_revision_not_found(authed_client, mock_db):
    """Test deleting a non-existent board revision returns 404."""
    mock_db.board.find_first.return_value = make_obj(
        id="board-1",
        productId="prod-1",
        name="Main Board",
    )

    mock_db.boardrevision.find_first.return_value = None

    response = authed_client.delete("/v2/products/prod-1/boards/board-1/revisions/nonexistent")

    assert response.status_code == 404
