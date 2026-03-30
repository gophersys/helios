"""Tests for the board discovery API — list branches, scan boards, board detail."""

import json
from unittest.mock import MagicMock, patch

import pytest


MOCK_REFS = {
    "branches": ["main", "release/v2.1", "feature/sigma5-rev2"],
    "tags": ["v1.0.0", "v2.0.0"],
}

MOCK_BOARDS = [
    {
        "board": "alpha",
        "socs": ["nrf52840", "nrf9151"],
        "revisions": ["rev1.1", "rev1.2"],
        "variants": ["alpha_b0"],
    },
    {
        "board": "sigma5",
        "socs": ["nrf52840"],
        "revisions": ["rev1.0"],
        "variants": ["sigma5_std"],
    },
]

MOCK_ALPHA_DETAIL = {
    "board": "alpha",
    "socs": ["nrf52840", "nrf9151"],
    "revisions": [
        {
            "name": "rev1.2",
            "peripherals": [
                {"compatible": "bosch,bmi270", "type": "accelerometer", "bus": "spi"},
                {"compatible": "ti,bq25180", "type": "charger", "bus": "i2c"},
            ],
        },
    ],
    "variants": ["alpha_b0"],
}


@pytest.fixture
def mock_ck_boards():
    """Patch the ck_boards service singleton used by the discovery handler."""
    with patch("api.v2.products.board_discovery.get_ck_boards_service") as mock_get:
        svc = MagicMock()
        mock_get.return_value = svc
        yield svc


# ---------------------------------------------------------------------------
# GET /v2/products/boards/branches
# ---------------------------------------------------------------------------

def test_list_branches(authed_client, mock_ck_boards):
    """Returns branches and tags from ck_boards repo."""
    mock_ck_boards.list_refs.return_value = MOCK_REFS

    response = authed_client.get("/v2/products/boards/branches")
    assert response.status_code == 200
    body = json.loads(response.data)
    data = body["data"]
    assert "main" in data["branches"]
    assert "v1.0.0" in data["tags"]


def test_list_branches_service_error(authed_client, mock_ck_boards):
    """Returns 500 when ck_boards service fails."""
    mock_ck_boards.list_refs.side_effect = RuntimeError("git failed")

    response = authed_client.get("/v2/products/boards/branches")
    assert response.status_code == 500


# ---------------------------------------------------------------------------
# GET /v2/products/boards/discover?branch=main
# ---------------------------------------------------------------------------

def test_discover_boards(authed_client, mock_ck_boards):
    """Scans all boards on the given branch."""
    mock_ck_boards.discover_boards.return_value = MOCK_BOARDS

    response = authed_client.get("/v2/products/boards/discover?branch=main")
    assert response.status_code == 200
    body = json.loads(response.data)
    boards = body["data"]
    assert len(boards) == 2
    names = [b["board"] for b in boards]
    assert "alpha" in names
    assert "sigma5" in names


def test_discover_boards_missing_branch(authed_client, mock_ck_boards):
    """Returns 400 when branch query param is missing."""
    response = authed_client.get("/v2/products/boards/discover")
    assert response.status_code == 400


def test_discover_boards_invalid_branch(authed_client, mock_ck_boards):
    """Returns 400 when branch doesn't exist."""
    mock_ck_boards.discover_boards.side_effect = ValueError("Ref 'bad' not found")

    response = authed_client.get("/v2/products/boards/discover?branch=bad")
    assert response.status_code == 400


# ---------------------------------------------------------------------------
# GET /v2/products/boards/discover/<board>?branch=main
# ---------------------------------------------------------------------------

def test_discover_board_detail(authed_client, mock_ck_boards):
    """Deep scan of a single board with peripheral manifest."""
    mock_ck_boards.discover_board_detail.return_value = MOCK_ALPHA_DETAIL

    response = authed_client.get("/v2/products/boards/discover/alpha?branch=main")
    assert response.status_code == 200
    body = json.loads(response.data)
    data = body["data"]
    assert data["board"] == "alpha"
    assert len(data["revisions"]) == 1
    assert data["revisions"][0]["name"] == "rev1.2"
    peripherals = data["revisions"][0]["peripherals"]
    assert any(p["compatible"] == "bosch,bmi270" for p in peripherals)


def test_discover_board_detail_missing_branch(authed_client, mock_ck_boards):
    """Returns 400 when branch query param is missing."""
    response = authed_client.get("/v2/products/boards/discover/alpha")
    assert response.status_code == 400


def test_discover_board_detail_not_found(authed_client, mock_ck_boards):
    """Returns 404 when board doesn't exist on the branch."""
    mock_ck_boards.discover_board_detail.side_effect = ValueError("Board 'nope' not found")

    response = authed_client.get("/v2/products/boards/discover/nope?branch=main")
    assert response.status_code == 404


def test_discover_board_detail_not_found_does_not_leak_exception(authed_client, mock_ck_boards):
    """404 message uses safe template — no raw exception text returned to client."""
    mock_ck_boards.discover_board_detail.side_effect = ValueError(
        "Board 'nope' not found: internal path /secrets/repo"
    )

    response = authed_client.get("/v2/products/boards/discover/nope?branch=main")
    assert response.status_code == 404
    body = json.loads(response.data)
    msg = body["errors"][0]["message"]
    assert "/secrets/repo" not in msg
    assert "internal path" not in msg
    # Safe template used
    assert "nope" in msg
    assert "main" in msg


def test_discover_board_detail_validation_error_does_not_leak_exception(authed_client, mock_ck_boards):
    """400 message for non-not-found ValueError is a safe generic message."""
    mock_ck_boards.discover_board_detail.side_effect = ValueError(
        "Schema parse error at /internal/config: unexpected token"
    )

    response = authed_client.get("/v2/products/boards/discover/alpha?branch=main")
    assert response.status_code == 400
    body = json.loads(response.data)
    msg = body["errors"][0]["message"]
    assert "/internal/config" not in msg
    assert "unexpected token" not in msg


def test_discover_boards_validation_error_does_not_leak_exception(authed_client, mock_ck_boards):
    """discover_boards 400 does not expose raw ValueError text."""
    mock_ck_boards.discover_boards.side_effect = ValueError(
        "Ref 'bad' not found in /var/repo/.git"
    )

    response = authed_client.get("/v2/products/boards/discover?branch=bad")
    assert response.status_code == 400
    body = json.loads(response.data)
    msg = body["errors"][0]["message"]
    assert "/var/repo" not in msg
    assert "not found in" not in msg
