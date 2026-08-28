"""Tests for services/ck_boards/service.py — board parsing, name splitting, scanning."""

from __future__ import annotations

import threading
from unittest.mock import MagicMock, patch

import pytest
import requests


# ---------------------------------------------------------------------------
# _split_board_name
# ---------------------------------------------------------------------------

class TestSplitBoardName:
    """Tests for _split_board_name()."""

    def test_standard_format(self):
        """Splits alpha_b0 into family and revision."""
        from src.services.ck_boards.service import _split_board_name

        family, rev = _split_board_name("alpha_b0")
        assert family == "alpha"
        assert rev == "b0"

    def test_multi_part_family(self):
        """Splits sigma5_c0 preserving multi-part family name."""
        from src.services.ck_boards.service import _split_board_name

        family, rev = _split_board_name("sigma5_c0")
        assert family == "sigma5"
        assert rev == "c0"

    def test_complex_family_name(self):
        """Splits iwsck_a1 correctly."""
        from src.services.ck_boards.service import _split_board_name

        family, rev = _split_board_name("iwsck_a1")
        assert family == "iwsck"
        assert rev == "a1"

    def test_no_revision_pattern(self):
        """Returns full name as family with empty revision when no match."""
        from src.services.ck_boards.service import _split_board_name

        family, rev = _split_board_name("standalone")
        assert family == "standalone"
        assert rev == ""

    def test_multiple_underscores(self):
        """Handles names with multiple underscores."""
        from src.services.ck_boards.service import _split_board_name

        family, rev = _split_board_name("my_custom_board_a2")
        assert family == "my_custom_board"
        assert rev == "a2"


# ---------------------------------------------------------------------------
# _parse_board_yml
# ---------------------------------------------------------------------------

class TestParseBoardYml:
    """Tests for _parse_board_yml()."""

    def test_standard_board_yml(self):
        """Parses a standard board.yml with socs and revisions."""
        from src.services.ck_boards.service import _parse_board_yml

        content = """
board:
  name: alpha_b0
  vendor: corekinect
  socs:
    - name: nrf52840
    - name: nrf9151
  revision:
    revisions:
      - name: b0
"""
        result = _parse_board_yml(content)

        assert result["name"] == "alpha_b0"
        assert result["vendor"] == "corekinect"
        assert result["socs"] == ["nrf52840", "nrf9151"]
        assert result["revisions"] == ["b0"]

    def test_board_with_variants(self):
        """Parses board.yml with SoC variants."""
        from src.services.ck_boards.service import _parse_board_yml

        content = """
board:
  name: test_board
  vendor: testco
  socs:
    - name: nrf52840
      variants:
        - name: nrf52840dk
        - name: nrf52840dongle
"""
        result = _parse_board_yml(content)

        assert result["variants"] == ["nrf52840dk", "nrf52840dongle"]

    def test_board_without_revision(self):
        """Parses board.yml without revision block."""
        from src.services.ck_boards.service import _parse_board_yml

        content = """
board:
  name: simple
  vendor: acme
  socs:
    - name: esp32
"""
        result = _parse_board_yml(content)

        assert result["name"] == "simple"
        assert result["revisions"] == []

    def test_raises_on_non_dict(self):
        """Raises ValueError for non-dict YAML."""
        from src.services.ck_boards.service import _parse_board_yml

        with pytest.raises(ValueError, match="must be a YAML mapping"):
            _parse_board_yml("just a string")

    def test_bare_dict_without_board_key(self):
        """Parses dict without board key using top-level data."""
        from src.services.ck_boards.service import _parse_board_yml

        content = """
name: flat_board
vendor: flatco
socs:
  - name: nrf9160
"""
        result = _parse_board_yml(content)

        assert result["name"] == "flat_board"
        assert result["vendor"] == "flatco"

    def test_empty_socs(self):
        """Handles board with no socs."""
        from src.services.ck_boards.service import _parse_board_yml

        content = """
board:
  name: no_soc
  vendor: nobody
  socs: []
"""
        result = _parse_board_yml(content)

        assert result["socs"] == []
        assert result["variants"] == []


# ---------------------------------------------------------------------------
# Helper to create a CkBoardsService with mocked Bitbucket API
# ---------------------------------------------------------------------------

def _make_service():
    """Create a CkBoardsService bypassing the real __init__ / _verify_access."""
    from src.services.ck_boards.service import CkBoardsService

    with patch.object(CkBoardsService, "__init__", lambda self, **kw: None):
        svc = CkBoardsService.__new__(CkBoardsService)
        svc._workspace = "test-workspace"
        svc._repo_slug = "ck-boards"
        svc._auth = ("test@test.com", "token")
        svc._fetch_interval = 60
        svc._cache = {}
        svc._cache_time = {}
        svc._cache_ttl = 60
        svc._lock = threading.Lock()
        svc._ready = True
        return svc


# ---------------------------------------------------------------------------
# CkBoardsService — list_refs
# ---------------------------------------------------------------------------

class TestCkBoardsServiceListRefs:
    """Tests for CkBoardsService.list_refs() with mocked REST API."""

    @patch("src.services.ck_boards.service.requests.get")
    def test_list_refs_returns_every_branch_and_tag(self, mock_get):
        """No environment filtering — every ref the repo exposes is returned."""
        svc = _make_service()

        branches_resp = MagicMock()
        branches_resp.status_code = 200
        branches_resp.json.return_value = {
            "values": [{"name": "main"}, {"name": "develop"}, {"name": "feature/x"}],
        }

        tags_resp = MagicMock()
        tags_resp.status_code = 200
        tags_resp.json.return_value = {
            "values": [{"name": "v1.0"}],
        }

        mock_get.side_effect = [branches_resp, tags_resp]

        refs = svc.list_refs()
        assert refs["branches"] == ["main", "develop", "feature/x"]
        assert refs["tags"] == ["v1.0"]


# ---------------------------------------------------------------------------
# CkBoardsService — _scan_boards (REST API version)
# ---------------------------------------------------------------------------

class TestScanBoards:
    """Tests for CkBoardsService._scan_boards() with mocked REST API."""

    @patch("src.services.ck_boards.service.requests.get")
    def test_scan_discovers_families(self, mock_get):
        """Scans board directories via REST API and groups by family."""
        svc = _make_service()

        # _find_boards_path: list current/boards → returns vendor dir
        boards_list_resp = MagicMock()
        boards_list_resp.status_code = 200
        boards_list_resp.json.return_value = {
            "values": [{"type": "commit_directory", "path": "current/boards/corekinect"}],
        }

        # _scan_boards: list entries in boards path
        entries_resp = MagicMock()
        entries_resp.status_code = 200
        entries_resp.json.return_value = {
            "values": [
                {"type": "commit_directory", "path": "current/boards/corekinect/alpha_a0"},
                {"type": "commit_directory", "path": "current/boards/corekinect/alpha_b0"},
                {"type": "commit_directory", "path": "current/boards/corekinect/sigma5_c0"},
            ],
        }

        # board.yml file contents (3 calls to _api_get/_get_file)
        alpha_a0_resp = MagicMock()
        alpha_a0_resp.text = "board:\n  name: alpha_a0\n  vendor: ck\n  socs:\n    - name: nrf52840\n"
        alpha_b0_resp = MagicMock()
        alpha_b0_resp.text = "board:\n  name: alpha_b0\n  vendor: ck\n  socs:\n    - name: nrf52840\n    - name: nrf9151\n"
        sigma5_c0_resp = MagicMock()
        sigma5_c0_resp.text = "board:\n  name: sigma5_c0\n  vendor: ck\n  socs:\n    - name: nrf54l15\n"

        mock_get.side_effect = [boards_list_resp, entries_resp, alpha_a0_resp, alpha_b0_resp, sigma5_c0_resp]

        families = svc._scan_boards("main")

        family_names = [f["family"] for f in families]
        assert "alpha" in family_names
        assert "sigma5" in family_names

        alpha = next(f for f in families if f["family"] == "alpha")
        assert len(alpha["revisions"]) == 2
        assert alpha["vendor"] == "ck"

    @patch("src.services.ck_boards.service.requests.get")
    def test_scan_skips_non_board_dirs(self, mock_get):
        """Skips entries without board.yml (404 from REST API)."""
        svc = _make_service()

        boards_list_resp = MagicMock()
        boards_list_resp.status_code = 200
        boards_list_resp.json.return_value = {
            "values": [{"type": "commit_directory", "path": "current/boards/corekinect"}],
        }

        entries_resp = MagicMock()
        entries_resp.status_code = 200
        entries_resp.json.return_value = {
            "values": [
                {"type": "commit_directory", "path": "current/boards/corekinect/not_a_board"},
                {"type": "commit_file", "path": "current/boards/corekinect/readme.txt"},
            ],
        }

        # board.yml fetch returns HTTPError (404)
        board_yml_resp = MagicMock()
        board_yml_resp.status_code = 404
        board_yml_resp.raise_for_status.side_effect = requests.HTTPError(response=board_yml_resp)

        mock_get.side_effect = [boards_list_resp, entries_resp, board_yml_resp]

        families = svc._scan_boards("main")
        assert len(families) == 0

    @patch("src.services.ck_boards.service.requests.get")
    def test_scan_handles_malformed_yml(self, mock_get):
        """Malformed board.yml files are skipped with warning."""
        svc = _make_service()

        boards_list_resp = MagicMock()
        boards_list_resp.status_code = 200
        boards_list_resp.json.return_value = {
            "values": [{"type": "commit_directory", "path": "current/boards/corekinect"}],
        }

        entries_resp = MagicMock()
        entries_resp.status_code = 200
        entries_resp.json.return_value = {
            "values": [
                {"type": "commit_directory", "path": "current/boards/corekinect/bad_board_a0"},
            ],
        }

        # board.yml with malformed YAML
        bad_yml_resp = MagicMock()
        bad_yml_resp.text = "this is not valid yaml: ["

        mock_get.side_effect = [boards_list_resp, entries_resp, bad_yml_resp]

        families = svc._scan_boards("main")
        assert len(families) == 0


# ---------------------------------------------------------------------------
# CkBoardsService — _find_boards_path (REST API version)
# ---------------------------------------------------------------------------

class TestFindBoardsPath:
    """Tests for CkBoardsService._find_boards_path()."""

    @patch("src.services.ck_boards.service.requests.get")
    def test_finds_current_boards_vendor(self, mock_get):
        """Finds boards at current/boards/<vendor>/ layout."""
        svc = _make_service()

        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {
            "values": [{"type": "commit_directory", "path": "current/boards/corekinect"}],
        }
        mock_get.return_value = resp

        result = svc._find_boards_path("main")
        assert result == "current/boards/corekinect"

    @patch("src.services.ck_boards.service.requests.get")
    def test_falls_back_to_boards_dir(self, mock_get):
        """Falls back to boards/ directory when current/boards/ is empty."""
        svc = _make_service()

        empty_resp = MagicMock()
        empty_resp.status_code = 404
        empty_resp.json.return_value = {"values": []}

        boards_resp = MagicMock()
        boards_resp.status_code = 200
        boards_resp.json.return_value = {
            "values": [{"type": "commit_directory", "path": "boards/alpha_b0"}],
        }

        mock_get.side_effect = [empty_resp, boards_resp]

        result = svc._find_boards_path("main")
        assert result == "boards"

    @patch("src.services.ck_boards.service.requests.get")
    def test_returns_empty_when_no_boards_found(self, mock_get):
        """Returns empty string when no boards directory found."""
        svc = _make_service()

        empty_resp = MagicMock()
        empty_resp.status_code = 404
        empty_resp.json.return_value = {"values": []}

        mock_get.return_value = empty_resp

        result = svc._find_boards_path("main")
        assert result == ""
