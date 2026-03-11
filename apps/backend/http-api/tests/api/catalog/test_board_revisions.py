"""Integration tests for Board Revisions API."""

import json
from datetime import datetime, timezone
from unittest.mock import patch

from tests.conftest import make_obj


def test_create_board_revision(authed_client, mock_db):
    """Test creating a new board revision."""
    # Mock board exists and belongs to product
    mock_db.board.find_first.return_value = make_obj(
        id="board-1",
        productId="prod-1",
        name="Main Board",
    )

    # Mock no existing revision with same version
    mock_db.boardrevision.find_first.return_value = None

    # Mock chipsets exist
    mock_db.chipset.find_unique.return_value = make_obj(
        id="chip-1",
        name="nRF9160",
        isModem=True,
    )

    # Mock create returns new revision
    mock_db.boardrevision.create.return_value = make_obj(
        id="rev-new",
        boardId="board-1",
        version="2.0",
        selectedBuilds=None,
        status="ACTIVE",
        notes="New revision",
        createdAt=datetime(2025, 1, 15, tzinfo=timezone.utc),
        updatedAt=datetime(2025, 1, 15, tzinfo=timezone.utc),
        chipsets=[],
    )

    # Mock re-fetch after chipset creation
    mock_db.boardrevision.find_unique.return_value = make_obj(
        id="rev-new",
        boardId="board-1",
        version="2.0",
        selectedBuilds=None,
        status="ACTIVE",
        notes="New revision",
        createdAt=datetime(2025, 1, 15, tzinfo=timezone.utc),
        updatedAt=datetime(2025, 1, 15, tzinfo=timezone.utc),
        chipsets=[
            make_obj(
                chipset=make_obj(id="chip-1", name="nRF9160", isModem=True),
            ),
        ],
    )

    with patch("src.api.v2.catalog.board_revisions.log_audit"):
        response = authed_client.post(
            "/v2/products/prod-1/boards/board-1/revisions",
            data=json.dumps({
                "version": "2.0",
                "chipsetIds": ["chip-1"],
                "status": "ACTIVE",
                "notes": "New revision",
            }),
        )

    assert response.status_code == 201
    data = json.loads(response.data)
    assert data["data"]["version"] == "2.0"
    assert data["data"]["status"] == "ACTIVE"
    assert len(data["data"]["chipsets"]) == 1
    assert data["data"]["chipsets"][0]["name"] == "nRF9160"


def test_create_board_revision_board_not_found(authed_client, mock_db):
    """Test creating board revision for non-existent board returns 404."""
    mock_db.board.find_first.return_value = None

    response = authed_client.post(
        "/v2/products/prod-1/boards/nonexistent/revisions",
        data=json.dumps({"version": "1.0"}),
    )

    assert response.status_code == 404


def test_create_board_revision_duplicate_version(authed_client, mock_db):
    """Test creating board revision with duplicate version returns 409."""
    mock_db.board.find_first.return_value = make_obj(
        id="board-1",
        productId="prod-1",
        name="Main Board",
    )

    # Existing revision with same version
    mock_db.boardrevision.find_first.return_value = make_obj(
        id="rev-existing",
        boardId="board-1",
        version="1.0",
    )

    response = authed_client.post(
        "/v2/products/prod-1/boards/board-1/revisions",
        data=json.dumps({"version": "1.0"}),
    )

    assert response.status_code == 409
    data = json.loads(response.data)
    assert len(data["errors"]) > 0


def test_update_board_revision(authed_client, mock_db):
    """Test updating an existing board revision."""
    # Mock board exists
    mock_db.board.find_first.return_value = make_obj(
        id="board-1",
        productId="prod-1",
        name="Main Board",
    )

    # Mock find revision
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

    # Mock re-fetch after update
    mock_db.boardrevision.find_unique.return_value = make_obj(
        id="rev-1",
        boardId="board-1",
        version="1.0",
        selectedBuilds=None,
        status="DEPRECATED",
        notes="Updated notes",
        createdAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
        updatedAt=datetime(2025, 1, 15, tzinfo=timezone.utc),
        chipsets=[],
    )

    with patch("src.api.v2.catalog.board_revisions.log_audit"):
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
    # Mock board exists
    mock_db.board.find_first.return_value = make_obj(
        id="board-1",
        productId="prod-1",
        name="Main Board",
    )

    # Mock revision exists
    mock_db.boardrevision.find_first.return_value = make_obj(
        id="rev-delete",
        boardId="board-1",
        version="1.0",
        status="ACTIVE",
        notes=None,
        createdAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
        updatedAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
    )

    with patch("src.api.v2.catalog.board_revisions.log_audit"):
        response = authed_client.delete("/v2/products/prod-1/boards/board-1/revisions/rev-delete")

    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["data"]["deleted"] is True


def test_create_board_revision_invalid_chipset(authed_client, mock_db):
    """Test creating board revision with invalid chipset returns 400."""
    mock_db.board.find_first.return_value = make_obj(
        id="board-1",
        productId="prod-1",
        name="Main Board",
    )

    mock_db.boardrevision.find_first.return_value = None
    mock_db.chipset.find_unique.return_value = None

    response = authed_client.post(
        "/v2/products/prod-1/boards/board-1/revisions",
        data=json.dumps({"version": "3.0", "chipsetIds": ["bad-chip"]}),
    )

    assert response.status_code == 400


def test_create_board_revision_no_chipsets(authed_client, mock_db):
    """Test creating board revision with no chipsets succeeds."""
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
        selectedBuilds=None,
        status="ACTIVE",
        notes=None,
        createdAt=datetime(2025, 1, 15, tzinfo=timezone.utc),
        updatedAt=datetime(2025, 1, 15, tzinfo=timezone.utc),
        chipsets=[],
    )

    mock_db.boardrevision.find_unique.return_value = make_obj(
        id="rev-new",
        boardId="board-1",
        version="3.0",
        selectedBuilds=None,
        status="ACTIVE",
        notes=None,
        createdAt=datetime(2025, 1, 15, tzinfo=timezone.utc),
        updatedAt=datetime(2025, 1, 15, tzinfo=timezone.utc),
        chipsets=[],
    )

    with patch("src.api.v2.catalog.board_revisions.log_audit"):
        response = authed_client.post(
            "/v2/products/prod-1/boards/board-1/revisions",
            data=json.dumps({"version": "3.0"}),
        )

    assert response.status_code == 201
    data = json.loads(response.data)
    assert data["data"]["version"] == "3.0"
    assert data["data"]["chipsets"] == []


def test_update_board_revision_chipsets(authed_client, mock_db):
    """Test updating board revision chipsets."""
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
    mock_db.boardrevision.find_first.return_value = existing_rev

    mock_db.chipset.find_unique.return_value = make_obj(
        id="chip-a",
        name="nRF52840",
        isModem=False,
    )

    mock_db.boardrevision.find_unique.return_value = make_obj(
        id="rev-1",
        boardId="board-1",
        version="1.0",
        selectedBuilds=None,
        status="ACTIVE",
        notes=None,
        createdAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
        updatedAt=datetime(2025, 1, 15, tzinfo=timezone.utc),
        chipsets=[
            make_obj(chipset=make_obj(id="chip-a", name="nRF52840", isModem=False)),
            make_obj(chipset=make_obj(id="chip-b", name="nRF9160", isModem=True)),
        ],
    )

    with patch("src.api.v2.catalog.board_revisions.log_audit"):
        response = authed_client.put(
            "/v2/products/prod-1/boards/board-1/revisions/rev-1",
            data=json.dumps({"chipsetIds": ["chip-a", "chip-b"]}),
        )

    assert response.status_code == 200
    data = json.loads(response.data)
    assert len(data["data"]["chipsets"]) == 2

    mock_db.boardrevisionchipset.delete_many.assert_called_once()
    assert mock_db.boardrevisionchipset.create.call_count == 2


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
