"""Tests for the ck_boards REST API service — board parsing, discovery, refs."""

import textwrap
import threading
from unittest.mock import MagicMock, patch

import pytest
import requests

from src.services.ck_boards.service import CkBoardsService, _split_board_name, _parse_board_yml


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_service(environment="development"):
    """Create a CkBoardsService bypassing __init__ / _verify_access."""
    with patch.object(CkBoardsService, "__init__", lambda self, **kw: None):
        svc = CkBoardsService.__new__(CkBoardsService)
        svc._workspace = "test-workspace"
        svc._repo_slug = "ck-boards"
        svc._auth = ("test@test.com", "token")
        svc._environment = environment
        svc._fetch_interval = 0
        svc._cache = {}
        svc._cache_time = {}
        svc._cache_ttl = 60
        svc._lock = threading.Lock()
        svc._ready = True
        return svc


def _mock_boards_api(mock_get):
    """Set up mock responses for the Bitbucket REST API to simulate a board repo.

    Simulates this layout:
        current/boards/corekinect/alpha_a0/board.yml
        current/boards/corekinect/alpha_b0/board.yml
        current/boards/corekinect/sigma5_c0/board.yml
    """
    # list_refs: branches
    branches_resp = MagicMock()
    branches_resp.status_code = 200
    branches_resp.json.return_value = {
        "values": [
            {"name": "main"},
            {"name": "release/v2.1"},
        ],
    }

    # list_refs: tags
    tags_resp = MagicMock()
    tags_resp.status_code = 200
    tags_resp.json.return_value = {
        "values": [{"name": "v1.0.0"}],
    }

    # _find_boards_path: current/boards → vendor dirs
    boards_list_resp = MagicMock()
    boards_list_resp.status_code = 200
    boards_list_resp.json.return_value = {
        "values": [{"type": "commit_directory", "path": "current/boards/corekinect"}],
    }

    # _scan_boards: entries in vendor dir
    entries_resp = MagicMock()
    entries_resp.status_code = 200
    entries_resp.json.return_value = {
        "values": [
            {"type": "commit_directory", "path": "current/boards/corekinect/alpha_a0"},
            {"type": "commit_directory", "path": "current/boards/corekinect/alpha_b0"},
            {"type": "commit_directory", "path": "current/boards/corekinect/sigma5_c0"},
        ],
    }

    # board.yml file contents
    alpha_a0_resp = MagicMock()
    alpha_a0_resp.text = textwrap.dedent("""\
        board:
          name: alpha_a0
          vendor: corekinect
          socs:
            - name: nrf9160
            - name: nrf52840
          revision:
            revisions: []
    """)

    alpha_b0_resp = MagicMock()
    alpha_b0_resp.text = textwrap.dedent("""\
        board:
          name: alpha_b0
          vendor: corekinect
          socs:
            - name: nrf9151
            - name: nrf52840
          revision:
            revisions: []
    """)

    sigma5_c0_resp = MagicMock()
    sigma5_c0_resp.text = textwrap.dedent("""\
        board:
          name: sigma5_c0
          vendor: corekinect
          socs:
            - name: nrf52840
          revision:
            revisions: []
    """)

    return {
        "branches": branches_resp,
        "tags": tags_resp,
        "boards_list": boards_list_resp,
        "entries": entries_resp,
        "alpha_a0": alpha_a0_resp,
        "alpha_b0": alpha_b0_resp,
        "sigma5_c0": sigma5_c0_resp,
    }


# ---------------------------------------------------------------------------
# _split_board_name helper
# ---------------------------------------------------------------------------

def test_split_board_name_standard():
    """Standard {family}_{rev} names split correctly."""
    assert _split_board_name("alpha_a0") == ("alpha", "a0")
    assert _split_board_name("alpha_b0") == ("alpha", "b0")
    assert _split_board_name("sigma5_c0") == ("sigma5", "c0")
    assert _split_board_name("iwsck_a1") == ("iwsck", "a1")


def test_split_board_name_no_revision():
    """Names without revision pattern return full name as family."""
    assert _split_board_name("standalone") == ("standalone", "")
    assert _split_board_name("no_match_here") == ("no_match_here", "")


def test_split_board_name_underscore_in_family():
    """Family names with underscores still split on the last letter+digit pattern."""
    assert _split_board_name("my_board_b0") == ("my_board", "b0")


# ---------------------------------------------------------------------------
# _parse_board_yml
# ---------------------------------------------------------------------------

def test_parse_board_yml_zephyr_format():
    """Parses Zephyr-style board.yml with nested 'board:' key."""
    content = textwrap.dedent("""\
        board:
          name: alpha_b0
          vendor: corekinect
          socs:
            - name: nrf9151
            - name: nrf52840
          revision:
            revisions:
              - name: rev1.2
    """)
    result = _parse_board_yml(content)
    assert result["name"] == "alpha_b0"
    assert result["vendor"] == "corekinect"
    assert result["socs"] == ["nrf9151", "nrf52840"]
    assert result["revisions"] == ["rev1.2"]


def test_parse_board_yml_flat_format():
    """Parses flat-style board.yml without 'board:' wrapper."""
    content = textwrap.dedent("""\
        name: theta_c0
        vendor: corekinect
        socs:
          - name: nrf52840
    """)
    result = _parse_board_yml(content)
    assert result["name"] == "theta_c0"
    assert result["socs"] == ["nrf52840"]
    assert result["revisions"] == []


def test_parse_board_yml_with_variants():
    """Variants are extracted from socs[].variants[]."""
    content = textwrap.dedent("""\
        board:
          name: alpha_b0
          vendor: corekinect
          socs:
            - name: nrf52840
              variants:
                - name: debug
                - name: release
    """)
    result = _parse_board_yml(content)
    assert result["variants"] == ["debug", "release"]


# ---------------------------------------------------------------------------
# Branch / tag listing
# ---------------------------------------------------------------------------

@patch("src.services.ck_boards.service.requests.get")
def test_list_branches(mock_get):
    """list_refs returns branches and tags from the REST API."""
    svc = _make_service()
    resps = _mock_boards_api(mock_get)
    mock_get.side_effect = [resps["branches"], resps["tags"]]

    refs = svc.list_refs()
    assert "main" in refs["branches"]
    assert "release/v2.1" in refs["branches"]
    assert "v1.0.0" in refs["tags"]


# ---------------------------------------------------------------------------
# Board scanning — returns grouped families
# ---------------------------------------------------------------------------

@patch("src.services.ck_boards.service.requests.get")
def test_discover_boards(mock_get):
    """discover_boards returns family-grouped list of boards."""
    svc = _make_service()
    resps = _mock_boards_api(mock_get)
    mock_get.side_effect = [
        resps["boards_list"],
        resps["entries"],
        resps["alpha_a0"],
        resps["alpha_b0"],
        resps["sigma5_c0"],
    ]

    families = svc.discover_boards("main")
    family_names = [f["family"] for f in families]
    assert "alpha" in family_names
    assert "sigma5" in family_names

    alpha = next(f for f in families if f["family"] == "alpha")
    assert alpha["vendor"] == "corekinect"
    assert len(alpha["revisions"]) == 2

    rev_names = [r["ckBoardsName"] for r in alpha["revisions"]]
    assert "alpha_a0" in rev_names
    assert "alpha_b0" in rev_names

    # Check SoCs on a revision
    b0 = next(r for r in alpha["revisions"] if r["ckBoardsName"] == "alpha_b0")
    assert set(b0["socs"]) == {"nrf9151", "nrf52840"}

    sigma = next(f for f in families if f["family"] == "sigma5")
    assert len(sigma["revisions"]) == 1
    assert sigma["revisions"][0]["socs"] == ["nrf52840"]


@patch("src.services.ck_boards.service.requests.get")
def test_discover_boards_empty_branch(mock_get):
    """discover_boards returns empty list when no boards directory found."""
    svc = _make_service()

    empty_resp = MagicMock()
    empty_resp.status_code = 404
    empty_resp.json.return_value = {"values": []}
    mock_get.return_value = empty_resp

    families = svc.discover_boards("nonexistent-branch")
    assert families == []


# ---------------------------------------------------------------------------
# Single board detail
# ---------------------------------------------------------------------------

@patch("src.services.ck_boards.service.requests.get")
def test_discover_board_detail(mock_get):
    """discover_board_detail returns detail for a single product family."""
    svc = _make_service()
    resps = _mock_boards_api(mock_get)
    mock_get.side_effect = [
        resps["boards_list"],
        resps["entries"],
        resps["alpha_a0"],
        resps["alpha_b0"],
        resps["sigma5_c0"],
    ]

    detail = svc.discover_board_detail("alpha", "main")
    assert detail["family"] == "alpha"
    assert detail["vendor"] == "corekinect"
    assert len(detail["revisions"]) == 2


@patch("src.services.ck_boards.service.requests.get")
def test_discover_board_detail_not_found(mock_get):
    """discover_board_detail raises ValueError for unknown family."""
    svc = _make_service()
    resps = _mock_boards_api(mock_get)
    mock_get.side_effect = [
        resps["boards_list"],
        resps["entries"],
        resps["alpha_a0"],
        resps["alpha_b0"],
        resps["sigma5_c0"],
    ]

    with pytest.raises(ValueError, match="not found"):
        svc.discover_board_detail("nonexistent-board", "main")


# ---------------------------------------------------------------------------
# Cache behavior
# ---------------------------------------------------------------------------

@patch("src.services.ck_boards.service.requests.get")
def test_fetch_clears_cache(mock_get):
    """fetch() clears the internal cache so next discover_boards hits the API."""
    svc = _make_service()
    resps = _mock_boards_api(mock_get)

    # First call populates cache
    mock_get.side_effect = [
        resps["boards_list"],
        resps["entries"],
        resps["alpha_a0"],
        resps["alpha_b0"],
        resps["sigma5_c0"],
    ]
    svc.discover_boards("main")
    assert "main" in svc._cache

    # Clear cache
    svc.fetch()
    assert "main" not in svc._cache
