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
    with patch("api.v2.catalog.shared.presigned_get_url", return_value=None):
        yield


# ── 1. Chipset in use by board revision blocks delete, then succeeds ──


def test_chipset_in_use_by_revision_blocks_delete(authed_client, mock_db):
    """Deleting a chipset referenced by a board revision should 409, then succeed once cleared."""
    mock_db.chipset.find_unique.return_value = make_obj(
        id="chip-1",
        name="nRF52840",
        manufacturer="Nordic Semiconductor",
        isModem=False,
        description=None,
        active=True,
        createdAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
        updatedAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
    )

    # Reference exists in board revision chipsets
    mock_db.boardrevisionchipset.find_first.return_value = make_obj(
        id="brc-1",
        boardRevisionId="rev-1",
        chipsetId="chip-1",
    )

    response = authed_client.delete("/v2/products/chipsets/chip-1")
    assert response.status_code == 409
    data = json.loads(response.data)
    assert "board revisions" in data["errors"][0]["message"].lower()

    # Clear references
    mock_db.boardrevisionchipset.find_first.return_value = None
    mock_db.firmwarebuild.find_first.return_value = None

    with patch("src.api.v2.catalog.chipsets.log_audit"):
        response = authed_client.delete("/v2/products/chipsets/chip-1")

    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["data"]["deleted"] is True


# ── 2. Chipset in use by firmware build blocks delete ──


def test_chipset_in_use_by_firmware_blocks_delete(authed_client, mock_db):
    """Deleting a chipset referenced by a firmware build should 409."""
    mock_db.chipset.find_unique.return_value = make_obj(
        id="chip-2",
        name="nRF9160",
        manufacturer="Nordic Semiconductor",
        isModem=True,
        description=None,
        active=True,
        createdAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
        updatedAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
    )

    # No board revision chipset reference
    mock_db.boardrevisionchipset.find_first.return_value = None
    # But firmware build reference exists
    mock_db.firmwarebuild.find_first.return_value = make_obj(
        id="build-1",
        chipsetId="chip-2",
    )

    response = authed_client.delete("/v2/products/chipsets/chip-2")
    assert response.status_code == 409
    data = json.loads(response.data)
    assert "firmware builds" in data["errors"][0]["message"].lower()


# ── 3. Board with revisions blocks delete ──


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


# ── 4. Product with sessions blocks delete ──


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


# ── 5. Product with tests blocks delete ──


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


# ── 6. Board name unique per product ──


def test_board_name_unique_per_product(authed_client, mock_db):
    """Same board name should conflict in the same product but succeed in a different product."""
    # Product exists
    mock_db.product.find_unique.return_value = make_obj(
        id="prod-1",
        name="Product Alpha",
    )

    # Duplicate board exists for prod-1
    mock_db.board.find_first.return_value = make_obj(
        id="existing-board",
        productId="prod-1",
        name="Main Board",
    )

    response = authed_client.post(
        "/v2/products/prod-1/boards",
        data=json.dumps({"name": "Main Board"}),
    )
    assert response.status_code == 409

    # Now try with a different product where no duplicate exists
    mock_db.product.find_unique.return_value = make_obj(
        id="prod-2",
        name="Product Beta",
    )
    mock_db.board.find_first.return_value = None

    mock_db.board.create.return_value = make_obj(
        id="board-new",
        productId="prod-2",
        name="Main Board",
        description=None,
        active=True,
        createdAt=datetime(2025, 2, 1, tzinfo=timezone.utc),
        updatedAt=datetime(2025, 2, 1, tzinfo=timezone.utc),
        revisions=[],
    )

    with patch("src.api.v2.catalog.boards.log_audit"):
        response = authed_client.post(
            "/v2/products/prod-2/boards",
            data=json.dumps({"name": "Main Board"}),
        )

    assert response.status_code == 201
    data = json.loads(response.data)
    assert data["data"]["name"] == "Main Board"
    assert data["data"]["productId"] == "prod-2"


# ── 7. Revision version unique per board ──


def test_revision_version_unique_per_board(authed_client, mock_db):
    """Same revision version should conflict on the same board but succeed on a different board."""
    # Board exists
    mock_db.board.find_first.return_value = make_obj(
        id="board-1",
        productId="prod-1",
        name="Main Board",
    )

    # Duplicate version exists for board-1
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

    # Now try with a different board where no duplicate exists
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
        selectedBuilds=None,
        status="ACTIVE",
        notes=None,
        createdAt=datetime(2025, 2, 1, tzinfo=timezone.utc),
        updatedAt=datetime(2025, 2, 1, tzinfo=timezone.utc),
        chipsets=[],
    )

    # Re-fetch after creation
    mock_db.boardrevision.find_unique.return_value = make_obj(
        id="rev-new",
        boardId="board-2",
        version="1.0",
        selectedBuilds=None,
        status="ACTIVE",
        notes=None,
        createdAt=datetime(2025, 2, 1, tzinfo=timezone.utc),
        updatedAt=datetime(2025, 2, 1, tzinfo=timezone.utc),
        chipsets=[],
    )

    with patch("src.api.v2.catalog.board_revisions.log_audit"):
        response = authed_client.post(
            "/v2/products/prod-1/boards/board-2/revisions",
            data=json.dumps({"version": "1.0"}),
        )

    assert response.status_code == 201
    data = json.loads(response.data)
    assert data["data"]["version"] == "1.0"
    assert data["data"]["boardId"] == "board-2"


# ── 8. Firmware version unique per product + chipset ──


def test_firmware_version_unique_per_product_chipset(authed_client, mock_db):
    """Same firmware version + chipset should conflict, but different chipset should succeed."""
    mock_db.product.find_unique.return_value = make_obj(
        id="prod-1",
        name="Product Alpha",
    )

    mock_db.chipset.find_unique.return_value = make_obj(
        id="chip-1",
        name="nRF52840",
        isModem=False,
    )

    # Duplicate exists for prod-1 / chip-1 / 1.0.0
    mock_db.firmwarebuild.find_first.return_value = make_obj(
        id="build-existing",
        productId="prod-1",
        chipsetId="chip-1",
        version="1.0.0",
    )

    # Multipart upload (headers without Content-Type so Flask uses multipart)
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
            "chipsetId": "chip-1",
            "version": "1.0.0",
            "file": (BytesIO(b"\x00\x01\x02\x03"), "app.bin"),
        },
        content_type="multipart/form-data",
    )
    assert response.status_code == 409

    # Now upload with a different chipset (chip-2) — no duplicate
    mock_db.chipset.find_unique.return_value = make_obj(
        id="chip-2",
        name="nRF9160",
        isModem=False,
    )
    mock_db.firmwarebuild.find_first.return_value = None

    mock_db.firmwarebuild.create.return_value = make_obj(
        id="build-new",
        productId="prod-1",
        chipsetId="chip-2",
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
        chipsetId="chip-2",
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
        chipset=make_obj(id="chip-2", name="nRF9160", isModem=False),
    )

    mock_storage = MagicMock()
    with patch("api.v2.catalog.firmware_builds.get_storage_client", return_value=mock_storage):
        with patch("api.v2.catalog.firmware_builds.get_bucket_name", return_value="test-bucket"):
            with patch("api.v2.catalog.firmware_builds.log_audit"):
                response = authed_client._client.post(
                    "/v2/products/prod-1/firmware/upload",
                    headers=auth_headers,
                    data={
                        "chipsetId": "chip-2",
                        "version": "1.0.0",
                        "file": (BytesIO(b"\x00\x01\x02\x03"), "app.bin"),
                    },
                    content_type="multipart/form-data",
                )

    assert response.status_code == 201
    data = json.loads(response.data)
    assert data["data"]["chipsetId"] == "chip-2"
    assert data["data"]["version"] == "1.0.0"


# ── 9. Updating revision replaces chipsets ──


def test_update_revision_replaces_chipsets(authed_client, mock_db):
    """Updating a revision's chipsetIds should delete old and create new associations."""
    mock_db.board.find_first.return_value = make_obj(
        id="board-1",
        productId="prod-1",
        name="Main Board",
    )

    mock_db.boardrevision.find_first.return_value = make_obj(
        id="rev-1",
        boardId="board-1",
        version="1.0",
        status="ACTIVE",
        notes=None,
        createdAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
        updatedAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
    )

    # Chipset validation — each find_unique call returns a valid chipset
    mock_db.chipset.find_unique.side_effect = [
        make_obj(id="chip-b", name="ESP32", isModem=False),
        make_obj(id="chip-c", name="nRF9160", isModem=True),
    ]

    # Re-fetch after update
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
            make_obj(chipset=make_obj(id="chip-b", name="ESP32", isModem=False)),
            make_obj(chipset=make_obj(id="chip-c", name="nRF9160", isModem=True)),
        ],
    )

    with patch("src.api.v2.catalog.board_revisions.log_audit"):
        response = authed_client.put(
            "/v2/products/prod-1/boards/board-1/revisions/rev-1",
            data=json.dumps({
                "chipsetIds": ["chip-b", "chip-c"],
            }),
        )

    assert response.status_code == 200
    data = json.loads(response.data)
    assert len(data["data"]["chipsets"]) == 2
    chipset_ids = [c["id"] for c in data["data"]["chipsets"]]
    assert "chip-b" in chipset_ids
    assert "chip-c" in chipset_ids

    # Verify delete_many was called to remove old associations
    mock_db.boardrevisionchipset.delete_many.assert_called_once_with(
        where={"boardRevisionId": "rev-1"}
    )

    # Verify create was called for each new chipset
    assert mock_db.boardrevisionchipset.create.call_count == 2


# ── 10. Updating revision selected builds ──


def test_update_revision_selected_builds(authed_client, mock_db):
    """Updating a revision's selectedBuilds should persist and return them."""
    mock_db.board.find_first.return_value = make_obj(
        id="board-1",
        productId="prod-1",
        name="Main Board",
    )

    mock_db.boardrevision.find_first.return_value = make_obj(
        id="rev-1",
        boardId="board-1",
        version="1.0",
        status="ACTIVE",
        notes=None,
        createdAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
        updatedAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
    )

    # Re-fetch after update includes selectedBuilds
    mock_db.boardrevision.find_unique.return_value = make_obj(
        id="rev-1",
        boardId="board-1",
        version="1.0",
        selectedBuilds={"chip-1": "build-1"},
        status="ACTIVE",
        notes=None,
        createdAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
        updatedAt=datetime(2025, 1, 15, tzinfo=timezone.utc),
        chipsets=[],
    )

    with patch("src.api.v2.catalog.board_revisions.log_audit"):
        response = authed_client.put(
            "/v2/products/prod-1/boards/board-1/revisions/rev-1",
            data=json.dumps({
                "selectedBuilds": {"chip-1": "build-1"},
            }),
        )

    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["data"]["selectedBuilds"] == {"chip-1": "build-1"}
