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


def test_product_with_sessions_blocks_delete(authed_client, mock_db):
    """Deleting a product that has sessions should return 409."""
    mock_db.product.find_unique.return_value = make_obj(
        id="prod-1",
        name="Product Alpha",
        description="",
        active=True,
        metadata={},
        createdAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
        updatedAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
    )

    mock_db.session.find_first.return_value = make_obj(
        id="session-1",
        productId="prod-1",
    )

    response = authed_client.delete("/v2/products/prod-1")
    assert response.status_code == 409
    data = json.loads(response.data)
    assert "sessions" in data["errors"][0]["message"].lower()


# ── 3. Product with tests blocks delete ──


def test_product_with_tests_blocks_delete(authed_client, mock_db):
    """Deleting a product that has tests (but no sessions) should return 409."""
    mock_db.product.find_unique.return_value = make_obj(
        id="prod-2",
        name="Product Beta",
        description="",
        active=True,
        metadata={},
        createdAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
        updatedAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
    )

    mock_db.session.find_first.return_value = None
    mock_db.test.find_first.return_value = make_obj(
        id="test-1",
        productId="prod-2",
    )

    response = authed_client.delete("/v2/products/prod-2")
    assert response.status_code == 409
    data = json.loads(response.data)
    assert "tests" in data["errors"][0]["message"].lower()


# ── 4. Board name unique per product ──


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


def test_firmware_version_unique_per_product_target(authed_client, mock_db):
    """Same firmware version + target should conflict, but different target should succeed."""
    mock_db.product.find_unique.return_value = make_obj(
        id="prod-1",
        name="Product Alpha",
    )

    mock_db.producttarget.find_first.return_value = make_obj(
        id="tgt-1",
        boardRevisionId="rev-1",
        role="app",
        soc="nrf52840",
        appId=109,
    )

    # Duplicate exists for prod-1 / tgt-1 / 1.0.0
    mock_db.firmwarebuild.find_first.return_value = make_obj(
        id="build-existing",
        productId="prod-1",
        targetId="tgt-1",
        version="1.0.0",
    )

    from src.services.auth.jwt import create_token
    token = create_token(
        user_id="test-user-id",
        email="test@example.com",
        name="Test User",
        permission_set_id="test-perm-set-id",
    )
    auth_headers = {"Authorization": f"Bearer {token}"}

    response = authed_client._client.post(
        "/v2/products/prod-1/firmware/upload",
        headers=auth_headers,
        data={
            "targetId": "tgt-1",
            "version": "1.0.0",
            "file": (BytesIO(b"\x00\x01\x02\x03"), "app.bin"),
        },
        content_type="multipart/form-data",
    )
    assert response.status_code == 409

    # Now upload with a different target (tgt-2) — no duplicate
    mock_db.producttarget.find_first.return_value = make_obj(
        id="tgt-2",
        boardRevisionId="rev-1",
        role="comms",
        soc="nrf9151",
        appId=108,
    )
    mock_db.firmwarebuild.find_first.return_value = None

    mock_db.firmwarebuild.create.return_value = make_obj(
        id="build-new",
        productId="prod-1",
        targetId="tgt-2",
        version="1.0.0",
        isManufacturing=False,
        storageKey="firmware/prod-1/pending/app.bin",
        filename="app.bin",
        sizeBytes=4,
        checksum="abc123",
        contentType="application/octet-stream",
        status="DRAFT",
        notes=None,
        createdAt=datetime(2025, 2, 1, tzinfo=timezone.utc),
        updatedAt=datetime(2025, 2, 1, tzinfo=timezone.utc),
    )

    mock_db.firmwarebuild.update.return_value = make_obj(
        id="build-new",
        productId="prod-1",
        targetId="tgt-2",
        version="1.0.0",
        isManufacturing=False,
        storageKey="firmware/prod-1/build-new/app.bin",
        filename="app.bin",
        sizeBytes=4,
        checksum="abc123",
        contentType="application/octet-stream",
        status="DRAFT",
        notes=None,
        createdAt=datetime(2025, 2, 1, tzinfo=timezone.utc),
        updatedAt=datetime(2025, 2, 1, tzinfo=timezone.utc),
        target=make_obj(id="tgt-2", role="comms", soc="nrf9151", appId=108),
    )

    mock_storage = MagicMock()
    with patch("api.v2.products.firmware_builds.get_storage_client", return_value=mock_storage):
        with patch("api.v2.products.firmware_builds.get_bucket_name", return_value="test-bucket"):
            with patch("api.v2.products.firmware_builds.log_audit"):
                response = authed_client._client.post(
                    "/v2/products/prod-1/firmware/upload",
                    headers=auth_headers,
                    data={
                        "targetId": "tgt-2",
                        "version": "1.0.0",
                        "file": (BytesIO(b"\x00\x01\x02\x03"), "app.bin"),
                    },
                    content_type="multipart/form-data",
                )

    assert response.status_code == 201
    data = json.loads(response.data)
    assert data["data"]["targetId"] == "tgt-2"
    assert data["data"]["version"] == "1.0.0"


